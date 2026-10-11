#!/usr/bin/env python3
"""Scan, sign, and verify exact image evidence without changing image content."""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from library import ROOT, encoded, read, validate_record
from xorder.transport import download

IDENTITY = "https://github.com/xormania/xorder/.github/workflows/publish.yml@refs/heads/master"
ISSUER = "https://token.actions.githubusercontent.com"
PREDICATE = "https://github.com/xormania/xorder/assurance/v1"
IMAGE = re.compile(r"^ghcr\.io/xormania/[a-z0-9-]+@sha256:[a-f0-9]{64}$")
POLICY = "no-fixable-critical-v1"
TRIVY = {
    "version": "0.75.0",
    "url": "https://github.com/aquasecurity/trivy/releases/download/v0.75.0/trivy_0.75.0_Linux-64bit.tar.gz",
    "sha256": "c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f",
}


def run(*args, env=None):
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"Assurance command failed ({args[0]} {args[1]}):\n{result.stdout}\n{result.stderr}")
    return result.stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def anonymous_registry_environment(config):
    # An existing empty Docker file prevents go-containerregistry's
    # DefaultKeychain from falling back to Podman or host credential files.
    (Path(config) / "config.json").write_text('{"auths":{}}\n')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("TRIVY_")
           and key not in {"GH_TOKEN", "GITHUB_TOKEN", "REGISTRY_AUTH_FILE", "DOCKER_AUTH_CONFIG", "COSIGN_REPOSITORY"}}
    env["DOCKER_CONFIG"] = str(config)
    return env


def install_scanner(directory):
    """Install checksum-pinned bytes, never execute a mutable upstream installer."""
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xorder-trivy-") as temporary:
        archive_path = Path(temporary) / "trivy.tar.gz"
        download(TRIVY["url"], archive_path, TRIVY["sha256"])
        with tarfile.open(archive_path) as archive:
            matches = [m for m in archive.getmembers() if m.name == "trivy" and m.isfile()]
            if len(matches) != 1:
                raise ValueError("Pinned scanner archive has no unique regular trivy executable")
            with archive.extractfile(matches[0]) as source:
                (directory / "trivy").write_bytes(source.read())
        (directory / "trivy").chmod(0o755)
    if os.environ.get("GITHUB_PATH"):
        with open(os.environ["GITHUB_PATH"], "a") as stream:
            stream.write(str(directory.resolve()) + "\n")
    return directory / "trivy"


def scan_summary(report):
    if (report.get("SchemaVersion") != 2 or not isinstance(report.get("Results"), list)
            or not report.get("Metadata", {}).get("OS", {}).get("Family")
            or not any(result.get("Class") == "os-pkgs" for result in report["Results"])):
        raise ValueError("Scanner did not produce a complete supported vulnerability report")
    counts = {level: 0 for level in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")}
    blocked = []
    for result in report["Results"]:
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list):
            raise ValueError("Malformed vulnerability results")
        for finding in vulnerabilities:
            severity = finding.get("Severity")
            if severity not in counts or not finding.get("VulnerabilityID"):
                raise ValueError("Malformed vulnerability finding")
            counts[severity] += 1
            if severity == "CRITICAL" and finding.get("FixedVersion"):
                blocked.append({"id": finding["VulnerabilityID"], "package": finding.get("PkgName"),
                                "fixed_version": finding["FixedVersion"]})
    return {"policy": POLICY, "status": "blocked" if blocked else "passed", "counts": counts,
            "fixable_critical": blocked}


