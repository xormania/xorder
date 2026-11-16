"""Project preparation behavior exercised through the public process interface."""
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "examples/xorchestrate/runner.py"
FIXTURE = ROOT / "tests/fixtures/xorchestrate-runner/fixture.py"


@unittest.skipUnless(sys.platform.startswith("linux"), "native Linux runner contract")
class XorchestrateRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.workspace = self.directory / "candidate project"
        self.state = self.directory / "owned state"
        self.log = self.directory / "commands.jsonl"
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.workspace.mkdir()
        # Execute byte-identical runner source with explicit project/native
        # fixtures. These tests establish orchestration behavior, while the
        # separate native acceptance test below uses the real host and tmux.
        runner_directory = self.directory / "runner subject"
        runner_directory.mkdir()
        self.runner = runner_directory / "runner.py"
        shutil.copyfile(RUNNER, self.runner)
        (runner_directory / "native.py").write_text(
            "import os,sys\nsys.path.insert(0,os.getcwd())\n"
            "from fixture import main\nmain('native')\n", encoding="utf-8")
        for path in ("scripts/ci", "scripts/testkit/adapters", "tests/hexagonal/support",
                     "xorchestrate/adapters/telemetry_collector", ".github/workflows"):
            (self.workspace / path).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURE, self.workspace / "fixture.py")
        (self.workspace / "pyproject.toml").write_text(
            '[project]\nname="fixture-consumer"\nversion="0.0.0"\nrequires-python=">=3.12"\n'
            '[dependency-groups]\nvalidation=["zizmor==1.32.0"]\n', encoding="utf-8")
        (self.workspace / "uv.lock").write_text("version = 1\nrevision = 3\n", encoding="utf-8")
        (self.workspace / ".github/requirements-ci.txt").write_text("zizmor==1.32.0\n", encoding="utf-8")
        (self.workspace / ".github/workflows/ci.yml").write_text(json.dumps({"jobs": {"checks": {"steps": [
            {"uses": "actions/setup-python@" + "0" * 40, "with": {"python-version": platform.python_version()}},
            {"uses": "astral-sh/setup-uv@" + "0" * 40, "with": {"version": "0.13.7"}},
        ]}}}), encoding="utf-8")
        (self.workspace / "xorchestrate/adapters/telemetry_collector/sqlite.py").write_text(
            "from fixture import failure, record\n"
            "def require_sqlite():\n"
            "    record('sqlite')\n"
            "    failure('sqlite')\n", encoding="utf-8")
        (self.workspace / "scripts/ci/dependencies.py").write_text(
            'from fixture import main\nmain("dependencies")\n', encoding="utf-8")
        (self.workspace / "scripts/testkit/adapters/profiles.py").write_text(
            "from fixture import setup\n", encoding="utf-8")
        for relative in ("scripts/testkit/adapters/static.py", "tests/hexagonal/test_workflow_security.py",
                         "tests/hexagonal/support/static_checks.py"):
            (self.workspace / relative).write_text("# project-owned scanner contract fixture\n", encoding="utf-8")
        (self.workspace / "pytest.py").write_text('from fixture import main\nmain("controls")\n', encoding="utf-8")
        proof = self.workspace / "scripts/proof.sh"
        proof.write_text(
            '#!/bin/sh\nexec "' + sys.executable + '" "' + str(self.workspace / "fixture.py")
            + '" proof "$@"\n', encoding="utf-8")
        proof.chmod(0o755)
        uv = self.bin / "uv"
        uv.write_text(
            "#!" + sys.executable + " -S\nimport os,sys\n"
            "os.execv(sys.executable, [sys.executable, '-S', " + repr(str(self.workspace / "fixture.py"))
            + ", 'uv', *sys.argv[1:]])\n", encoding="utf-8")
        uv.chmod(0o755)
        tmux = self.bin / "tmux"
        tmux.write_text(
            "#!" + sys.executable + " -S\nimport os,sys\n"
            "os.execv(sys.executable, [sys.executable, '-S', " + repr(str(self.workspace / "fixture.py"))
            + ", 'tmux', *sys.argv[1:]])\n", encoding="utf-8")
        tmux.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "XR_FIXTURE_LOG": str(self.log), "PYTHONDONTWRITEBYTECODE": "1"}
        self.command = [sys.executable, str(self.runner), "--workspace", str(self.workspace),
                        "--state-dir", str(self.state), "--python", sys.executable, "--uv", str(uv)]

    def invoke(self, action, *, success=True, env=None, arguments=()):
        result = subprocess.run([*self.command, *arguments, action], env=env or self.env,
                                capture_output=True, text=True, timeout=30, check=False)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail("Runner must end with machine-readable result: " + result.stdout + result.stderr)
        return output

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def snapshot(self, folder):
        if not folder.exists():
            return None
        return {str(path.relative_to(folder)): (path.stat().st_mtime_ns, path.read_bytes())
                for path in folder.rglob("*") if path.is_file() and not path.is_symlink()}

    def assert_ready(self, output):
        self.assertEqual(output["status"], "passed", output)
        self.assertTrue((self.state / "environment/bin/zizmor").is_file())
        self.assertTrue((self.state / "receipt.json").is_file())

    def test_missing_tool_is_not_ready_then_preparation_verifies_selected_environment(self):
        before = self.snapshot(self.workspace)
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assertFalse(self.state.exists(), "Observation must not create state")
        prepared = self.invoke("prepare")
        self.assert_ready(prepared)
        stages = [call["stage"] for call in self.calls()]
        self.assertIn("sync", stages)
        self.assertIn("doctor", stages)
        self.assertIn("controls", stages)
        self.assertIn("sqlite", stages)
        self.assertIn("native", stages)
        self.assertEqual(self.snapshot(self.workspace), before, "Preparation preserves source and locks")
        self.assertEqual(self.invoke("status")["status"], "passed")

    def test_unchanged_preparation_reuses_installation_but_repeats_verification(self):
        self.assert_ready(self.invoke("prepare"))
        first = self.calls()
        self.assert_ready(self.invoke("prepare"))
        later = self.calls()[len(first):]
        self.assertNotIn("sync", [call["stage"] for call in later])
        self.assertNotIn("install", [call["stage"] for call in later])
        self.assertIn("doctor", [call["stage"] for call in later])
        self.assertIn("controls", [call["stage"] for call in later])

    def test_new_validation_dependency_invalidates_reuse_without_touching_another_scope(self):
        self.assert_ready(self.invoke("prepare"))
        sibling = self.directory / "another worktree state"
        sibling.mkdir()
        (sibling / "healthy").write_text("preserve me", encoding="utf-8")
        before = self.snapshot(sibling)
        inputs = self.workspace / "pyproject.toml"
        inputs.write_text(inputs.read_text().replace("1.32.0", "1.33.0"), encoding="utf-8")
        export = self.workspace / ".github/requirements-ci.txt"
        export.write_text("zizmor==1.33.0\n", encoding="utf-8")
        lock = self.workspace / "uv.lock"
        lock.write_text(lock.read_text() + "# changed baseline\n", encoding="utf-8")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        old_count = len(self.calls())
        self.assert_ready(self.invoke("prepare"))
        self.assertIn("sync", [call["stage"] for call in self.calls()[old_count:]])
        self.assertEqual(self.snapshot(sibling), before)
        actual = subprocess.run([str(self.state / "environment/bin/zizmor"), "--version"],
                                env=self.env, capture_output=True, text=True, check=True)
        self.assertEqual(actual.stdout.strip(), "zizmor 1.33.0")

    def test_unrelated_source_edit_does_not_reinstall_dependencies(self):
        self.assert_ready(self.invoke("prepare"))
        (self.workspace / "application.py").write_text("print('changed application')\n", encoding="utf-8")
        old_count = len(self.calls())
        self.assert_ready(self.invoke("prepare"))
        self.assertNotIn("sync", [call["stage"] for call in self.calls()[old_count:]])

    def test_missing_selected_scanner_is_not_satisfied_by_global_tool(self):
        self.assert_ready(self.invoke("prepare"))
        scanner = self.state / "environment/bin/zizmor"
        shutil.copyfile(scanner, self.bin / "zizmor")
        (self.bin / "zizmor").chmod(0o755)
        scanner.unlink()
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.invoke("check", success=False)
        self.assertFalse(scanner.exists(), "A check must never install packages")
        self.assert_ready(self.invoke("prepare"))

    def test_wrong_selected_scanner_version_invalidates_preparation_and_is_repaired(self):
        self.assert_ready(self.invoke("prepare"))
        scanner = self.state / "environment/bin/zizmor"
        scanner.write_text(scanner.read_text().replace("1.32.0", "0.0.1"), encoding="utf-8")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        old_count = len(self.calls())
        self.assert_ready(self.invoke("prepare"))
        self.assertIn("sync", [call["stage"] for call in self.calls()[old_count:]])

    def test_failed_refresh_cannot_reuse_an_old_success_receipt(self):
        self.assert_ready(self.invoke("prepare"))
        lock = self.workspace / "uv.lock"
        lock.write_text(lock.read_text() + "# new dependency\n", encoding="utf-8")
        self.assertEqual(self.invoke("prepare", success=False, env={**self.env, "XR_FIXTURE_FAIL": "sync"})["status"], "failed")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_inconsistent_dependencies_fail_before_package_install(self):
        (self.workspace / ".inconsistent").write_text("stale export", encoding="utf-8")
        self.assertEqual(self.invoke("prepare", success=False)["status"], "failed")
        self.assertNotIn("sync", [call["stage"] for call in self.calls()])
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")

    def test_selected_python_must_match_the_project_ci_baseline_before_installation(self):
        path = self.workspace / ".github/workflows/ci.yml"
        workflow = json.loads(path.read_text())
        workflow["jobs"]["checks"]["steps"][0]["with"]["python-version"] = "3.12.999"
        path.write_text(json.dumps(workflow), encoding="utf-8")
        result = self.invoke("prepare", success=False)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("sync", [call["stage"] for call in self.calls()])
        self.assertFalse((self.state / "environment").exists())

    def test_selected_uv_must_match_the_project_ci_baseline_before_installation(self):
        path = self.workspace / ".github/workflows/ci.yml"
        workflow = json.loads(path.read_text())
        workflow["jobs"]["checks"]["steps"][1]["with"]["version"] = "0.0.1"
        path.write_text(json.dumps(workflow), encoding="utf-8")
        result = self.invoke("prepare", success=False)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("sync", [call["stage"] for call in self.calls()])
        self.assertFalse((self.state / "environment").exists())

    def test_project_sqlite_failure_prevents_ready_state(self):
        result = self.invoke("prepare", success=False, env={**self.env, "XR_FIXTURE_FAIL": "sqlite"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("sqlite", [call["stage"] for call in self.calls()])
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_missing_tmux_is_reported_before_installation(self):
        result = self.invoke("prepare", success=False, arguments=("--tmux", str(self.bin / "absent-tmux")))
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("sync", [call["stage"] for call in self.calls()])
        self.assertFalse((self.state / "environment").exists())

    def test_failed_native_terminal_probe_prevents_ready_state(self):
        result = self.invoke("prepare", success=False, env={**self.env, "XR_FIXTURE_FAIL": "native"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("native", [call["stage"] for call in self.calls()])
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_failed_doctor_and_failed_scanner_controls_never_become_ready(self):
        for stage in ("doctor", "controls"):
            with self.subTest(stage=stage):
                self.invoke("prepare", success=False, env={**self.env, "XR_FIXTURE_FAIL": stage})
                self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_ambient_pytest_collection_setting_cannot_skip_scanner_execution(self):
        self.assert_ready(self.invoke("prepare", env={**self.env, "PYTEST_ADDOPTS": "--collect-only"}))
        observations = [call for call in self.calls() if call["stage"] == "scanner"]
        self.assertGreaterEqual(len(observations), 2, "Both clean and deliberate-fault scanner observations must execute")

    def test_status_preserves_all_prepared_state(self):
        self.assert_ready(self.invoke("prepare"))
        state_before = self.snapshot(self.state)
        source_before = self.snapshot(self.workspace)
        old_count = len(self.calls())
        self.assertEqual(self.invoke("status")["status"], "passed")
        self.assertEqual(self.snapshot(self.state), state_before)
        self.assertEqual(self.snapshot(self.workspace), source_before)
        self.assertEqual(len(self.calls()), old_count, "Status must not invoke project setup, doctor, or validation hooks")

    def test_status_before_ownership_cannot_import_a_repository_shadow_module(self):
        canary = self.directory / "repository-code-executed"
        (self.workspace / "platform.py").write_text(
            "from pathlib import Path\n"
            "Path(" + repr(str(canary)) + ").write_text('repository code executed')\n"
            "def python_version():\n    return " + repr(platform.python_version()) + "\n", encoding="utf-8")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assertFalse(canary.exists(), "Fixed interpreter observation imported repository code")
        self.assertFalse(self.state.exists())

    def test_status_of_prepared_environment_cannot_import_a_repository_shadow_module(self):
        self.assert_ready(self.invoke("prepare"))
        canary = self.directory / "repository-code-executed"
        (self.workspace / "platform.py").write_text(
            "from pathlib import Path\n"
            "Path(" + repr(str(canary)) + ").write_text('repository code executed')\n"
            "def python_version():\n    return " + repr(platform.python_version()) + "\n", encoding="utf-8")
        state_before = self.snapshot(self.state)
        self.assertEqual(self.invoke("status")["status"], "passed")
        self.assertFalse(canary.exists(), "Fixed interpreter observation imported repository code")
        self.assertEqual(self.snapshot(self.state), state_before)

    def test_check_runs_selected_suite_without_reinstalling(self):
        self.assert_ready(self.invoke("prepare"))
        old_count = len(self.calls())
        self.assertEqual(self.invoke("check")["status"], "passed")
        stages = [call["stage"] for call in self.calls()[old_count:]]
        self.assertIn("consistency", stages)
        self.assertIn("doctor", stages)
        self.assertIn("run", stages)
        self.assertNotIn("sync", stages)

    def test_failed_actual_check_invalidates_old_readiness_until_verification_succeeds(self):
        self.assert_ready(self.invoke("prepare"))
        result = self.invoke("check", success=False, env={**self.env, "XR_FIXTURE_FAIL": "check"})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["check"], "failed")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_package_timeout_leaves_incomplete_state_and_bounded_diagnostics(self):
        blocked = self.directory / "blocked"
        started = time.monotonic()
        result = self.invoke("prepare", success=False, arguments=("--timeout", "0.3"),
                             env={**self.env, "XR_FIXTURE_BLOCK": "sync", "XR_FIXTURE_BLOCKED": str(blocked)})
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(blocked.exists(), result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("exceeded", result["reason"])
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))

    def test_setup_behavior_changes_invalidate_reuse(self):
        self.assert_ready(self.invoke("prepare"))
        setup = self.workspace / "scripts/testkit/adapters/profiles.py"
        setup.write_text(setup.read_text() + "# changed consumer setup behavior\n", encoding="utf-8")
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        old_count = len(self.calls())
        self.assert_ready(self.invoke("prepare"))
        self.assertIn("sync", [call["stage"] for call in self.calls()[old_count:]])

    def test_one_state_directory_cannot_be_adopted_by_another_workspace(self):
        self.assert_ready(self.invoke("prepare"))
        before = self.snapshot(self.state)
        second = self.directory / "second candidate"
        shutil.copytree(self.workspace, second)
        command = list(self.command)
        command[command.index("--workspace") + 1] = str(second)
        result = subprocess.run([*command, "prepare"], env=self.env, capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(self.state), before)

    def test_unowned_environment_is_preserved_and_no_installer_runs(self):
        environment = self.state / "environment"
        environment.mkdir(parents=True)
        (environment / "owner-data").write_text("existing intentional environment", encoding="utf-8")
        original = self.snapshot(environment)
        result = self.invoke("prepare", success=False)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.snapshot(environment), original)
        self.assertNotIn("sync", [call["stage"] for call in self.calls()])

    def test_redirected_state_is_rejected_without_modifying_the_destination(self):
        destination = self.directory / "unrelated destination"
        destination.mkdir()
        (destination / "owner-data").write_text("preserve", encoding="utf-8")
        self.state.symlink_to(destination, target_is_directory=True)
        original = self.snapshot(destination)
        result = self.invoke("prepare", success=False)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.snapshot(destination), original)
        self.assertEqual(self.calls(), [])

    def test_redirected_profile_cannot_operate_on_an_unrelated_environment(self):
        self.assert_ready(self.invoke("prepare"))
        unrelated = self.directory / "unrelated environment"
        unrelated.mkdir()
        (unrelated / "intentional-pin").write_text("preserve", encoding="utf-8")
        profile_path = self.state / "profile.json"
        profile = json.loads(profile_path.read_text())
        profile["environment"] = str(unrelated)
        profile["interpreter"] = str(unrelated / "bin/python")
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        before = self.snapshot(unrelated)
        state_before = self.snapshot(self.state)
        old_count = len(self.calls())
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.invoke("check", success=False)
        self.invoke("prepare", success=False)
        self.assertEqual(self.snapshot(unrelated), before)
        self.assertEqual(self.snapshot(self.state), state_before)
        self.assertEqual(len(self.calls()), old_count, "Refuse redirected selection before project hooks")

    def test_interrupted_setup_is_incomplete_and_recovers_through_preparation(self):
        blocked = self.directory / "blocked"
        environment = {**self.env, "XR_FIXTURE_BLOCK": "sync", "XR_FIXTURE_BLOCKED": str(blocked)}
        process = subprocess.Popen([*self.command, "prepare"], env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not blocked.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(blocked.exists(), "Preparation never reached the interruptible install")
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
        self.assertEqual(self.invoke("status", success=False)["status"], "not_ready")
        self.assert_ready(self.invoke("prepare"))


@unittest.skipUnless(sys.platform.startswith("linux"), "native Linux readiness acceptance")
class XorchestrateNativeAcceptanceTests(unittest.TestCase):
    def test_real_tmux_transfers_terminal_data_and_cleans_its_private_processes(self):
        tmux = shutil.which("tmux")
        if tmux is None:
            self.skipTest("Real tmux is unavailable on this host")
        try:
            with socket.socket(socket.AF_UNIX):
                pass
        except OSError as error:
            self.skipTest("Host cannot create Unix sockets: " + str(error))
        result = subprocess.run([sys.executable, str(ROOT / "examples/xorchestrate/native.py"), tmux],
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["status"], "passed", evidence)
        for capability in ("pty", "unix_socket", "proc", "terminal_communication", "cleanup"):
            self.assertEqual(evidence[capability], "passed", evidence)
        self.assertEqual(evidence["uid"], os.geteuid())
        self.assertEqual(evidence["gid"], os.getegid())
        for key in ("server_pid", "pane_pid"):
            self.assertFalse((Path("/proc") / str(evidence[key])).exists(), key + " remained after readiness")


if __name__ == "__main__":
    unittest.main()
