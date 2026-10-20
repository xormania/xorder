"""Behavior checks for persistent, explicit harness version management."""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("harnesses", Path(__file__).resolve().parents[1] / "images/harness-live/harnesses.py")
harnesses = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harnesses)


class HarnessManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "installs"
        self.pins = Path(self.temporary.name) / "pins.json"
        self.pins.write_text(json.dumps({"harnesses": {name: {"version": "1.0.0"} for name in harnesses.NAMES}}))
        self.manager = harnesses.Manager(self.root, self.pins)

    def installed(self, name, version, extra=False):
        directory = self.manager.installation(name, version)
        (directory / "bin").mkdir(parents=True)
        executable = directory / "bin" / name
        executable.write_text("#!/bin/sh\nprintf '%s\\n' '" + version + "'\n")
        executable.chmod(0o755)
        if extra:
            (directory / "dependency").write_text("original native runtime")
        receipt = {"schema_version": 1, "name": name, "version": version,
                   "executable": "bin/" + name, "version_output": version,
                   "sha256": harnesses.sha256(executable), "files": harnesses.file_hashes(directory)}
        harnesses.atomic_json(directory / "receipt.json", receipt)
        return executable

    def test_status_on_absent_root_is_read_only(self):
        self.assertEqual(self.manager.status(harnesses.NAMES)["harnesses"]["codex"], {"status": "not_installed"})
        self.assertFalse(self.root.exists())

    def test_exact_versions_reject_paths_channels_and_shell_fragments(self):
        for value in ("../1.2.3", "latest", "1.2.3/../evil", "1.2.3;echo bad", "--help", "1.2.3\n", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manager.installation("codex", value)
        self.assertEqual(harnesses.version("1.2.3-alpha.4"), "1.2.3-alpha.4")
        with self.assertRaises(ValueError):
            self.manager.installation("../codex", "1.2.3")

    def test_install_environment_excludes_credentials_and_real_home(self):
        with patch.dict(os.environ, {"HOME": "/real/home", "ANTHROPIC_API_KEY": "secret",
                                    "OPENAI_API_KEY": "secret", "XAI_API_KEY": "secret",
                                    "GROK_DEPLOYMENT_KEY": "secret", "AWS_ACCESS_KEY_ID": "secret",
                                    "NODE_EXTRA_CA_CERTS": "/public/ca.pem", "HTTPS_PROXY": "http://proxy"}):
            env = harnesses.isolated_environment(Path("/temporary/home"))
        self.assertEqual(env["HOME"], "/temporary/home")
        self.assertFalse(any("KEY" in name for name in env))
        self.assertEqual(env["NODE_EXTRA_CA_CERTS"], "/public/ca.pem")
        self.assertEqual(env["HTTPS_PROXY"], "http://proxy")
        self.assertNotEqual(env["npm_config_userconfig"], env["npm_config_globalconfig"])

    def test_failure_during_new_install_preserves_selection_and_cleans_stage(self):
        self.installed("codex", "1.0.0")
        self.manager.activate("codex", "1.0.0")
        with patch.object(harnesses, "run", side_effect=ValueError("download failed")):
            with self.manager.locked(), self.assertRaisesRegex(ValueError, "download failed"):
                self.manager.install("codex", "2.0.0")
        self.assertEqual(self.manager.state()["harnesses"]["codex"]["version"], "1.0.0")
        self.assertFalse(self.manager.installation("codex", "2.0.0").exists())
        self.assertEqual(list((self.root / "versions/codex").glob(".install-*")), [])

    def test_new_selection_keeps_old_executable_and_rollback_is_offline(self):
        old = self.installed("grok", "1.0.0")
        new = self.installed("grok", "2.0.0")
        self.manager.activate("grok", "1.0.0")
        running_session = self.manager.receipt("grok", "1.0.0")[1]
        self.manager.activate("grok", "2.0.0")
        self.assertEqual(subprocess.check_output([str(running_session)], text=True).strip(), "1.0.0")
        self.assertEqual(subprocess.check_output([str(new)], text=True).strip(), "2.0.0")
        with patch.object(harnesses, "fetch", side_effect=AssertionError("network on rollback")):
            self.manager.rollback("grok")
        self.assertEqual(self.manager.state()["harnesses"]["grok"]["version"], "1.0.0")
        self.assertTrue(old.exists())
        self.assertTrue(new.exists())

    def test_ensure_preserves_explicit_upgrade_and_reuses_offline(self):
        self.installed("claude", "2.0.0")
        self.manager.activate("claude", "2.0.0")
        before = (self.root / "selected.json").read_bytes()
        with patch.object(self.manager, "install", side_effect=AssertionError("reinstall")):
            self.manager.ensure(["claude"])
        self.assertEqual((self.root / "selected.json").read_bytes(), before)
        self.assertEqual(self.manager.status(["claude"])["harnesses"]["claude"]["version"], "2.0.0")

    def test_native_dependency_changes_are_detected_beyond_launcher(self):
        self.installed("codex", "1.0.0", extra=True)
        self.manager.activate("codex", "1.0.0")
        (self.manager.installation("codex", "1.0.0") / "dependency").write_text("unexpected runtime")
        self.assertEqual(self.manager.status(["codex"])["harnesses"]["codex"]["integrity"], "failed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.manager.ensure(["codex"])
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.manager.rollback("codex", "1.0.0")

    def test_executable_permission_loss_fails_status_ensure_and_launch(self):
        executable = self.installed("grok", "1.0.0")
        self.manager.activate("grok", "1.0.0")
        executable.chmod(0o644)
        self.assertEqual(self.manager.status(["grok"])["harnesses"]["grok"]["integrity"], "failed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.manager.ensure(["grok"])
        with patch.object(os, "execve") as execute, self.assertRaisesRegex(ValueError, "permissions changed"):
            self.manager.execute("grok", ["--version"])
        execute.assert_not_called()

    def test_directory_traversal_or_setuid_permission_changes_are_detected(self):
        executable = self.installed("grok", "1.0.0")
        self.manager.activate("grok", "1.0.0")
        executable.chmod(0o4755)
        self.assertEqual(self.manager.status(["grok"])["harnesses"]["grok"]["integrity"], "failed")
        executable.chmod(0o755)
        directory = executable.parent
        original_mode = directory.stat().st_mode & 0o7777
        directory.chmod(0o644)
        try:
            self.assertEqual(self.manager.status(["grok"])["harnesses"]["grok"]["integrity"], "failed")
        finally:
            directory.chmod(original_mode)

    def test_version_directory_mode_is_part_of_integrity(self):
        self.installed("grok", "1.0.0")
        self.manager.activate("grok", "1.0.0")
        directory = self.manager.installation("grok", "1.0.0")
        before = directory.stat().st_mode & 0o7777
        directory.chmod(before ^ 0o1000)
        self.assertEqual(self.manager.status(["grok"])["harnesses"]["grok"]["integrity"], "failed")

    def test_receipt_executable_cannot_escape_installation(self):
        self.installed("grok", "1.0.0")
        directory = self.manager.installation("grok", "1.0.0")
        receipt = json.loads((directory / "receipt.json").read_text())
        receipt["executable"] = "/bin/sh"
        harnesses.atomic_json(directory / "receipt.json", receipt)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.manager.receipt("grok", "1.0.0")

    def test_version_directory_symlink_is_rejected(self):
        external = Path(self.temporary.name) / "elsewhere"
        external.mkdir()
        directory = self.manager.installation("codex", "1.0.0")
        directory.parent.mkdir(parents=True)
        directory.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.manager.receipt("codex", "1.0.0")

    def test_cli_execution_resolves_selected_binary_and_disables_updaters(self):
        executable = self.installed("codex", "1.0.0")
        self.manager.activate("codex", "1.0.0")
        with patch.object(os, "execve") as execute:
            self.manager.execute("codex", ["--version"])
        path, command, env = execute.call_args.args
        self.assertEqual(path, str(executable.resolve()))
        self.assertEqual(command, [path, "-c", "check_for_update_on_startup=false", "--version"])
        self.assertEqual(env["DISABLE_UPDATES"], "1")
        self.assertEqual(env["GROK_DISABLE_AUTOUPDATER"], "1")

    def test_initializers_serialize_and_install_once(self):
        self.installed("grok", "1.0.0")
        events = Path(self.temporary.name) / "events"
        # Fork inherits this fixture; locks must work across OS processes.
        def worker():
            manager = harnesses.Manager(self.root, self.pins)
            with manager.locked():
                if not manager.state()["harnesses"].get("grok"):
                    with events.open("a") as stream:
                        stream.write("installed\n")
                    time.sleep(0.05)
                    manager.activate("grok", "1.0.0")
        processes = [multiprocessing.get_context("fork").Process(target=worker) for _ in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(3)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(events.read_text().splitlines(), ["installed"])

    def test_probe_rejects_changed_version_before_activation(self):
        with patch.object(harnesses, "run", return_value=subprocess.CompletedProcess([], 0, "codex-cli 9.9.9\n", "")):
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                harnesses.probe("codex", Path("/not-executed"), "1.0.0", {})


if __name__ == "__main__":
    unittest.main()