def validate_receipt(receipt, artifact, source):
    if (receipt.get("schema_version") != 1 or receipt.get("artifact") != artifact
            or receipt.get("source_commit") != source or not IMAGE.fullmatch(artifact)
            or not re.fullmatch(r"[a-f0-9]{40}", source)
            or receipt.get("certificate_identity") != IDENTITY
            or receipt.get("certificate_oidc_issuer") != ISSUER
            or receipt.get("predicate_type") != PREDICATE
            or receipt.get("scan", {}).get("policy") != POLICY
            or receipt["scan"].get("status") != "passed"):
        raise ValueError("Assurance receipt differs from the exact image, source, signer, or accepted policy")
    if datetime.fromisoformat(receipt["completed_at"].replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Assurance completion time must include its timezone")
    if set(receipt["files"]) != {"vulnerabilities", "sbom", "scanner"}:
        raise ValueError("Assurance receipt needs the scan, SBOM, and scanner/database observations")
    for facts in receipt["files"].values():
        if (not re.fullmatch(r"[a-z]+-[a-f0-9]{64}\.json", facts["filename"])
                or not re.fullmatch(r"[a-f0-9]{64}", facts["sha256"])):
            raise ValueError("Invalid assurance asset identity")
    return receipt


def statements(output):
    """Cosign emits one authenticated DSSE envelope per JSON line (or a list)."""
    decoder = json.JSONDecoder()
    remaining = output.strip()
    while remaining:
        value, end = decoder.raw_decode(remaining)
        for envelope in value if isinstance(value, list) else [value]:
            yield json.loads(base64.b64decode(envelope["payload"], validate=True))
        remaining = remaining[end:].lstrip()


def verify_attestation(artifact, kind, predicate, env):
    output = run("cosign", "verify-attestation", "--type", kind, "--certificate-identity", IDENTITY,
                 "--certificate-oidc-issuer", ISSUER, artifact, env=env)
    expected_digest = artifact.split("@sha256:")[1]
    for statement in statements(output):
        if (statement.get("predicate") == predicate
                and any(subject.get("digest", {}).get("sha256") == expected_digest
                        for subject in statement.get("subject", []))):
            return
    raise ValueError("Authenticated attestation does not contain the expected predicate and exact image digest")


def verify_local(receipt, folder):
    validate_receipt(receipt, receipt["artifact"], receipt["source_commit"])
    for facts in receipt["files"].values():
        if sha256(folder / facts["filename"]) != facts["sha256"]:
            raise ValueError("Assurance evidence checksum mismatch")
    report = read(folder / receipt["files"]["vulnerabilities"]["filename"])
    if receipt["artifact"] not in report.get("Metadata", {}).get("RepoDigests", []):
        raise ValueError("Vulnerability evidence does not name the exact image digest")
    if scan_summary(report) != receipt["scan"]:
        raise ValueError("Recorded scan policy differs from the evidence findings")
    sbom = read(folder / receipt["files"]["sbom"]["filename"])
    if sbom.get("bomFormat") != "CycloneDX" or not isinstance(sbom.get("components"), list):
        raise ValueError("Incomplete CycloneDX SBOM")
    scanner = read(folder / receipt["files"]["scanner"]["filename"])
    if (scanner.get("Version") != receipt["scanner"].get("version")
            or not scanner.get("VulnerabilityDB")):
        raise ValueError("Scanner version or vulnerability database evidence differs")
    # Registry access is anonymous, even when called from a publisher/PR job.
    with tempfile.TemporaryDirectory(prefix="xorder-public-cosign-") as config:
        env = anonymous_registry_environment(config)
        run("cosign", "verify", "--certificate-identity", IDENTITY,
            "--certificate-oidc-issuer", ISSUER, receipt["artifact"], env=env)
        verify_attestation(receipt["artifact"], "cyclonedx", sbom, env)
        verify_attestation(receipt["artifact"], PREDICATE, receipt, env)
    return receipt


def create(artifact, source, evidence, folder):
    if not IMAGE.fullmatch(artifact) or not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Assurance requires a published exact image digest and source commit")
    if "https://github.com/" + os.environ.get("GITHUB_WORKFLOW_REF", "") != IDENTITY:
        raise ValueError("Signing is only permitted from xorder's master publication workflow")
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    with tempfile.TemporaryDirectory(prefix="xorder-public-trivy-") as config:
        env = anonymous_registry_environment(config)
        scanner_config = Path(config) / "trivy-empty.yaml"
        scanner_config.write_text("{}\n")
        scanner_ignore = Path(config) / "trivy-empty.ignore"
        scanner_ignore.write_text("")
        for name, arguments in (
            ("vulnerabilities", ["image", "--image-src", "remote", "--platform", "linux/amd64",
                                 "--scanners", "vuln", "--format", "json"]),
            ("sbom", ["image", "--image-src", "remote", "--platform", "linux/amd64", "--format", "cyclonedx"]),
        ):
            path = folder / (name + ".json")
            run("trivy", "--config", str(scanner_config), *arguments, "--ignorefile", str(scanner_ignore),
                "--output", str(path), artifact, env=env)
            digest = sha256(path)
            final = folder / (name + "-" + digest + ".json")
            path.rename(final)
            files[name] = {"filename": final.name, "sha256": digest}
        scanner = run("trivy", "--config", str(scanner_config), "version", "--format", "json", env=env)
    value = json.loads(scanner)
    if value.get("Version") != TRIVY["version"] or not value.get("VulnerabilityDB"):
        raise ValueError("Unexpected scanner version or missing vulnerability database observation")
    path = folder / "scanner.json"
    path.write_text(scanner)
    digest = sha256(path)
    final = folder / ("scanner-" + digest + ".json")
    path.rename(final)
    files["scanner"] = {"filename": final.name, "sha256": digest}
    summary = scan_summary(read(folder / files["vulnerabilities"]["filename"]))
    receipt = {"schema_version": 1, "artifact": artifact, "source_commit": source,
               "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
               "evidence": evidence, "assurance_workflow_commit": os.environ.get("GITHUB_SHA"), "certificate_identity": IDENTITY,
               "certificate_oidc_issuer": ISSUER, "predicate_type": PREDICATE,
               "scanner": {"name": "trivy", **TRIVY}, "scan": summary, "files": files}
    (folder / "assurance.json").write_text(encoded(receipt))
    if summary["status"] != "passed":
        raise RuntimeError("Release scan blocked: fixable CRITICAL vulnerabilities; inspect assurance.json and vulnerability evidence")
    validate_receipt(receipt, artifact, source)
    run("cosign", "sign", "--yes", artifact)
    run("cosign", "attest", "--yes", "--type", "cyclonedx", "--predicate",
        str(folder / files["sbom"]["filename"]), artifact)
    run("cosign", "attest", "--yes", "--type", PREDICATE, "--predicate", str(folder / "assurance.json"), artifact)
    return verify_local(receipt, folder)


def receipt_link(receipt, source_tag, folder):
    return {"receipt_url": f"https://github.com/xormania/xorder/releases/download/{urllib.parse.quote(source_tag, safe='')}/assurance.json",
            "receipt_sha256": sha256(folder / "assurance.json"), "predicate_type": PREDICATE}


def verify_published(publication, expected_image, folder):
    if publication["artifact"] != expected_image or not IMAGE.fullmatch(expected_image):
        raise ValueError("Published assurance does not identify the consumer's pinned image")
    summary = publication["assurance"]
    parsed = urllib.parse.urlsplit(summary["receipt_url"])
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
            or not parsed.path.startswith("/xormania/xorder/releases/download/")
            or not parsed.path.endswith("/assurance.json") or summary["predicate_type"] != PREDICATE):
        raise ValueError("Assurance evidence is outside xorder's public Releases")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "assurance.json"
    download(summary["receipt_url"], path, summary["receipt_sha256"])
    receipt = validate_receipt(read(path), expected_image, publication["source_commit"])
    for facts in receipt["files"].values():
        download(summary["receipt_url"].rsplit("/", 1)[0] + "/" + facts["filename"], folder / facts["filename"], facts["sha256"])
    return verify_local(receipt, folder)


