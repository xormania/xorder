"""Fault lifecycle checks use a tracked fixture and a separate served copy."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
from testing_contract import load_contract, run_plant, sync_contract


class ProjectFaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "project"
        self.workspace.mkdir()
        self.source = self.workspace / "recipe.js"
        self.copy = self.workspace / "demo.js"
        self.source.write_text("export const ready = true;\n")
        self.copy.write_bytes(self.source.read_bytes())
        (self.workspace / ".gitignore").write_text("demo.js\n")
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture"], check=True)
        self.env = {**os.environ, "XDG_CACHE_HOME": str(self.root / "cache")}
        self.contract = {"schema_version": 1, "sync": {"command": ["sync"], "check": {"command": ["check"]}},
                         "plants": {"disable": {"edits": [{"path": "recipe.js", "search": "true", "replace": "false"}],
                                               "confirm": {"command": ["fetch"], "contains": "ready = false"}}}}
        self.calls = []
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)
        self.errors = io.StringIO()
        error_capture = redirect_stderr(self.errors)
        error_capture.__enter__()
        self.addCleanup(error_capture.__exit__, None, None, None)

    def execute(self, command):
        self.calls.append(command[0])
        if command == ["sync"]:
            shutil.copyfile(self.source, self.copy)
            return subprocess.CompletedProcess(command, 0, "synced\n", "")
        if command == ["check"]:
            stale = self.source.read_bytes() != self.copy.read_bytes()
            return subprocess.CompletedProcess(command, int(stale), "demo.js differs\n" if stale else "", "")
        if command == ["fetch"]:
            return subprocess.CompletedProcess(command, 0, self.copy.read_text(), "")
        self.fail("Unexpected command " + repr(command))

    def journals(self):
        return list((self.root / "cache").rglob("recovery.json"))

    def test_test_status_and_arguments_survive_served_confirmation_and_cleanup(self):
        original = self.source.read_bytes()
        def run(arguments):
            self.calls.append("test")
            self.assertEqual(arguments, ["spec.ts", "--project=webkit"])
            self.assertIn("ready = false", self.copy.read_text())
            self.assertEqual(self.env["XORDER_PLANT_NAME"], "disable")
            return 7
        result = run_plant(self.workspace, self.env, self.contract, ["disable", "--", "spec.ts", "--project=webkit"], self.execute, run)
        self.assertEqual(result, 7)
        self.assertEqual(self.calls, ["sync", "check", "fetch", "test", "sync", "check"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.copy.read_bytes(), original)
        self.assertFalse(self.journals())
        self.assertNotIn("XORDER_PLANT_NAME", self.env)

    def test_missing_confirmation_never_runs_specs_and_restores_both_copies(self):
        self.contract["plants"]["disable"]["confirm"]["contains"] = "unexpected"
        with self.assertRaisesRegex(ValueError, "did not observe"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, lambda arguments: self.fail("Specs ran without confirmation"))
        self.assertEqual(self.source.read_bytes(), self.copy.read_bytes())
        self.assertIn("ready = true", self.copy.read_text())
        self.assertFalse(self.journals())

    def test_failed_or_interrupted_test_restores_source_and_untracked_copy(self):
        for exception in (subprocess.CalledProcessError(2, "playwright"), KeyboardInterrupt()):
            with self.subTest(exception=type(exception).__name__):
                def run(arguments):
                    raise exception
                with self.assertRaises(type(exception)):
                    run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, run)
                self.assertIn("ready = true", self.source.read_text())
                self.assertEqual(self.copy.read_bytes(), self.source.read_bytes())
                self.assertFalse(self.journals())

    def test_sigterm_uses_cleanup_and_restores_prior_signal_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        def interrupted(arguments):
            signal.raise_signal(signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, interrupted)
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assertIn("ready = true", self.copy.read_text())
        self.assertFalse(self.journals())

    def test_dirty_source_is_rejected_without_changes(self):
        self.source.write_text("user-owned changes\n")
        with self.assertRaisesRegex(ValueError, "match Git HEAD"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, lambda arguments: 0)
        self.assertEqual(self.source.read_text(), "user-owned changes\n")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.journals())

    def test_all_edits_are_validated_before_mutation(self):
        self.contract["plants"]["disable"]["edits"].append({"path": "recipe.js", "search": "missing", "replace": "x"})
        with self.assertRaisesRegex(ValueError, "search count"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, lambda arguments: 0)
        self.assertIn("ready = true", self.source.read_text())
        self.assertEqual(self.calls, [])

    def test_untracked_or_symlink_source_cannot_be_planted(self):
        untracked = self.workspace / "untracked.js"
        untracked.write_bytes(self.source.read_bytes())
        edit = self.contract["plants"]["disable"]["edits"][0]
        edit["path"] = "untracked.js"
        with self.assertRaisesRegex(ValueError, "tracked"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, lambda arguments: 0)
        linked = self.workspace / "linked.js"
        linked.symlink_to(self.source)
        edit["path"] = "linked.js"
        with self.assertRaisesRegex(ValueError, "symlinks"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, lambda arguments: 0)
        self.assertIn("ready = true", self.source.read_text())
        self.assertFalse(self.journals())

    def test_newer_source_edit_is_preserved_and_recovery_remains_reviewable(self):
        def newer_edit(arguments):
            self.source.write_text("owner changed this during the run\n")
            return 1
        self.assertEqual(run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, newer_edit), 1)
        self.assertIn("kept newer source edits", self.errors.getvalue())
        self.assertEqual(self.source.read_text(), "owner changed this during the run\n")
        journal = self.journals()[0]
        self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
        self.source.write_text("export const ready = false;\n")
        self.assertEqual(run_plant(self.workspace, self.env, self.contract, ["--restore"], self.execute, lambda arguments: 0), 0)
        self.assertIn("ready = true", self.copy.read_text())
        self.assertFalse(self.journals())

    def test_restore_sync_failure_retains_recovery_for_retry(self):
        syncs = 0
        def failing_sync(command):
            nonlocal syncs
            if command == ["sync"]:
                syncs += 1
                if syncs == 2:
                    return subprocess.CompletedProcess(command, 9, "", "server stopped")
            return self.execute(command)
        with self.assertRaisesRegex(ValueError, "server stopped"):
            run_plant(self.workspace, self.env, self.contract, ["disable"], failing_sync, lambda arguments: 0)
        self.assertIn("ready = true", self.source.read_text())
        self.assertIn("ready = false", self.copy.read_text())
        self.assertEqual(len(self.journals()), 1)
        run_plant(self.workspace, self.env, self.contract, ["--restore"], self.execute, lambda arguments: 0)
        self.assertIn("ready = true", self.copy.read_text())
        self.assertFalse(self.journals())

    def test_cleanup_failure_preserves_nonzero_test_status_or_exception(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                syncs = 0
                def failing_sync(command):
                    nonlocal syncs
                    if command == ["sync"]:
                        syncs += 1
                        if syncs == 2:
                            return subprocess.CompletedProcess(command, 9, "", "cleanup unavailable")
                    return self.execute(command)
                def run(arguments):
                    if raises:
                        raise subprocess.CalledProcessError(7, "playwright")
                    return 7
                if raises:
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        run_plant(self.workspace, self.env, self.contract, ["disable"], failing_sync, run)
                    self.assertEqual(failure.exception.returncode, 7)
                else:
                    self.assertEqual(run_plant(self.workspace, self.env, self.contract, ["disable"], failing_sync, run), 7)
                self.assertIn("cleanup unavailable", self.errors.getvalue())
                self.assertEqual(len(self.journals()), 1)
                self.assertIn("ready = true", self.source.read_text())
                run_plant(self.workspace, self.env, self.contract, ["--restore"], self.execute, lambda arguments: 0)

    def test_unconfirmed_test_cancellation_defers_source_and_copy_cleanup(self):
        class UnsafeCancellation(subprocess.CalledProcessError):
            plant_cleanup_safe = False
        def run(arguments):
            raise UnsafeCancellation(130, "playwright")
        with self.assertRaises(UnsafeCancellation):
            run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, run)
        self.assertIn("ready = false", self.source.read_text())
        self.assertIn("ready = false", self.copy.read_text())
        self.assertEqual(len(self.journals()), 1)
        self.assertEqual(self.calls, ["sync", "check", "fetch"])
        self.assertIn("test payload may still be running", self.errors.getvalue())
        run_plant(self.workspace, self.env, self.contract, ["--restore"], self.execute, lambda arguments: 0)
        self.assertIn("ready = true", self.source.read_text())

    def test_plant_replaces_hardlink_inode_without_mutating_other_worktree(self):
        donor = self.root / "donor.js"
        os.link(self.source, donor)
        def run(arguments):
            self.assertIn("ready = true", donor.read_text())
            self.assertIn("ready = false", self.source.read_text())
            return 0
        run_plant(self.workspace, self.env, self.contract, ["disable"], self.execute, run)
        self.assertEqual(self.source.read_bytes(), donor.read_bytes())
        self.assertNotEqual(self.source.stat().st_ino, donor.stat().st_ino)

    def test_profile_dry_run_detects_stale_copies_without_mutating_them(self):
        contract = load_contract(self.workspace, ROOT / "examples/flowbite-xor")
        command = ["php", "tools/sync-demo", "--dry-run"]
        original = self.copy.read_bytes()
        def execute(argv):
            self.assertEqual(argv, command)
            return subprocess.CompletedProcess(argv, 0, "[dry-run] recipe.js -> demo.js\n", "")
        with self.assertRaisesRegex(ValueError, "differing synced copies"):
            sync_contract(contract, execute, check=True)
        self.assertEqual(self.copy.read_bytes(), original)
        self.assertIn("recipe.js -> demo.js", self.output.getvalue())

    def test_project_contract_owns_commands_and_rejects_unsafe_or_unobserved_edits(self):
        (self.workspace / ".xorder").mkdir()
        path = self.workspace / ".xorder/testing.json"
        path.write_text(json.dumps(self.contract))
        self.assertEqual(load_contract(self.workspace, ROOT / "examples/flowbite-xor")["sync"]["command"], ["sync"])
        for unsafe in ("../outside.js", "/outside.js"):
            self.contract["plants"]["disable"]["edits"][0]["path"] = unsafe
            path.write_text(json.dumps(self.contract))
            with self.assertRaisesRegex(ValueError, "inside the workspace"):
                load_contract(self.workspace, ROOT / "examples/flowbite-xor")
        self.contract["plants"]["disable"]["edits"][0]["path"] = "recipe.js"
        self.contract["plants"]["disable"]["confirm"].pop("contains")
        path.write_text(json.dumps(self.contract))
        with self.assertRaisesRegex(ValueError, "assert served content"):
            load_contract(self.workspace, ROOT / "examples/flowbite-xor")


if __name__ == "__main__":
    unittest.main()
