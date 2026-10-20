"""Target file ownership and recovery through real staged artifact bytes."""
import copy
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from xorder import apply as application, model
from xorder.resolve import resolve
from test_resources import definition, record, profile


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.state = self.base / "state"
        self.cache = self.base / "cache"
        self.cache.mkdir()
        self.target = {"platform": "linux/amd64", "commands": [], "scope": "project", "harness": "codex"}

    def selection(self, files=None, revision="1.0.0", targets=None):
        files = files or {".editorconfig": b"root = true\n"}
        d = definition("editor", "configuration", revision)
        if targets is not None:
            d["targets"] = targets
        d["details"]["files"] = [{"source": f"file-{i}", "destination": name} for i, name in enumerate(files)]
        archive = self.base / (revision + ".tar")
        with tarfile.open(archive, "w") as tar:
            for i, content in enumerate(files.values()):
                member = tarfile.TarInfo(f"file-{i}")
                member.size = len(content)
                member.mode = 0o644
                tar.addfile(member, io.BytesIO(content))
        checksum = application.digest(archive)
        (self.cache / checksum).write_bytes(archive.read_bytes())
        r = record(d)
        r["publication"].update(sha256=checksum, filename="editor.tar", size_bytes=archive.stat().st_size)
        cat = {"schema_version": 2, "generated_at": r["created_at"], "resources": [model.artifact_entry(r)]}
        lock = resolve(profile(d["id"]), cat, self.target)["lock"]
        return lock, cat

    def install(self, lock, cat):
        return application.apply(lock, self.root, self.state, self.cache, cat)

    def test_apply_repeat_and_verify_without_touching_unrelated_files(self):
        self.root.mkdir()
        unrelated = self.root / "keep.txt"
        unrelated.write_text("user content")
        lock, cat = self.selection()
        self.assertEqual(self.install(lock, cat)["status"], "applied")
        destination = self.root / ".editorconfig"
        before = destination.stat().st_mtime_ns
        self.assertEqual(self.install(lock, cat)["status"], "unchanged")
        self.assertEqual(destination.stat().st_mtime_ns, before)
        self.assertEqual(unrelated.read_text(), "user content")
        self.assertEqual(application.verify(self.root, self.state)["status"], "passed")

    def test_platform_independent_selection_plans_and_applies_without_platform(self):
        self.target.pop("platform")
        lock, cat = self.selection(targets=["any"])
        self.assertEqual(application.plan(lock, self.root, self.state, cat)["status"], "ready")
        self.assertEqual(self.install(lock, cat)["status"], "applied")
        self.assertEqual((self.root / ".editorconfig").read_bytes(), b"root = true\n")
        self.assertEqual(application.verify(self.root, self.state)["status"], "passed")

    def test_published_editorconfig_plan_uses_the_same_platform_contract_as_resolution(self):
        cat = model.catalog()
        lock = resolve(profile("configuration/editorconfig"), cat, {"scope": "project"})["lock"]
        result = application.plan(lock, self.root, self.state, cat)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["actions"][0]["destination"], ".editorconfig")

    def test_recorded_platform_changes_stop_plan_and_apply_before_writes(self):
        lock, cat = self.selection(targets=["any"])
        with patch.object(application.platform, "system", return_value="Linux"), \
                patch.object(application.platform, "machine", return_value="aarch64"):
            for result in (application.plan(lock, self.root, self.state, cat), self.install(lock, cat)):
                self.assertEqual(result["status"], "prerequisite_missing")
                self.assertEqual(result["gaps"], [{"code": "target_changed", "expected": "linux/amd64", "actual": "linux/arm64"}])
        self.assertFalse(self.root.exists())
        self.assertFalse(self.state.exists())

    def test_platform_specific_lock_cannot_omit_observed_platform(self):
        lock, cat = self.selection()
        lock["target"].pop("platform")
        for action in (lambda: application.plan(lock, self.root, self.state, cat), lambda: self.install(lock, cat)):
            with self.assertRaisesRegex(ValueError, "incompatible"):
                action()
        self.assertFalse(self.root.exists())
        self.assertFalse(self.state.exists())

    def test_unowned_and_locally_edited_destinations_are_preserved(self):
        lock, cat = self.selection()
        self.root.mkdir()
        destination = self.root / ".editorconfig"
        destination.write_text("unowned")
        self.assertEqual(self.install(lock, cat)["status"], "conflict")
        self.assertEqual(destination.read_text(), "unowned")
        destination.unlink()
        self.install(lock, cat)
        destination.write_text("locally edited")
        new, newer = self.selection({".editorconfig": b"replacement"}, "1.1.0")
        self.assertEqual(self.install(new, newer)["status"], "conflict")
        self.assertEqual(application.remove(self.root, ["configuration/editor"], self.state, self.cache)["status"], "conflict")
        self.assertEqual(destination.read_text(), "locally edited")

    def test_update_and_rollback_restore_retained_exact_bytes(self):
        lock, cat = self.selection()
        self.install(lock, cat)
        newer, newcat = self.selection({".editorconfig": b"changed defaults\n"}, "1.1.0")
        self.install(newer, newcat)
        self.assertEqual((self.root / ".editorconfig").read_bytes(), b"changed defaults\n")
        self.assertEqual(application.rollback(self.root, self.state, self.cache)["status"], "recovered")
        self.assertEqual((self.root / ".editorconfig").read_bytes(), b"root = true\n")
        self.assertEqual(application.verify(self.root, self.state)["status"], "passed")

    def test_mode_edits_are_preserved_by_apply_and_remove(self):
        lock, cat = self.selection()
        self.install(lock, cat)
        path = self.root / ".editorconfig"
        path.chmod(0o755)
        self.assertEqual(self.install(lock, cat)["status"], "conflict")
        self.assertEqual(application.remove(self.root, ["configuration/editor"], self.state, self.cache)["status"], "conflict")
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_repeat_restores_missing_owned_file(self):
        lock, cat = self.selection()
        self.install(lock, cat)
        (self.root / ".editorconfig").unlink()
        self.assertEqual(self.install(lock, cat)["status"], "applied")
        self.assertEqual(application.verify(self.root, self.state)["status"], "passed")

    def test_interruption_requires_recovery_and_can_restore_before_state(self):
        lock, cat = self.selection({"one": b"first", "two": b"second"})
        original = application._replace
        calls = 0
        def interrupted(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return original(*args)
        with patch.object(application, "_replace", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.install(lock, cat)
        self.assertEqual(application.verify(self.root, self.state)["status"], "recovery_required")
        self.assertEqual(self.install(lock, cat)["status"], "recovery_required")
        self.assertEqual(application.recover(self.root, self.state, self.cache)["status"], "recovered")
        self.assertFalse((self.root / "one").exists())
        self.assertFalse((self.root / "two").exists())
        self.assertEqual(self.install(lock, cat)["status"], "applied")

    def test_recovery_preserves_edit_made_after_interruption(self):
        lock, cat = self.selection({"one": b"first", "two": b"second"})
        original = application._replace
        def interrupted(root, name, cache, metadata):
            if name == "two":
                raise KeyboardInterrupt()
            return original(root, name, cache, metadata)
        with patch.object(application, "_replace", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            self.install(lock, cat)
        (self.root / "one").write_text("user edit")
        result = application.recover(self.root, self.state, self.cache)
        self.assertEqual(result["status"], "recovery_conflict")
        self.assertEqual((self.root / "one").read_text(), "user edit")
        self.assertEqual(application.verify(self.root, self.state)["status"], "recovery_required")

    def test_destination_created_during_staging_is_not_adopted(self):
        lock, cat = self.selection()
        self.root.mkdir()
        original = application.unpack
        def late_file(*args, **kwargs):
            (self.root / ".editorconfig").write_text("created during staging")
            return original(*args, **kwargs)
        with patch.object(application, "unpack", side_effect=late_file), self.assertRaises(application.Conflict):
            self.install(lock, cat)
        self.assertEqual((self.root / ".editorconfig").read_text(), "created during staging")

    def test_symlink_destination_never_changes_outside_target(self):
        lock, cat = self.selection({"nested/config": b"managed"})
        self.root.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "config").write_text("outside")
        (self.root / "nested").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.install(lock, cat)["status"], "conflict")
        self.assertEqual((outside / "config").read_text(), "outside")

    def test_local_edit_during_backup_is_not_adopted(self):
        lock, cat = self.selection()
        self.install(lock, cat)
        newer, newcat = self.selection({".editorconfig": b"replacement"}, "1.1.0")
        original = application._blob
        def edited(path, cache):
            if Path(path) == self.root / ".editorconfig":
                Path(path).write_text("edited during backup")
            return original(path, cache)
        with patch.object(application, "_blob", side_effect=edited), self.assertRaises(application.Conflict):
            self.install(newer, newcat)
        self.assertEqual((self.root / ".editorconfig").read_text(), "edited during backup")

    def test_edited_lock_destinations_are_rejected_against_catalog(self):
        lock, cat = self.selection()
        edited = copy.deepcopy(lock)
        edited["resources"][0]["details"]["files"][0]["destination"] = "other"
        with self.assertRaises(ValueError):
            self.install(edited, cat)
        self.assertFalse(self.root.exists())

    def test_corrupt_cached_payload_is_retrieved_again_before_use(self):
        lock, cat = self.selection()
        delivery = lock["resources"][0]["delivery"]
        cached = self.cache / delivery["sha256"]
        correct = cached.read_bytes()
        cached.write_bytes(b"corrupt")
        def retrieve(url, destination, checksum):
            Path(destination).write_bytes(correct)
            self.assertEqual(application.digest(destination), checksum)
        with patch.object(application, "download", side_effect=retrieve) as downloaded:
            self.assertEqual(self.install(lock, cat)["status"], "applied")
            downloaded.assert_called_once()

    def test_remove_only_owned_files_and_rollback_removal(self):
        lock, cat = self.selection()
        self.install(lock, cat)
        (self.root / "user.txt").write_text("leave me")
        self.assertEqual(application.remove(self.root, ["configuration/editor"], self.state, self.cache)["status"], "applied")
        self.assertFalse((self.root / ".editorconfig").exists())
        self.assertEqual((self.root / "user.txt").read_text(), "leave me")
        self.assertEqual(application.rollback(self.root, self.state, self.cache)["status"], "recovered")
        self.assertEqual((self.root / ".editorconfig").read_bytes(), b"root = true\n")

    def test_overlapping_application_is_blocked(self):
        lock, cat = self.selection()
        _, state, _ = application.locations(self.root, self.state, self.cache)
        with application.target_lock(state), self.assertRaises(application.Conflict):
            self.install(lock, cat)