def smoke_record(base):
    """Select one accepted small image only when the assurance delivery path changes."""
    from library import records, version
    changed = subprocess.check_output(["git", "diff", "--name-only", base, "HEAD", "--",
                                       ".github/workflows/publish.yml", "scripts/image_assurance.py",
                                       "scripts/release.py"], cwd=ROOT, text=True).splitlines()
    if not changed:
        return ""
    candidates = [record for record in records() if record["line_id"] == "python-dev/3.14-trixie"
                  and record["lifecycle"] == "available"]
    if not candidates:
        raise ValueError("Assurance smoke needs an accepted python-dev public digest")
    record = max(candidates, key=lambda item: version(item["version"]))
    return f"release-records/{record['line_id']}/{record['version']}.json"


def assure_existing(record_path, folder):
    """Publish newly observed assurance separately from immutable historical facts."""
    from registry import resolve
    from release import stage_assurance
    path = record_path.resolve()
    if not path.is_relative_to(ROOT / "release-records") or path.is_relative_to(ROOT / "release-records/artifacts"):
        raise ValueError("Assurance-only publication requires a committed image release record")
    record = validate_record(read(path))
    folder.mkdir(parents=True, exist_ok=True)
    artifact = record["publication"]["repository"] + "@" + record["publication"]["digest"]
    resolved = resolve(artifact)
    if not resolved or resolved["digest"] != record["publication"]["digest"]:
        raise ValueError("The recorded exact digest is no longer publicly accessible")
    tag = f"image-assurance/{record['line_id']}/v{record['version']}/{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    evidence = f"https://github.com/xormania/xorder/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    summary = stage_assurance(tag, record["source_commit"], artifact, evidence, folder / "assurance")
    run("gh", "release", "edit", tag, "--draft=false", "--notes",
        f"New image scan, SBOM and keyless signatures for {artifact}. Original image source: {record['source_commit']}. "
        "This evidence does not repeat behavior tests or replace the historical release record.")
    publication = {"artifact": artifact, "source_commit": record["source_commit"], "assurance": summary}
    verify_published(publication, artifact, folder / "public-assurance")
    (folder / "assurance-publication.json").write_text(encoded(publication))
    return publication


