"""Receipt and real-Docker fixture orchestration fails closed on missing evidence."""
from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import json
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
