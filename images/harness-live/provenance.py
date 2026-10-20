"""Verify official native release identities before any vendor code executes."""
import base64
import hashlib
import json
from pathlib import Path
import re
import tarfile


TRUST_DIR = Path(__file__).with_name("trust")
CLAUDE_FINGERPRINT = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
NPM_KEY_ID = "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U"
OPENSSL = "/usr/bin/openssl"
GPGV = "/usr/bin/gpgv"
NODE = "/usr/local/bin/node"
MAX_METADATA = 1024 * 1024
MAX_PAYLOAD = 512 * 1024 * 1024
EXACT_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9._-]+)?\Z")


def digest(path, algorithm="sha256"):
    result = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.digest()


def bounded(path, limit):
    if not 0 < path.stat().st_size <= limit:
        raise ValueError("Release file is empty or exceeds its size limit: " + path.name)


def verify_claude_manifest(manifest, signature, directory, env, run):
    """Use only the image's reviewed release key; never an operator keyring."""
    bounded(manifest, MAX_METADATA)
    bounded(signature, MAX_METADATA)
    armor = (TRUST_DIR / "claude-code.asc").read_text().splitlines()
    if not armor or armor[0] != "-----BEGIN PGP PUBLIC KEY BLOCK-----":
        raise ValueError("Invalid pinned Claude release key")
    collecting = False
    body = []
    for line in armor[1:]:
        if not collecting:
            if not line.strip():
                collecting = True
            continue
        if line.startswith(("=", "-----END")):
            break
        body.append(line.strip())
    keyring = directory / "claude-keyring.gpg"
    keyring.write_bytes(base64.b64decode("".join(body), validate=True))
    home = directory / "gpgv-home"
    home.mkdir(mode=0o700, exist_ok=True)
    result = run([GPGV, "--homedir", str(home), "--keyring", str(keyring),
                  "--status-fd", "1", str(signature), str(manifest)], env=env, timeout=30)
    valid = [line.split() for line in result.stdout.splitlines()
             if line.startswith("[GNUPG:] VALIDSIG ")]
    if not any(CLAUDE_FINGERPRINT in (fields[2], fields[-1]) for fields in valid):
        raise ValueError("Claude manifest was not signed by the pinned release key")
    value = json.loads(manifest.read_text())
    if not isinstance(value, dict):
        raise ValueError("Claude release manifest must be an object")
    return value