def verify_record(record, folder):
    assurance = record.get("assurance")
    if not assurance:
        raise ValueError("This historical release has no recorded image assurance; select an assured release or explicitly retain the existing pin")
    expected_url = f"https://github.com/xormania/xorder/releases/download/{urllib.parse.quote(record['source_tag'], safe='')}/assurance.json"
    if assurance["receipt_url"] != expected_url:
        raise ValueError("Assurance receipt is outside the expected source Release")
    return verify_published({"artifact": record["publication"]["repository"] + "@" + record["publication"]["digest"],
                             "source_commit": record["source_commit"], "assurance": assurance},
                            record["publication"]["repository"] + "@" + record["publication"]["digest"], folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    install = commands.add_parser("install-scanner")
    install.add_argument("--directory", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("record", type=Path)
    check.add_argument("--output", type=Path, required=True)
    existing = commands.add_parser("assure-existing")
    existing.add_argument("record", type=Path)
    existing.add_argument("--output", type=Path, required=True)
    published = commands.add_parser("verify-publication")
    published.add_argument("publication", type=Path)
    published.add_argument("--image", required=True)
    published.add_argument("--output", type=Path, required=True)
    smoke = commands.add_parser("smoke-record")
    smoke.add_argument("--base", required=True)
    args = parser.parse_args()
    if args.action == "install-scanner":
        print(install_scanner(args.directory))
    elif args.action == "smoke-record":
        print("assurance_smoke_record=" + smoke_record(args.base))
    elif args.action == "assure-existing":
        print(encoded(assure_existing(args.record, args.output)))
    else:
        receipt = (verify_published(read(args.publication), args.image, args.output)
                   if args.action == "verify-publication" else verify_record(read(args.record), args.output))
        print(encoded({"status": "verified", "artifact": receipt["artifact"], "scan": receipt["scan"], "evidence": receipt["evidence"]}))
