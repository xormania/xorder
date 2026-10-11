"""Runner dispatch keeps source faults, leases, and test status connected."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/flowbite-xor"))
spec = importlib.util.spec_from_file_location("plant_runner", ROOT / "examples/flowbite-xor/runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PlantDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "consumer"
        (self.workspace / "demo").mkdir(parents=True)
        self.source = self.workspace / "recipe.js"
        self.copy = self.workspace / "demo/recipe.js"
        self.source.write_text("ready = true;\n")
        self.copy.write_bytes(self.source.read_bytes())
        (self.workspace / ".gitignore").write_text("demo/recipe.js\n")
        (self.workspace / "package.json").write_text(json.dumps({"devDependencies": {"@playwright/test": "1.58.2"}}))
        (self.workspace / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/@playwright/test": {"version": "1.58.2"}}}))
        for name in ("compose.yaml", "compose.override.yaml"):
            (self.workspace / "demo" / name).write_text("services: {}\n")
        (self.workspace / ".xorder").mkdir()
        configuration = {"schema_version": 1, "sync": {"command": ["project-sync"], "check": {"command": ["project-check"]}},
                         "plants": {"disabled": {"edits": [{"path": "recipe.js", "search": "true", "replace": "false"}],
                                                  "confirm": {"command": ["project-fetch"], "contains": "ready = false"}}}}
        (self.workspace / ".xorder/testing.json").write_text(json.dumps(configuration))
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture"], check=True)
        self.env = {"PATH": os.environ["PATH"], "WORKSPACE": str(self.workspace), "IMAGE": "fixture:project",
                    "XDG_CACHE_HOME": str(self.root / "cache"), "PROXY_PASSTHROUGH": "0"}
        self.events = []
        self.active = False
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        for context in (redirect_stdout(self.stdout), redirect_stderr(self.stderr)):
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    @contextmanager
    def lease(self, workspace, env):
        self.assertFalse(self.active, "A plant must not take a nested test lease")
        self.assertIn("ready = true", self.source.read_text())
        self.events.append("lease")
        self.active = True
        self.lease_env = dict(env)
        try:
            yield 2
        finally:
            self.assertIn("ready = true", self.source.read_text())
            self.assertEqual(self.copy.read_bytes(), self.source.read_bytes())
            self.active = False
            self.events.append("release")

    def execute(self, compose, env, *arguments, **options):
        self.assertTrue(options["capture"])
        self.assertFalse(options["check"])
        self.events.append(arguments[0])
        if arguments == ("project-sync",):
            shutil.copyfile(self.source, self.copy)
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments == ("project-check",):
            stale = self.source.read_bytes() != self.copy.read_bytes()
            return subprocess.CompletedProcess(arguments, int(stale), "demo/recipe.js differs\n" if stale else "", "")
        if arguments == ("project-fetch",):
            return subprocess.CompletedProcess(arguments, 0, self.copy.read_text(), "")
        self.fail("Unexpected argv: " + repr(arguments))

    def dispatch(self, arguments, test=None, env=None, lease=None):
        with patch.dict(os.environ, env or self.env, clear=True), patch.object(runner, "container_environment", return_value={}), \
                patch.object(runner, "browser_image", return_value="fixture:browser"), patch.object(runner, "php_exec", side_effect=self.execute), \
                patch.object(runner, "heavy_run", side_effect=lease or self.lease), patch.object(runner, "run_test", side_effect=test, create=True):
            return runner.main(arguments)

    def test_named_plant_uses_outer_lease_and_preserves_failed_receipt_status(self):
        def test(compose, env, workspace, project, arguments, workers=None):
            self.assertTrue(self.active)
            self.assertEqual(workers, 2)
            self.assertEqual(arguments, ["spec.ts", "--project=webkit"])
            self.assertEqual(env["XORDER_PLANT_NAME"], "disabled")
            self.assertEqual(env["XORDER_TEST_WAIT_SECONDS"], "12")
            self.assertEqual(env["XORDER_TEST_MEASURE"], "1")
            self.assertEqual(env["XORDER_TEST_ATTEST_SERVER"], "1")
            self.assertIn("ready = false", self.copy.read_text())
            self.events.append("receipt-test")
            return 7
        result = self.dispatch(["plant", "disabled", "--wait=12", "--measure", "--attest-server", "--", "spec.ts", "--project=webkit"], test=test)
        self.assertEqual(result, 7)
        self.assertEqual(self.events, ["lease", "project-sync", "project-check", "project-fetch", "receipt-test", "project-sync", "project-check", "release"])

    def test_sync_check_reports_stale_copy_without_writes_or_test_lease(self):
        self.copy.write_text("leftover fault\n")
        with self.assertRaisesRegex(ValueError, "Sync check failed"):
            self.dispatch(["sync", "--check"], lease=lambda *arguments: self.fail("Read-only sync check took a test lease"))
        self.assertEqual(self.copy.read_text(), "leftover fault\n")
        self.assertEqual(self.events, ["project-check"])
        self.assertIn("demo/recipe.js differs", self.stdout.getvalue())

    def test_list_needs_neither_image_package_lock_nor_container(self):
        env = {key: value for key, value in self.env.items() if key != "IMAGE"}
        (self.workspace / "package-lock.json").unlink()
        with patch.object(runner, "playwright", side_effect=AssertionError("List read package locks")):
            self.assertEqual(self.dispatch(["plant", "--list"], env=env), 0)
        self.assertEqual(self.events, [])
        self.assertIn("disabled", self.stdout.getvalue())

    def test_restore_uses_running_stack_and_lease_without_package_lock(self):
        contract = runner.load_contract(self.workspace, runner.PROFILE)
        syncs = 0
        def prepare_recovery(command):
            nonlocal syncs
            if command == ["project-sync"]:
                syncs += 1
                if syncs == 2:
                    return subprocess.CompletedProcess(command, 9, "", "cleanup stopped")
            return self.execute([], self.env, *command, capture=True, check=False)
        self.assertEqual(runner.run_plant(self.workspace, self.env, contract, ["disabled"], prepare_recovery, lambda args: 7), 7)
        (self.workspace / "package-lock.json").unlink()
        (self.workspace / "package.json").unlink()
        self.events.clear()
        with patch.object(runner, "playwright", side_effect=AssertionError("Restore read package locks")):
            self.assertEqual(self.dispatch(["plant", "--restore"], test=lambda *args, **kwargs: self.fail("Restore ran specs")), 0)
        self.assertEqual(self.events, ["lease", "project-sync", "project-check", "release"])


if __name__ == "__main__":
    unittest.main()
