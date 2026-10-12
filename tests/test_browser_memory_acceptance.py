"""Receipt and real-Docker fixture orchestration fails closed on missing evidence."""
from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("browser_acceptance", ROOT / "tests/fixtures/uxor/browser_acceptance.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class BrowserMemoryAcceptanceTests(unittest.TestCase):
    def test_failed_behavior_keeps_original_exit_and_still_runs_both_memory_checks(self):
        # Execute the actual fixture dispatch with stand-in commands; a second
        # failure must not erase the behavior exit or prevent the isolated probe.
        source = (ROOT / "tests/fixtures/uxor/run.sh").read_text()
        dispatch = source.split("normal_status=0\n", 1)[1].split("# Audit the actual pinned consumer run", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = root / "examples/uxor/run.sh"
            runner.parent.mkdir(parents=True)
            runner.write_text("#!/bin/bash\nexit 7\n")
            python = root / "bin/python3"
            python.parent.mkdir()
            python.write_text('#!/bin/bash\nprintf "%s\\n" "$2" >> "$CHECK_LOG"\nif [ "$2" = normal ]; then exit 9; fi\n')
            python.chmod(0o755)
            (root / acceptance.CONFIG_NAME).touch()
            script = 'set -euo pipefail\nroot="$FIXTURE_ROOT"\nwork="$FIXTURE_ROOT"\nWORKSPACE="$FIXTURE_ROOT"\nUXOR_PROJECT=fixture\ncross_browser=1\nconsumer=(repo sha selected.spec.ts)\nnormal_status=0\n' + dispatch
            result = subprocess.run(["bash", "-c", script], env={**os.environ, "FIXTURE_ROOT": str(root),
                                    "CHECK_LOG": str(root / "checks"), "PATH": str(python.parent) + ":" + os.environ["PATH"]},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual((root / "checks").read_text().splitlines(), ["config", "normal", "oom"])
            self.assertIn("behavior=7 normal_memory=9 isolated_child_oom=0", result.stdout)

    def test_cleanup_archive_retains_failed_trace_context_and_receipt_logs(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
            root = Path(temporary)
            workspace, attempts, logs, destination = (root / name for name in ("repo", "attempts", "logs", "out"))
            attempt = attempts / "run-id"
            attempt.mkdir(parents=True)
            logs.mkdir()
            for state in ("failed", "passed"):
                folder = workspace / "test-results" / state
                folder.mkdir(parents=True)
                (folder / "trace.zip").write_bytes(state.encode())
                (folder / "error-context.md").write_text(state)
            receipt = {"exit_code": 1, "observed_test_attempts": [
                {"status": state, "trace_attachments": [{"path": f"/app/test-results/{state}/trace.zip"}]}
                for state in ("failed", "passed")]}
            (attempt / "receipt.json").write_text(json.dumps(receipt))
            for name in ("events.jsonl", "test-output.log", "server.log"):
                (attempt / name).write_text(name)
            (logs / "child-oom.log").write_text("original_exit_code=137")
            acceptance.archive_evidence(workspace, attempts, logs, destination)
            self.assertEqual(json.loads((destination / "attempts/run-id/receipt.json").read_text())["exit_code"], 1)
            self.assertEqual((destination / "failure-artifacts/test-results/failed/trace.zip").read_bytes(), b"failed")
            self.assertTrue((destination / "failure-artifacts/test-results/failed/error-context.md").is_file())
            self.assertFalse((destination / "failure-artifacts/test-results/passed").exists())
            self.assertEqual((destination / "child-oom.log").read_text(), "original_exit_code=137")
            self.assertTrue((destination / "attempts/run-id/events.jsonl").is_file())
            self.assertTrue((destination / "attempts/run-id/server.log").is_file())

    def receipt(self):
        return {"exit_code": 0, "observer_status": "complete", "selected_test_count": 135,
                "observed_test_attempts": [{"project": project, "status": "passed", "retry": 0}
                                           for project in acceptance.PROJECTS for _ in range(45)]}

    def test_three_engine_receipt_requires_executed_passes_for_every_project(self):
        with redirect_stdout(io.StringIO()):
            acceptance.verify_behavior(self.receipt())
        for mutate in (lambda receipt: receipt["observed_test_attempts"].pop(),
                       lambda receipt: receipt["observed_test_attempts"][0].update(project="acceptance-chromium", retry=1),
                       lambda receipt: receipt["observed_test_attempts"][45].update(project="acceptance-chromium"),
                       lambda receipt: receipt.update(observer_status="incomplete")):
            receipt = self.receipt()
            mutate(receipt)
            with self.assertRaisesRegex(RuntimeError, "45 passed cases per engine"):
                acceptance.verify_behavior(receipt)

    def run_oom(self, exit_code=137, delta=1, diagnosed=True):
        self.calls = []
        prior = {"service": "browser", "container": "fixture-id", "started_at": "same-start",
                 "cgroup_version": 2, "cgroup_limit_bytes": acceptance.OOM_LIMIT,
                 "docker_limit_bytes": acceptance.OOM_LIMIT, "events": {"oom_kill": 0}, "oom_kill_delta": 0,
                 "command_window_oom": False, "oom_killed": False}
        after = {**prior, "events": {"oom_kill": delta}, "oom_kill_delta": delta,
                 "command_window_oom": delta > 0, "oom_killed": True}
        def observe(project, env, before=None):
            self.assertEqual(env["BROWSER_MEMORY"], "512m")
            return {"services": [after if before is not None else prior]}
        @contextmanager
        def diagnostics(project, env):
            try:
                yield
            except subprocess.CalledProcessError:
                if diagnosed:
                    print("service=browser container=fixture-id Docker limit=0.50 GiB cgroup limit=0.50 GiB BROWSER_MEMORY=512m during the command window: out of memory; raise BROWSER_MEMORY")
                raise
        def docker(arguments, env, **options):
            self.calls.append(arguments)
            if arguments[0] == "run":
                self.assertIn("--memory-swap", arguments)
                self.assertIn("--init", arguments)
                return subprocess.CompletedProcess(arguments, 0, "fixture-id\n", "")
            if arguments[0] == "exec":
                self.assertEqual(options["timeout"], 45)
                raise subprocess.CalledProcessError(exit_code, ["docker", *arguments])
            return subprocess.CompletedProcess(arguments, 0, "", "")
        self.state = {"State": {"Running": True, "OOMKilled": True}}
        with tempfile.TemporaryDirectory() as temporary, patch.object(acceptance, "docker", side_effect=docker), \
                patch.object(acceptance, "inspect", return_value=self.state):
            self.output = io.StringIO()
            with redirect_stdout(self.output):
                acceptance.child_oom("real-live-project", {"BROWSER_MEMORY": "4g"}, "accepted-image@sha256:fixture", Path(temporary) / "state", observe, diagnostics)

    def test_child_oom_preserves_137_observes_actual_flag_and_removes_isolated_container(self):
        self.run_oom()
        self.assertEqual(self.calls[-1], ["rm", "--force", "fixture-id"])
        self.assertIn('"original_exit_code": 137', self.output.getvalue())
        self.assertIn('"docker_oom_killed": true', self.output.getvalue())
        self.assertIn("not a renderer benchmark", self.output.getvalue())

    def test_missing_kill_delta_or_wrong_original_exit_fails_and_still_cleans_up(self):
        for options in ({"delta": 0}, {"exit_code": 42}):
            with self.subTest(options=options):
                with self.assertRaisesRegex(RuntimeError, "current-window counter, limit, or original exit"):
                    self.run_oom(**options)
                self.assertEqual(self.calls[-1], ["rm", "--force", "fixture-id"])

    def test_missing_failed_command_diagnostic_is_an_acceptance_failure(self):
        with self.assertRaisesRegex(RuntimeError, "observer did not report"):
            self.run_oom(diagnosed=False)
        self.assertEqual(self.calls[-1], ["rm", "--force", "fixture-id"])


if __name__ == "__main__":
    unittest.main()
