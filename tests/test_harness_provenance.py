"""Verify real vendor signatures and reject tampering before native execution."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/harness-live/provenance"
SPEC = importlib.util.spec_from_file_location("harness_provenance", ROOT / "images/harness-live/provenance.py")
provenance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provenance)


def crypto_run(command, *, env, timeout=30, check=True, **kwargs):
    result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise ValueError("Signature verification failed: " + result.stderr)
    return result


class HarnessProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)
        (self.stage / "bin").mkdir()
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.stage)}
        self.metadata = json.loads((FIXTURE / "grok-metadata.json").read_text())

    def claude_fetch(self, url, destination, env):
        if url.endswith("manifest.json"):
            shutil.copyfile(FIXTURE / "claude-manifest.json", destination)
        elif url.endswith("manifest.json.sig"):
            shutil.copyfile(FIXTURE / "claude-manifest.json.sig", destination)
        else:
            raise AssertionError("Unexpected binary fetch before verification: " + url)

    @unittest.skipUnless(Path(provenance.GPGV).exists(), "gpgv is required for vendor signature verification")
    def test_real_claude_manifest_signature_uses_pinned_key(self):
        value = provenance.verify_claude_manifest(
            FIXTURE / "claude-manifest.json", FIXTURE / "claude-manifest.json.sig",
            self.stage, self.env, crypto_run)
        self.assertEqual(value["version"], "2.1.302")
        self.assertEqual(value["platforms"]["linux-x64"]["checksum"],
                         "60d7eb7f12fbb28a52533fe8be5884097403562aa02dc73991a021c7067e29a5")

    @unittest.skipUnless(Path(provenance.GPGV).exists(), "gpgv is required for vendor signature verification")
    def test_tampered_claude_manifest_never_reaches_binary_download(self):
        def fetch(url, destination, env):
            self.claude_fetch(url, destination, env)
            if url.endswith("manifest.json"):
                value = json.loads(destination.read_text())
                value["platforms"]["linux-x64"]["checksum"] = "0" * 64
                destination.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "Signature verification failed"):
            provenance.install_native("claude", "2.1.302", self.stage, self.env, fetch, crypto_run)
        self.assertFalse((self.stage / "bin/claude").exists())

    @unittest.skipUnless(Path(provenance.GPGV).exists(), "gpgv is required for vendor signature verification")
    def test_signed_claude_manifest_cannot_substitute_another_version(self):
        with self.assertRaisesRegex(ValueError, "requested release"):
            provenance.install_native("claude", "2.1.303", self.stage, self.env, self.claude_fetch, crypto_run)

    @unittest.skipUnless(Path(provenance.GPGV).exists(), "gpgv is required for vendor signature verification")
    def test_claude_payload_mismatch_is_rejected_before_execution(self):
        calls = []
        def fetch(url, destination, env):
            if url.endswith("/linux-x64/claude"):
                destination.write_bytes(b"untrusted executable")
            else:
                self.claude_fetch(url, destination, env)
        def run(command, **kwargs):
            calls.append(command[0])
            return crypto_run(command, **kwargs)
        with self.assertRaisesRegex(ValueError, "signed release identity"):
            provenance.install_native("claude", "2.1.302", self.stage, self.env, fetch, run)
        self.assertEqual(calls, [provenance.GPGV])

    @unittest.skipUnless(Path(provenance.OPENSSL).exists(), "OpenSSL is required for registry verification")
    def test_real_grok_metadata_signature_authenticates_sri(self):
        expected = provenance.verify_npm_metadata(self.metadata, "@xai-official/grok-linux-x64", "1.0.62",
                                                  self.stage, self.env, crypto_run)
        self.assertEqual(expected, base64.b64decode(self.metadata["dist"]["integrity"].split("-", 1)[1]))

    @unittest.skipUnless(Path(provenance.OPENSSL).exists(), "OpenSSL is required for registry verification")
    def test_tampered_grok_integrity_has_no_valid_signature(self):
        self.metadata["dist"]["integrity"] = "sha512-" + base64.b64encode(b"x" * 64).decode()
        with self.assertRaisesRegex(ValueError, "no valid signature"):
            provenance.verify_npm_metadata(self.metadata, "@xai-official/grok-linux-x64", "1.0.62",
                                           self.stage, self.env, crypto_run)

    def test_grok_signature_is_bound_to_exact_name_and_version(self):
        for name, version in (("@other/grok-linux-x64", "1.0.62"),
                              ("@xai-official/grok-linux-x64", "1.0.63")):
            with self.subTest(name=name, version=version), self.assertRaisesRegex(ValueError, "identity"):
                provenance.verify_npm_metadata(self.metadata, name, version, self.stage, self.env,
                                               lambda *args, **kwargs: self.fail("Crypto need not run for wrong identity"))

    def test_downloaded_metadata_cannot_add_a_trust_key(self):
        self.metadata["dist"]["signatures"] = [{"keyid": "attacker-key", "sig": "AA=="}]
        self.metadata["keys"] = [{"keyid": "attacker-key", "key": "attacker-key"}]
        with self.assertRaisesRegex(ValueError, "no valid signature"):
            provenance.verify_npm_metadata(self.metadata, "@xai-official/grok-linux-x64", "1.0.62",
                                           self.stage, self.env,
                                           lambda *args, **kwargs: self.fail("Unknown key must not be used"))

    @unittest.skipUnless(Path(provenance.OPENSSL).exists(), "OpenSSL is required for registry verification")
    def test_grok_payload_mismatch_is_rejected_before_extraction_or_execution(self):
        calls = []
        def fetch(url, destination, env):
            if url.endswith(".tgz"):
                destination.write_bytes(b"untrusted archive")
            else:
                destination.write_text(json.dumps(self.metadata))
        def run(command, **kwargs):
            calls.append(command[0])
            return crypto_run(command, **kwargs)
        with self.assertRaisesRegex(ValueError, "signed release identity"):
            provenance.install_native("grok", "1.0.62", self.stage, self.env, fetch, run)
        self.assertNotIn(provenance.NODE, calls)
        self.assertFalse((self.stage / "bin/grok").exists())

    def test_grok_package_cannot_install_a_symlink_as_its_binary(self):
        archive = self.stage / "attack.tgz"
        with tarfile.open(archive, "w:gz") as stream:
            member = tarfile.TarInfo("package/bin/grok.br")
            member.type = tarfile.SYMTYPE
            member.linkname = "/outside/operator-secrets"
            stream.addfile(member)
        expected = hashlib.sha512(archive.read_bytes()).digest()
        def fetch(url, destination, env):
            if url.endswith(".tgz"):
                shutil.copyfile(archive, destination)
            else:
                destination.write_text(json.dumps(self.metadata))
        with patch.object(provenance, "verify_npm_metadata", return_value=expected):
            with self.assertRaisesRegex(ValueError, "regular binary payload"):
                provenance.install_native("grok", "1.0.62", self.stage, self.env, fetch,
                                          lambda *args, **kwargs: self.fail("Symlink payload must not execute"))


if __name__ == "__main__":
    unittest.main()
