"""Dependency snapshots repair corrupt members and prune only owned, idle caches."""
from contextlib import redirect_stdout
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cache_maintenance", ROOT / "examples/flowbite-xor/cache.py")
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class SnapshotMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "checkout/demo"
        self.vendor = self.project / "vendor"
        self.vendor.mkdir(parents=True)
        (self.vendor / "autoload.php").write_text("verified bytes")
        (self.project / "composer.json").write_text("{}")
        (self.project / "composer.lock").write_text("{}")
        self.directory = self.root / "snapshots"
        self.directory.mkdir()
        self.key = "a" * 64
        self.archive = self.directory / ("vendor-" + self.key + ".zip")
        cache.write_archive(self.vendor, self.archive, self.key)

    def test_store_repairs_corrupt_members_even_when_manifest_is_unchanged(self):
        with zipfile.ZipFile(self.archive) as source:
            members = {name: source.read(name) for name in source.namelist()}
        members["files/autoload.php"] = b"bad member with intact manifest"
        with zipfile.ZipFile(self.archive, "w") as output:
            for name, data in members.items():
                output.writestr(name, data)
        self.assertTrue(cache.write_archive(self.vendor, self.archive, self.key))
        self.assertTrue(cache.validate_archive(self.archive, self.key))
        quarantined = list(self.directory.glob(self.archive.name + ".corrupt-*"))
        self.assertEqual(len(quarantined), 1)
        with self.assertRaisesRegex(ValueError, "checksum"):
            cache.validate_archive(quarantined[0], self.key)
        target = self.root / "receiver/demo/vendor"
        cache.restore_archive(self.archive, target, self.key, self.root / "receiver")
        self.assertEqual((target / "autoload.php").read_text(), "verified bytes")

    def test_invalid_deflate_stream_is_quarantined_and_repaired(self):
        with zipfile.ZipFile(self.archive) as source:
            member = source.getinfo("files/autoload.php")
        data = bytearray(self.archive.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", data, member.header_offset + 26)
        offset = member.header_offset + 30 + name_length + extra_length
        # BFINAL=1/BTYPE=3 is a reserved raw-deflate block type. The ZIP
        # manifest and member metadata remain readable and unchanged.
        data[offset] = 0x07
        self.archive.write_bytes(data)
        self.assertTrue(cache.write_archive(self.vendor, self.archive, self.key))
        self.assertEqual(len(list(self.directory.glob(self.archive.name + ".corrupt-*"))), 1)
        self.assertTrue(cache.validate_archive(self.archive, self.key))

    def test_restored_relative_symlink_cannot_escape_via_existing_workspace_alias(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret").write_text("outside workspace")
        (self.project.parent / "alias").symlink_to(outside, target_is_directory=True)
        (self.vendor / "leaving").symlink_to("../../alias/secret")
        cache.write_archive(self.vendor, self.archive, self.key)
        shutil.rmtree(self.vendor)
        with self.assertRaisesRegex(ValueError, "leaves the mounted workspace"):
            cache.restore_archive(self.archive, self.vendor, self.key, self.project.parent)
        self.assertFalse(self.vendor.exists())

    def test_archive_symlink_topology_cannot_escape_after_alias_expansion(self):
        # Individually normalized targets stay inside the checkout. Their
        # combined OS interpretation expands alias before '..' and escapes.
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr("manifest.json", json.dumps({"schema": 1, "identity": self.key,
                "files": {"alias": {"link": "../../"}, "file": {"link": "alias/../outside"}}}))
        shutil.rmtree(self.vendor)
        with self.assertRaisesRegex(ValueError, "leaves the mounted workspace"):
            cache.restore_archive(self.archive, self.vendor, self.key, self.project.parent)
        self.assertFalse(self.vendor.exists())

    def test_import_validates_link_topology_at_final_location_before_key_promotion(self):
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr("manifest.json", json.dumps({"schema": 1, "identity": self.key,
                "files": {"alias": {"link": "../../"}, "file": {"link": "alias/../outside"}}}))
        bundle = self.root / "bundle.zip"
        with zipfile.ZipFile(bundle, "w") as output:
            output.write(self.archive, self.archive.name)
        shutil.rmtree(self.vendor)
        destination = self.root / "receiver-cache"
        destination.mkdir()
        with patch.object(cache, "identity", return_value=self.key), self.assertRaisesRegex(ValueError, "leaves the mounted workspace"):
            cache.main(["import", "--project", str(self.project), "--cache", str(destination),
                        "--input", str(bundle), "--sha256", cache.sha(bundle)])
        self.assertEqual(list(destination.glob("*.zip")), [])
        self.assertFalse(self.vendor.exists())

    def test_safe_internal_link_topology_is_preserved_and_cycles_are_rejected(self):
        (self.project.parent / "shared").write_text("inside checkout")
        shutil.rmtree(self.vendor)
        files = {"alias": {"link": "../../"}, "file": {"link": "alias/demo/../shared"}}
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr("manifest.json", json.dumps({"schema": 1, "identity": self.key, "files": files}))
        self.assertTrue(cache.restore_archive(self.archive, self.vendor, self.key, self.project.parent))
        self.assertEqual((self.vendor / "file").read_text(), "inside checkout")
        self.assertEqual(os.readlink(self.vendor / "file"), "alias/demo/../shared")
        shutil.rmtree(self.vendor)
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr("manifest.json", json.dumps({"schema": 1, "identity": self.key,
                "files": {"a": {"link": "b"}, "b": {"link": "a"}}}))
        with self.assertRaisesRegex(ValueError, "loop or too many"):
            cache.restore_archive(self.archive, self.vendor, self.key, self.project.parent)
        self.assertFalse(self.vendor.exists())

    def test_valid_unchanged_archive_is_reused_and_ambiguous_members_are_rejected(self):
        original = self.archive.read_bytes()
        cache.write_archive(self.vendor, self.archive, self.key)
        self.assertEqual(self.archive.read_bytes(), original)
        with zipfile.ZipFile(self.archive, "a") as output:
            output.writestr("files/unowned", "unowned archive payload")
        with self.assertRaisesRegex(ValueError, "members differ"):
            cache.validate_archive(self.archive, self.key)
        cache.write_archive(self.vendor, self.archive, self.key)
        self.assertTrue(cache.validate_archive(self.archive, self.key))

    def test_obsolete_snapshot_pruning_preserves_current_unknown_and_redirected_files(self):
        obsolete = self.directory / ("vendor-" + "b" * 64 + ".zip")
        obsolete.write_bytes(self.archive.read_bytes())
        quarantine = self.directory / (self.archive.name + ".corrupt-" + "c" * 32)
        quarantine.write_bytes(b"corrupt archive")
        foreign = self.directory / "notes.zip"
        foreign.write_bytes(b"another tool owns this")
        outside = self.root / "outside.zip"
        outside.write_bytes(b"do not follow")
        redirected = self.directory / ("vendor-" + "d" * 64 + ".zip")
        redirected.symlink_to(outside)
        arguments = ["prune", "--project", str(self.project), "--cache", str(self.directory)]
        with patch.object(cache, "identity", return_value=self.key), redirect_stdout(io.StringIO()) as output:
            cache.main(arguments)
        report = json.loads(output.getvalue())
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["reclaimable_bytes"], obsolete.stat().st_size + quarantine.stat().st_size)
        self.assertTrue(obsolete.exists())
        with patch.object(cache, "identity", return_value=self.key), redirect_stdout(io.StringIO()) as output:
            cache.main([*arguments, "--apply"])
        self.assertEqual(set(json.loads(output.getvalue())["removed"]), {obsolete.name, quarantine.name})
        self.assertTrue(self.archive.exists())
        self.assertEqual(foreign.read_bytes(), b"another tool owns this")
        self.assertTrue(redirected.is_symlink())
        self.assertEqual(outside.read_bytes(), b"do not follow")

    def test_usage_records_last_use_without_claiming_a_restored_installation(self):
        with patch.object(cache, "identity", return_value=self.key):
            cache.main(["store", "--project", str(self.project), "--cache", str(self.directory)])
        usage = json.loads((self.directory / "usage.json").read_text())["snapshots"][self.archive.name]
        self.assertEqual(usage["action"], "store")
        self.assertGreater(usage["last_used"], 0)

    def test_authenticated_bundle_must_match_all_selected_keys_before_cache_promotion(self):
        (self.project / "importmap.php").write_text("<?php return [];")
        bundle = self.root / "bundle.zip"
        with zipfile.ZipFile(bundle, "w") as output:
            output.write(self.archive, self.archive.name)
        destination = self.root / "receiver-cache"
        destination.mkdir()
        with patch.object(cache, "identity", return_value=self.key), self.assertRaisesRegex(ValueError, "exact importmap snapshot"):
            cache.main(["import", "--project", str(self.project), "--cache", str(destination),
                        "--input", str(bundle), "--sha256", cache.sha(bundle)])
        self.assertEqual(list(destination.glob("*.zip")), [])


class OrphanCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache_root = self.root / "cache"
        self.workspace = self.root / "absent checkout"
        self.repository = self.root / "repo/.git"
        scope = hashlib.sha256(str(self.repository).encode()).hexdigest()
        key = hashlib.sha256(str(self.workspace).encode()).hexdigest()
        self.directory = self.cache_root / scope / key
        self.directory.mkdir(parents=True)
        cache.register_workspace_cache(self.directory, self.workspace, self.repository, downloads=True)
        (self.directory / "composer-downloads").mkdir()
        (self.directory / "composer-downloads/package.zip").write_bytes(b"owned download")
        (self.directory / ("vendor-" + "a" * 64 + ".zip")).write_bytes(b"owned snapshot")

    def run_maintenance(self, containers=(), apply=False):
        with patch.object(cache, "cache_containers", return_value=list(containers)), redirect_stdout(io.StringIO()) as output:
            status = cache.orphan_cache_usage(self.cache_root, dict(os.environ), apply=apply)
        return status, json.loads(output.getvalue())

    def test_dry_run_accounts_for_snapshot_and_download_bytes_without_changes(self):
        before = {path.relative_to(self.directory): path.read_bytes() for path in self.directory.rglob("*") if path.is_file()}
        status, report = self.run_maintenance()
        self.assertEqual(status, 0)
        self.assertGreater(report["reclaimable_bytes"], 0)
        self.assertEqual(report["removed"], [])
        after = {path.relative_to(self.directory): path.read_bytes() for path in self.directory.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        status, report = self.run_maintenance(apply=True)
        self.assertEqual(status, 0)
        self.assertEqual(report["removed"], [str(self.directory)])
        self.assertFalse(self.directory.exists())

    def test_live_workspace_and_any_container_bind_protect_the_cache(self):
        self.workspace.mkdir()
        _, report = self.run_maintenance(apply=True)
        self.assertEqual(report["reclaimable_bytes"], 0)
        self.assertTrue(self.directory.exists())
        self.workspace.rmdir()
        for source in (self.directory, self.workspace, self.cache_root):
            with self.subTest(source=source):
                container = {"Id": "unlabelled-stopped", "State": {"Running": False}, "Mounts": [{"Type": "bind", "Source": str(source)}]}
                _, report = self.run_maintenance([container], apply=True)
                self.assertEqual(report["reclaimable_bytes"], 0)
                self.assertTrue(self.directory.exists())

    def test_unknown_and_symlink_cache_entries_are_preserved(self):
        foreign = self.directory / "another-tool-state"
        foreign.write_text("unowned")
        status, report = self.run_maintenance(apply=True)
        self.assertEqual(status, 1)
        self.assertIn("unowned", report["blocked"][0])
        self.assertEqual(foreign.read_text(), "unowned")
        foreign.unlink()
        downloads = self.directory / "composer-downloads"
        shutil.rmtree(downloads)
        outside = self.root / "external cache"
        outside.mkdir()
        (outside / "do-not-delete").write_text("preserve")
        downloads.symlink_to(outside)
        status, report = self.run_maintenance(apply=True)
        self.assertEqual(status, 1)
        self.assertEqual((outside / "do-not-delete").read_text(), "preserve")

    def test_apply_rechecks_mounts_and_snapshot_lock(self):
        appeared = {"Id": "new-import", "Mounts": [{"Type": "bind", "Source": str(self.directory)}]}
        with patch.object(cache, "cache_containers", side_effect=[[], [appeared]]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cache.orphan_cache_usage(self.cache_root, dict(os.environ), apply=True), 1)
        self.assertIn("now references", json.loads(output.getvalue())["blocked"][0])
        self.assertTrue(self.directory.exists())
        with (self.directory / "snapshots.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            status, report = self.run_maintenance(apply=True)
        self.assertEqual(status, 1)
        self.assertIn("active snapshot", report["blocked"][0])
        self.assertTrue(self.directory.exists())

    def test_no_docker_evidence_never_removes_an_orphan(self):
        with patch.object(cache, "cache_containers", side_effect=OSError("daemon down")), redirect_stdout(io.StringIO()) as output:
            status = cache.orphan_cache_usage(self.cache_root, dict(os.environ), apply=True)
        self.assertEqual(status, 1)
        self.assertIn("Cannot establish", json.loads(output.getvalue())["blocked"][0])
        self.assertTrue(self.directory.exists())

    def test_registration_keeps_ownership_when_explicit_download_cache_is_selected(self):
        cache.register_workspace_cache(self.directory, self.workspace, self.repository, downloads=False)
        self.assertEqual(json.loads((self.directory / "workspace.json").read_text())["owned_directories"], ["composer-downloads"])


if __name__ == "__main__":
    unittest.main()