def verify_npm_metadata(value, name, version, directory, env, run):
    """The pinned registry key authenticates name, exact version and SRI digest."""
    if not isinstance(value, dict):
        raise ValueError("npm release metadata must be an object")
    if value.get("name") != name or value.get("version") != version:
        raise ValueError("npm release metadata identity does not match the requested package")
    distribution = value.get("dist", {})
    if not isinstance(distribution, dict):
        raise ValueError("npm release distribution metadata must be an object")
    integrity = distribution.get("integrity", "")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise ValueError("npm release must provide a SHA512 integrity identity")
    expected = base64.b64decode(integrity[len("sha512-"):], validate=True)
    if len(expected) != 64:
        raise ValueError("Invalid npm SHA512 integrity identity")
    message = directory / "npm-signature-message"
    message.write_bytes(f"{name}@{version}:{integrity}".encode("utf-8"))
    signature = directory / "npm-signature.der"
    for candidate in distribution.get("signatures", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("keyid") != NPM_KEY_ID:
            continue
        encoded = candidate.get("sig", "")
        if not isinstance(encoded, str) or len(encoded) > 4096:
            continue
        try:
            signature.write_bytes(base64.b64decode(encoded, validate=True))
        except ValueError:
            continue
        result = run([OPENSSL, "dgst", "-sha256", "-verify", str(TRUST_DIR / "npm-registry.pem"),
                      "-signature", str(signature), str(message)], env=env, timeout=30, check=False)
        if result.returncode == 0:
            return expected
    raise ValueError("npm release metadata has no valid signature from the pinned registry key")


def install_native(name, selected_version, stage, env, fetch, run):
    """Return a verified native executable and auditable distribution metadata.

    `fetch` and `run` are the manager's bounded transport/process helpers.
    No downloaded shell, npm hook, launcher, or binary runs in this function.
    """
    if not isinstance(selected_version, str) or not EXACT_VERSION.fullmatch(selected_version):
        raise ValueError("A native release requires an exact version")
    stage = Path(stage)
    proof = stage / "provenance"
    proof.mkdir()
    executable = stage / "bin" / name
    if name == "claude":
        base = "https://downloads.claude.ai/claude-code-releases/" + selected_version
        manifest = proof / "manifest.json"
        signature = proof / "manifest.json.sig"
        fetch(base + "/manifest.json", manifest, env)
        fetch(base + "/manifest.json.sig", signature, env)
        value = verify_claude_manifest(manifest, signature, proof, env, run)
        if value.get("version") != selected_version:
            raise ValueError("Signed Claude manifest does not match the requested release")
        target = value.get("platforms", {}).get("linux-x64", {})
        checksum, size = target.get("checksum"), target.get("size")
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise ValueError("Signed Claude manifest lacks a valid Linux x64 checksum")
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_PAYLOAD:
            raise ValueError("Signed Claude manifest lacks a bounded Linux x64 binary size")
        source = base + "/linux-x64/claude"
        fetch(source, executable, env)
        if executable.stat().st_size != size or digest(executable).hex() != checksum:
            raise ValueError("Claude binary does not match its signed release identity")
        executable.chmod(0o755)
        return executable, {"distribution": "signed-native-release", "source": source,
                            "signing_key": CLAUDE_FINGERPRINT, "manifest_sha256": digest(manifest).hex(),
                            "signature_sha256": digest(signature).hex(), "payload_sha256": checksum}
    if name != "grok":
        raise ValueError("Unsupported native release: " + name)
    package = "@xai-official/grok-linux-x64"
    source = "https://registry.npmjs.org/" + package + "/" + selected_version
    metadata = proof / "npm-metadata.json"
    fetch(source, metadata, env)
    bounded(metadata, MAX_METADATA)
    value = json.loads(metadata.read_text())
    expected = verify_npm_metadata(value, package, selected_version, proof, env, run)
    tarball_url = ("https://registry.npmjs.org/@xai-official/grok-linux-x64/-/grok-linux-x64-"
                   + selected_version + ".tgz")
    if value["dist"].get("tarball") != tarball_url:
        raise ValueError("Grok npm tarball URL is outside its canonical official distribution")
    archive = proof / "grok.tgz"
    fetch(tarball_url, archive, env)
    bounded(archive, MAX_PAYLOAD)
    if digest(archive, "sha512") != expected:
        raise ValueError("Grok tarball does not match its signed release identity")
    compressed = proof / "grok.br"
    # Read one named regular file; never extract paths or links from a tarball.
    with tarfile.open(archive, "r:gz") as package_archive:
        entry = package_archive.getmember("package/bin/grok.br")
        if not entry.isfile() or not 0 < entry.size <= MAX_PAYLOAD:
            raise ValueError("Grok package must contain a bounded regular binary payload")
        with package_archive.extractfile(entry) as incoming, compressed.open("wb") as outgoing:
            while chunk := incoming.read(1024 * 1024):
                outgoing.write(chunk)
    script = ("const fs=require('fs'),zlib=require('zlib');"
              "fs.writeFileSync(process.argv[2],zlib.brotliDecompressSync("
              "fs.readFileSync(process.argv[1]),{maxOutputLength:536870912}));")
    run([NODE, "-e", script, str(compressed), str(executable)], env=env, timeout=90)
    bounded(executable, MAX_PAYLOAD)
    compressed.unlink()
    executable.chmod(0o755)
    return executable, {"distribution": "signed-npm-platform-package", "source": source,
                        "signing_key": NPM_KEY_ID, "package": package,
                        "metadata_sha256": digest(metadata).hex(), "integrity": value["dist"]["integrity"],
                        "payload_sha256": digest(executable).hex()}
