"""Source-only pending application builds cannot become publication evidence."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build
import browser_release


class ParityApplicationTests(unittest.TestCase):
    def setUp(self):
        self.source = "c" * 40
        self.line = "uxor-dev/8.5-trixie"
        self.image_id = "sha256:" + "a" * 64
        self.fixture = {"repository": "https://github.com/xormania/uxor.git", "commit": "d" * 40,
                        "playwright_version": "1.58.2",
                        "application_resource": {"id": "image/" + self.line, "version": "1.0.0"}}
        self.defs = {"php-frankenphp/8.5-trixie": {"family": "php-frankenphp", "revision": "1.1.1", "base": {}},
                     self.line: {"family": "uxor-dev", "revision": "1.0.0", "base": {"parent": "php-frankenphp/8.5-trixie"}}}
        self.facts = {"Id": self.image_id, "Config": {"Labels": {
            "org.opencontainers.image.revision": self.source, "org.opencontainers.image.version": "1.0.0"}}}

    def test_accepted_exact_application_needs_no_local_build(self):
        entry = {"id": "image/" + self.line, "version": "1.0.0", "lifecycle": "available",
                 "verification": {"status": "passed"}, "targets": ["linux/amd64"],
                 "identity": "ghcr.io/xormania/uxor-dev@" + self.image_id}
        with patch.object(build, "read", return_value={"resources": [entry]}), \
                patch("playwright_fixture.inputs") as resolve, patch.object(build, "validate_tree") as execute:
            self.assertIsNone(build.prepare_parity_application(self.fixture, self.source))
            resolve.assert_called_once()
            execute.assert_not_called()

    def test_pending_app_uses_only_its_exact_prerequisite_and_verified_local_identity(self):
        parent = "ghcr.io/xormania/php-frankenphp@sha256:" + "b" * 64
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(build, "ROOT", Path(temporary)), \
                patch.object(build, "read", return_value={"resources": []}), \
                patch.object(build, "definitions", return_value=self.defs), \
                patch.object(build, "reusable_artifact", side_effect=[parent, None]), \
                patch.object(build, "build") as construct, patch.object(build, "verify") as runtime, \
                patch.object(build, "inspect") as inventory, \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}), \
                patch.object(build.subprocess, "run") as docker, \
                patch.object(build, "image_facts", return_value=self.facts):
            result = build.prepare_parity_application(self.fixture, self.source)
            self.assertEqual(result, self.image_id)
            docker.assert_called_once_with(["docker", "pull", "--platform", "linux/amd64", parent], check=True)
            construct.assert_called_once_with(self.line, "image-library-check:uxor-dev", self.source, parent, None)
            runtime.assert_not_called()
            inventory.assert_called_once_with(self.line, self.image_id,
                Path(temporary) / "out/parity-application/uxor-dev-8.5-trixie/uxor-dev.json")

    def test_unavailable_known_record_is_not_treated_as_a_pending_definition(self):
        entry = {"id": "image/" + self.line, "version": "1.0.0", "lifecycle": "withdrawn",
                 "verification": {"status": "passed"}, "targets": ["linux/amd64"]}
        with patch.object(build, "read", return_value={"resources": [entry]}), \
                patch.object(build, "validate_tree") as execute, self.assertRaisesRegex(ValueError, "not available"):
            build.prepare_parity_application(self.fixture, self.source)
        execute.assert_not_called()

    def test_wrong_revision_or_local_source_fails_without_authorizing_parity(self):
        with patch.object(build, "read", return_value={"resources": []}), \
                patch.object(build, "definitions", return_value=self.defs), patch.object(build, "validate_tree") as execute:
            fixture = copy.deepcopy(self.fixture)
            fixture["application_resource"]["version"] = "1.0.1"
            with self.assertRaisesRegex(ValueError, "exact authored"):
                build.prepare_parity_application(fixture, self.source)
            execute.assert_not_called()
            facts = copy.deepcopy(self.facts)
            facts["Config"]["Labels"]["org.opencontainers.image.revision"] = "e" * 40
            with patch.object(build, "image_facts", return_value=facts), self.assertRaisesRegex(ValueError, "validating source"):
                build.prepare_parity_application(self.fixture, self.source)

    def test_source_mode_scopes_override_and_publication_rejects_it(self):
        browser_line = "playwright-browser/1.58-trixie"
        with patch.object(build, "definitions", return_value={browser_line: {"family": "playwright-browser"}}), \
                patch.object(build, "read", return_value=self.fixture), \
                patch.object(build, "prepare_parity_application", return_value=self.image_id), \
                patch.object(build, "inspect"), patch.object(build.subprocess, "run") as run:
            build.verify(browser_line, "browser:test", Path("out/inventory.json"), source_validation=True, source=self.source)
            self.assertEqual(run.call_args.kwargs["env"]["XORDER_PARITY_LOCAL_APPLICATION"], self.image_id)
            with patch.dict(os.environ, {"XORDER_PARITY_LOCAL_APPLICATION": "stale"}):
                build.prepare_parity_application.return_value = None
                build.verify(browser_line, "browser:test", Path("out/inventory.json"), source_validation=True, source=self.source)
                self.assertNotIn("XORDER_PARITY_LOCAL_APPLICATION", run.call_args.kwargs["env"])
        candidate = {"line": browser_line, "version": "1.0.2", "input_fingerprint": "f", "fixture_sha256": "g", "artifact": "browser:test"}
        definition = {"family": "playwright-browser", "revision": "1.0.2"}
        with patch.object(browser_release, "read", return_value=candidate), \
                patch.object(browser_release, "definitions", return_value={browser_line: definition}), \
                patch.object(browser_release, "fingerprint", return_value="f"), \
                patch.object(browser_release, "fixture_hash", return_value="g"), \
                patch.dict(os.environ, {"XORDER_PARITY_LOCAL_APPLICATION": self.image_id}, clear=True), \
                patch.object(browser_release.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "source-validation only"):
                browser_release.verify_candidate(Path("candidate.json"), Path("verified.json"))
            docker.assert_not_called()

    def test_publication_waits_for_accepted_application_even_without_an_override(self):
        line = "playwright-browser/1.58-trixie"
        candidate = {"line": line, "version": "1.0.2", "input_fingerprint": "f", "fixture_sha256": "g", "artifact": "browser:test"}
        definition = {"family": "playwright-browser", "revision": "1.0.2"}
        with patch.object(browser_release, "read", return_value=candidate), \
                patch.object(browser_release, "definitions", return_value={line: definition}), \
                patch.object(browser_release, "fingerprint", return_value="f"), \
                patch.object(browser_release, "fixture_hash", return_value="g"), \
                patch.object(browser_release, "public_parity_application", side_effect=ValueError("Application not accepted")), \
                patch.dict(os.environ, {}, clear=True), patch.object(browser_release.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "not accepted"):
                browser_release.verify_candidate(Path("candidate.json"), Path("verified.json"))
            docker.assert_not_called()
