"""Legacy application preparation is explicit and separate from image readiness."""
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build
from library import ROOT


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

    def test_browser_readiness_never_prepares_an_application_or_propagates_overrides(self):
        browser_line = "playwright-browser/1.58-trixie"
        with patch.object(build, "definitions", return_value={browser_line: {"family": "playwright-browser"}}), \
                patch.object(build, "prepare_parity_application") as prepare, \
                patch.object(build, "read", side_effect=AssertionError("Image readiness must not read consumer pins")), \
                patch.object(build, "inspect"), patch.object(build.subprocess, "run") as run, \
                patch.dict(os.environ, {"XORDER_PARITY_LOCAL_APPLICATION": self.image_id,
                                        "XORDER_SOURCE_VALIDATION_PROOF": "/stale/proof.json"}):
            build.verify(browser_line, "browser:test", Path("out/inventory.json"), source_validation=True, source=self.source)
            prepare.assert_not_called()
            self.assertNotIn("XORDER_PARITY_LOCAL_APPLICATION", run.call_args.kwargs["env"])
            self.assertNotIn("XORDER_SOURCE_VALIDATION_PROOF", run.call_args.kwargs["env"])

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
