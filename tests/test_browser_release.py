"""Anonymous browser verification and exact evidence binding before publication."""
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import quote
import tempfile
import unittest
from unittest.mock import patch

from test_library import record
from library import ROOT, definitions, encoded, fingerprint
import browser_release
import release


class BrowserReleaseTests(unittest.TestCase):
    line = "playwright-browser/1.58-trixie"
    source = "c" * 40
    artifact = "ghcr.io/xormania/playwright-browser@sha256:" + "d" * 64

    def proposal(self):
        return {"line": self.line, "source": self.source, "artifact": self.artifact,
                "version": definitions()[self.line]["revision"],
                "input_fingerprint": fingerprint(definitions()[self.line]),
                "fixture_sha256": browser_release.fixture_hash(self.line)}

    def test_staging_never_executes_consumers_and_anonymous_verification_binds_the_digest(self):
        inventory = record(self.line)["platforms"][0]["inventory"]
        inventory["runtime_version"] = "1.58.2"
        def verify(_line, _image, output):
            output.write_text(encoded(inventory))
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), \
                patch("release.release_asset", return_value=None), \
                patch.object(browser_release, "resolve", side_effect=[None, None, {"digest": "sha256:" + "d" * 64}, {"digest": "sha256:" + "d" * 64}]), \
                patch.object(browser_release, "build") as build, \
                patch.object(browser_release.subprocess, "run") as docker, \
                patch.object(browser_release, "public_parity_application", return_value=("https://github.com/xormania/uxor.git", "a" * 40, "1.58.2", "ghcr.io/xormania/uxor-dev@sha256:" + "b" * 64)), \
                patch.object(browser_release, "verify", side_effect=verify) as consumer:
            candidate, evidence = Path(folder) / "candidate.json", Path(folder) / "verified.json"
            browser_release.stage(self.line, self.source, candidate)
            build.assert_called_once()
            consumer.assert_not_called()
            browser_release.verify_candidate(candidate, evidence)
            consumer.assert_called_once_with(self.line, self.artifact, evidence.with_suffix(".inventory.json"))
            proof = browser_release.accepted_evidence(self.line, self.source, self.artifact, evidence)
            self.assertEqual(proof["status"], "passed")
            self.assertEqual(proof["inventory"], inventory)
            self.assertTrue(any(call.args[0][:2] == ["docker", "push"] for call in docker.call_args_list))

    def test_changed_digest_source_fixture_or_status_cannot_authorize_publication(self):
        proof = dict(self.proposal(), status="passed", verification_seconds=2)
        changes = {"artifact": self.artifact.replace("d" * 64, "e" * 64), "source": "e" * 40,
                   "fixture_sha256": "e" * 64, "status": "failed"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "proof.json"
            for key, value in changes.items():
                path.write_text(json.dumps(dict(proof, **{key: value})))
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "exact publication inputs"):
                    browser_release.accepted_evidence(self.line, self.source, self.artifact, path)

    def test_verification_refuses_publication_credentials_before_starting_docker(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"GH_TOKEN": "test-only-token"}), \
                patch.object(browser_release.subprocess, "run") as docker:
            path = Path(folder) / "candidate.json"
            path.write_text(json.dumps(self.proposal()))
            with self.assertRaisesRegex(ValueError, "without GitHub publication credentials"):
                browser_release.verify_candidate(path, Path(folder) / "proof.json")
            docker.assert_not_called()

    def test_credentialed_finalization_uses_bound_evidence_without_rebuilding_or_running_consumers(self):
        inventory = record(self.line)["platforms"][0]["inventory"]
        inventory["runtime_version"] = "1.58.2"
        proof = dict(self.proposal(), status="passed", inventory=inventory, verification_seconds=7,
                     completed_at="2026-10-10T19:00:00Z", build_seconds=11, cache_source="empty")
        digest = self.artifact.split("@", 1)[1]
        resolved = {"digest": digest, "platforms": {"linux/amd64": digest}}
        labels = {"org.opencontainers.image.revision": self.source,
                  "org.opencontainers.image.version": proof["version"]}
        facts = {"image_size_bytes": 629145600, "size_method": "docker-image-inspect-size", "image_store": "overlay2/classic"}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(release, "records", return_value=[]), \
                patch.object(release, "release_asset", return_value=None), \
                patch.object(release, "resolve", side_effect=[None, resolved, resolved, resolved]), \
                patch.object(release, "verify") as consumer, patch.object(release, "build") as build, \
                patch.object(release, "image_measurements", return_value=facts), \
                patch.object(release, "run"), patch.object(release, "gh", return_value="[[]]"), \
                patch.object(release.subprocess, "check_output", side_effect=lambda args, **kw: json.dumps(labels) if args[0] == "docker" else ""), \
                patch.object(release, "promote_exact"), patch.object(release, "finalize_release"), \
                patch.object(release, "stage_assurance", return_value={"receipt_url": "https://github.com/xormania/xorder/releases/download/" + quote(self.line + "/v" + proof["version"], safe="") + "/assurance.json", "receipt_sha256": "a" * 64, "predicate_type": "https://github.com/xormania/xorder/assurance/v1"}), \
                patch("image_assurance.verify_record"), \
                patch.object(browser_release, "public_parity_application", return_value=("https://github.com/xormania/uxor.git", "a" * 40, "1.58.2", "ghcr.io/xormania/uxor-dev@sha256:" + "b" * 64)), \
                patch.dict(os.environ, {"GH_TOKEN": "test-only-token", "GITHUB_REPOSITORY": "xormania/xorder", "GITHUB_RUN_ID": "42"}):
            evidence = Path(folder) / "proof.json"
            evidence.write_text(encoded(proof))
            published = release.publish(self.line, self.source, Path(folder) / "release", browser_evidence=evidence)
            consumer.assert_not_called()
            build.assert_not_called()
            self.assertEqual(published["verification"]["completed_at"], proof["completed_at"])
            self.assertEqual(published["platforms"][0]["metrics"]["verification_seconds"], 7)
            self.assertEqual(published["platforms"][0]["metrics"]["build_seconds"], 11)

    def test_controlled_compose_ignores_consumer_infrastructure_and_rejects_host_symlinks(self):
        spec = importlib.util.spec_from_file_location("parity_profile", ROOT / "examples/uxor/runner.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder) / "checkout"
            for name in ("Caddyfile", "conf.d/10-app.ini", "conf.d/20-app.dev.ini"):
                path = workspace / "demo/frankenphp" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            command = runner.compose_command(workspace, "parity", {"XORDER_PARITY_FIXTURE": "1"})
            self.assertNotIn(str(workspace / "demo/compose.yaml"), command)
            self.assertNotIn(str(workspace / "demo/compose.override.yaml"), command)
            self.assertEqual(command[command.index("--env-file") + 1], os.devnull)
            target = workspace / "demo/frankenphp/Caddyfile"
            target.unlink()
            outside = Path(folder) / "host-config"
            outside.touch()
            target.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "disposable consumer checkout"):
                runner.compose_command(workspace, "parity", {"XORDER_PARITY_FIXTURE": "1"})
