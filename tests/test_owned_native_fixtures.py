"""Capability fixtures must reject real operation and provenance failures."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load("owned_native_runtime", "tests/fixtures/native-runtime/check.py")
harness = load("owned_harness_fixture", "tests/fixtures/harness-live/check.py")
matrix = load("owned_matrix_fixture", "tests/fixtures/python-matrix/run.py")
matrix_host = load("owned_matrix_host", "tests/fixtures/python-matrix/check.py")


class NativeRuntimeTests(unittest.TestCase):
    def test_mount_write_failure_cannot_be_reported_as_readiness(self):
        with patch.object(native.tempfile, "NamedTemporaryFile", side_effect=PermissionError("read-only mount")):
            with self.assertRaisesRegex(PermissionError, "read-only mount"):
                native.mounts_check()

    def test_proc_identifies_the_actual_process(self):
        self.assertEqual(native.proc_check(), {"self_status": True})

    def test_pty_transfers_both_directions(self):
        self.assertEqual(native.pty_check(), {"bidirectional": True, "terminal": True})

    def test_socket_failure_cannot_be_reported_as_readiness(self):
        with patch.object(native.socket, "socket", side_effect=PermissionError("socket unavailable")):
            with self.assertRaisesRegex(PermissionError, "socket unavailable"):
                native.socket_check()

    def exercise_tmux(self, *, pane="xorder-terminal-proof\n", leftover=False, fail_send=False):
        calls = []
        def command(*argv, check=True):
            calls.append(argv)
            if argv[-1] == "-V":
                output, code = "tmux 3.6a", 0
            elif "capture-pane" in argv:
                output, code = pane, 0
            elif "has-session" in argv:
                killed = any("kill-session" in row for row in calls)
                output, code = "", 0 if not killed or leftover else 1
            elif fail_send and "send-keys" in argv:
                raise subprocess.CalledProcessError(1, argv)
            else:
                output, code = "", 0
            return subprocess.CompletedProcess(argv, code, output, "")
        return calls, command

    def test_tmux_requires_executed_output_and_session_cleanup(self):
        calls, command = self.exercise_tmux()
        with patch.object(native, "command", side_effect=command):
            self.assertIn("capture-pane", native.tmux_check()["checks"])
        self.assertTrue(any("send-keys" in row for row in calls))
        self.assertTrue(any("kill-session" in row for row in calls))
        self.assertEqual(calls[-1][-1], "kill-server")

    def test_echoed_shell_input_does_not_prove_terminal_execution(self):
        calls, command = self.exercise_tmux(pane="$ echo xorder-terminal-proof\n")
        with patch.object(native, "command", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "execute and render"):
                native.tmux_check()
        self.assertEqual(calls[-1][-1], "kill-server")

    def test_session_surviving_cleanup_fails(self):
        _, command = self.exercise_tmux(leftover=True)
        with patch.object(native, "command", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "survived cleanup"):
                native.tmux_check()

    def test_tmux_failure_still_cleans_its_private_server(self):
        calls, command = self.exercise_tmux(fail_send=True)
        with patch.object(native, "command", side_effect=command):
            with self.assertRaises(subprocess.CalledProcessError):
                native.tmux_check()
        self.assertEqual(calls[-1][-1], "kill-server")


class ImageOwnedFixtureTests(unittest.TestCase):
    def test_python_subject_installs_and_imports_a_local_wheel_without_index(self):
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory) / "venv"
            wheel = Path(directory) / "xorder_image_probe-1.0.0-py3-none-any.whl"
            matrix.wheel_fixture(wheel)
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True,
                           capture_output=True, text=True, timeout=60)
            python = str(venv / "bin/python")
            subprocess.run([python, "-m", "pip", "--isolated", "install", "--no-index", "--no-deps",
                            "--disable-pip-version-check", str(wheel)], check=True,
                           capture_output=True, text=True, timeout=30)
            result = subprocess.run([python, "-I", "-c", "import xorder_image_probe; print(xorder_image_probe.VALUE)"],
                                    check=True, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.stdout.strip(), "42")

    def test_python_host_wrapper_needs_no_git_and_preserves_offline_mounts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(matrix_host, "ROOT", Path(directory)), \
                patch.object(matrix_host.sys, "argv", ["check.py", "candidate:test"]), \
                patch.object(matrix_host, "run") as run, patch.object(matrix_host.subprocess, "run"):
            matrix_host.main()
        self.assertEqual(run.call_count, 1)
        argv = run.call_args.args
        self.assertEqual(argv[:3], ("docker", "run", "--rm"))
        self.assertIn("--network=none", argv)
        self.assertTrue(any("dst=/workspace" in arg for arg in argv))
        self.assertTrue(any("dst=/home/dev" in arg for arg in argv))
        self.assertTrue(any("dst=/runtime,readonly" in arg for arg in argv))

    def status(self):
        return {"harnesses": {name: {"status": "installed", "integrity": "passed", "version": "1.0.0",
                "sha256": "a" * 64, "provenance": {"distribution": distribution, "source": "https://vendor.invalid"}}
                for name, distribution in harness.DISTRIBUTIONS.items()}}

    def test_harness_status_rejects_missing_integrity_version_or_provenance(self):
        pins = {"harnesses": {name: {"version": "1.0.0"} for name in harness.NAMES}}
        status = self.status()
        harness.validate_status(status, pins)
        for key, value in (("integrity", "failed"), ("status", "not_installed"), ("version", "2.0.0"),
                           ("sha256", ""), ("provenance", {})):
            changed = copy.deepcopy(status)
            changed["harnesses"]["codex"][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                harness.validate_status(changed, pins)

    def test_codex_fixture_requires_generated_parseable_schema(self):
        def command(*argv):
            if argv[-1] == "--version":
                return "codex-cli 1.0.0\n"
            (Path(argv[-1]) / "schema.json").write_text(json.dumps({"type": "object"}))
            return ""
        with patch.object(harness, "command", side_effect=command):
            result = harness.cli_check("codex", "1.0.0")
        self.assertEqual(result["schema_files"], 1)
        self.assertEqual(result["live_round_trip"], "unverified")
        with patch.object(harness, "command", return_value="codex-cli 1.0.0"):
            with self.assertRaisesRegex(RuntimeError, "generate JSON schema"):
                harness.cli_check("codex", "1.0.0")

    def test_empty_help_and_wrong_executed_version_fail(self):
        for name in ("claude", "grok"):
            with self.subTest(name=name), patch.object(harness, "command", side_effect=["1.0.0", ""]):
                with self.assertRaisesRegex(RuntimeError, "help operation"):
                    harness.cli_check(name, "1.0.0")
        with patch.object(harness, "command", return_value="codex-cli 2.0.0"):
            with self.assertRaisesRegex(RuntimeError, "selected version"):
                harness.cli_check("codex", "1.0.0")


if __name__ == "__main__":
    unittest.main()
