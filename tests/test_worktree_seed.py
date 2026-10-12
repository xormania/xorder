"""Worktree seeding preserves isolation and refuses mismatched or existing inputs."""
import importlib.util
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
sys.path.insert(0, str(ROOT / "examples/uxor"))
spec = importlib.util.spec_from_file_location("worktree_seed", ROOT / "examples/uxor/seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class WorktreeSeedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = {"XDG_CACHE_HOME": str(self.root / "state")}
        self.source, self.target = self.root / "prepared checkout", self.root / "new checkout"
        for checkout in (self.source, self.target):
            (checkout / "demo").mkdir(parents=True)
            for name, value in {
                "package.json": '{"devDependencies":{"tool":"1.0.0"}}',
                "package-lock.json": '{"packages":{"node_modules/tool":{"version":"1.0.0"}}}',
                "demo/composer.json": '{"require-dev":{"vendor/tool":"1.0.0"}}',
                "demo/composer.lock": '{"packages-dev":[{"name":"vendor/tool","version":"1.0.0"}]}',
                "demo/symfony.lock": '{}', "demo/importmap.php": '<?php return [];',
            }.items():
                (checkout / name).write_text(value)
        self.paths = ["demo/assets/vendor", "demo/vendor", "node_modules"]
        for path in self.paths:
            (self.source / path).mkdir(parents=True)
            (self.source / path / "metadata").write_text("installed bytes\n")
        (self.source / "node_modules/tool").mkdir()
        (self.source / "node_modules/tool/cli").write_text("#!/bin/sh\nexit 0\n")
        (self.source / "node_modules/tool/cli").chmod(0o755)
        (self.source / "node_modules/bin").symlink_to("tool/cli")
        (self.source / "demo/var").mkdir()
        (self.source / "demo/var/runner-output").write_text("must remain private")

    def test_default_private_seed_needs_no_docker_and_preserves_modes_and_links(self):
        with patch.object(seed, "require_stopped", side_effect=AssertionError("private seed must not inspect Docker")):
            self.assertEqual(seed.seed(self.target, self.source, env=self.env), 0)
        original, copied = self.source / "demo/vendor/metadata", self.target / "demo/vendor/metadata"
        self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)
        copied.write_text("receiver changes")
        self.assertEqual(original.read_text(), "installed bytes\n")
        self.assertEqual((self.target / "node_modules/tool/cli").stat().st_mode & 0o777, 0o755)
        self.assertEqual(os.readlink(self.target / "node_modules/bin"), "tool/cli")
        self.assertFalse((self.target / "demo/var").exists())
        self.assertEqual(seed.shared_paths(self.source, self.env), [])
        self.assertEqual(seed.shared_paths(self.target, self.env), [])

    def test_host_guard_survives_deleted_or_changed_project_marker(self):
        with patch.object(seed, "require_stopped"):
            seed.seed(self.target, self.source, env=self.env, hardlink=True)
        marker = self.target / seed.SHARING_RECEIPT
        marker.unlink()
        with self.assertRaisesRegex(ValueError, "authoritative host guard"):
            seed.shared_paths(self.target, self.env)
        marker.write_text(json.dumps({"schema": 1, "paths": ["node_modules"]}))
        with self.assertRaisesRegex(ValueError, "authoritative host guard"):
            seed.shared_paths(self.target, self.env)
        self.assertTrue(seed.sharing_guard(self.target, self.env).is_file())
        self.assertEqual(seed.shared_paths(self.source, self.env), self.paths)
        with self.assertRaisesRegex(ValueError, "Remove the guarded"):
            seed.forget_sharing(self.target, self.env)
        for path in self.paths:
            shutil.rmtree(self.target / path)
        marker.unlink()
        with patch.object(seed, "require_stopped"):
            seed.forget_sharing(self.target, self.env)
        self.assertFalse(seed.sharing_guard(self.target, self.env).exists())
        self.assertEqual(seed.shared_paths(self.target, self.env), [])
        self.assertEqual(seed.shared_paths(self.source, self.env), self.paths)

    def test_local_marker_without_a_host_guard_fails_closed(self):
        (self.target / seed.SHARING_RECEIPT).write_text(json.dumps({"schema": 1, "paths": self.paths}))
        with self.assertRaisesRegex(ValueError, "no authoritative host guard"):
            seed.shared_paths(self.target, self.env)

    def test_host_guard_cannot_be_stored_in_either_checkout(self):
        with self.assertRaisesRegex(ValueError, "outside the checkout"):
            seed.seed(self.target, self.source, env={"XDG_CACHE_HOME": str(self.source / "state")}, hardlink=True)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))

    def test_local_git_exclusion_is_idempotent_for_linked_worktrees(self):
        subprocess.run(["git", "init", str(self.source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.source), "add", "package.json"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=xormania", "-c", "user.email=xormania@users.noreply.github.com", "commit", "-m", "Fixture"], check=True, capture_output=True)
        linked = self.root / "linked checkout"
        subprocess.run(["git", "-C", str(self.source), "worktree", "add", "--detach", str(linked)], check=True, capture_output=True)
        for workspace in (self.source, linked):
            (workspace / seed.SHARING_RECEIPT).write_text("local state")
            seed.exclude_local_receipt(workspace, self.env)
            seed.exclude_local_receipt(workspace, self.env)
            output = subprocess.run(["git", "-C", str(workspace), "status", "--porcelain", "--untracked-files=all"], check=True, capture_output=True, text=True).stdout
            self.assertNotIn(seed.SHARING_RECEIPT, output)
        exclude = self.source / ".git/info/exclude"
        self.assertEqual(exclude.read_text().splitlines().count("/" + seed.SHARING_RECEIPT), 1)

    def test_every_selected_manifest_lock_and_importmap_must_match_before_writes(self):
        for name in ("package.json", "package-lock.json", "demo/composer.json", "demo/composer.lock", "demo/symfony.lock", "demo/importmap.php"):
            with self.subTest(name=name):
                file = self.target / name
                original = file.read_bytes()
                file.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "inputs are missing or differ"):
                    seed.seed(self.target, self.source, env=self.env, hardlink=True)
                file.write_bytes(original)
                self.assertFalse(any((self.target / path).exists() for path in self.paths))
                self.assertFalse((self.source / seed.SHARING_RECEIPT).exists())

    def test_existing_empty_directory_and_symlink_destinations_are_never_replaced(self):
        target = self.target / "node_modules"
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            seed.seed(self.target, self.source, env=self.env)
        self.assertEqual(list(target.iterdir()), [])
        target.rmdir()
        target.symlink_to(self.source / "node_modules", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            seed.seed(self.target, self.source, env=self.env)
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.target / "demo/vendor").exists())

    def test_hardlinks_guard_both_workspaces_without_chmod_on_shared_files(self):
        with patch.object(seed, "require_stopped") as stopped:
            seed.seed(self.target, self.source, env=self.env, hardlink=True)
            self.assertEqual(stopped.call_count, 2)
        for checkout in (self.source, self.target):
            self.assertEqual(seed.shared_paths(checkout, self.env), self.paths)
        original, shared = self.source / "demo/vendor/metadata", self.target / "demo/vendor/metadata"
        self.assertEqual(original.stat().st_ino, shared.stat().st_ino)
        self.assertEqual(original.stat().st_mode & 0o777, 0o644)

    def test_docker_observation_timeout_fails_before_hardlink_mutations(self):
        with patch.object(seed.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker ps", 0.1)):
            with self.assertRaisesRegex(ValueError, "ownership observation exceeded"):
                seed.seed(self.target, self.source, env=dict(self.env, XORDER_OBSERVE_TIMEOUT_SECONDS="0.1"), hardlink=True)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))
        self.assertFalse(seed.sharing_guard(self.source, self.env).exists())

    def test_legacy_running_container_mounts_refuse_hardlinks_before_any_changes(self):
        calls = [subprocess.CompletedProcess([], 0, "legacy\n", ""),
                 subprocess.CompletedProcess([], 0, json.dumps([{"Name": "legacy writable stack", "Mounts": [{"Type": "bind", "Source": str(self.source)}]}]), "")]
        with patch.object(seed.subprocess, "run", side_effect=calls):
            with self.assertRaisesRegex(ValueError, "Stop containers"):
                seed.seed(self.target, self.source, env=self.env, hardlink=True)
        self.assertFalse((self.source / seed.SHARING_RECEIPT).exists())
        self.assertFalse((self.target / "node_modules").exists())

    def test_donor_symlink_cannot_refer_to_another_checkout_or_absolute_path(self):
        link = self.source / "node_modules/leaving"
        for target in (str(self.target / "package.json"), "../../new checkout/package.json"):
            with self.subTest(target=target):
                link.symlink_to(target)
                with self.assertRaisesRegex(ValueError, "symlink leaves"):
                    seed.seed(self.target, self.source, env=self.env)
                link.unlink()
                self.assertFalse((self.target / "node_modules").exists())

    def test_changed_source_snapshot_or_lock_does_not_publish_partial_dependencies(self):
        original_copy = seed.copy_tree
        def changed_copy(source, target, hardlink):
            (source / "metadata").write_text("changed while copying")
            original_copy(source, target, hardlink)
        with patch.object(seed, "copy_tree", side_effect=changed_copy):
            with self.assertRaisesRegex(ValueError, "changed while copying"):
                seed.seed(self.target, self.source, env=self.env)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))
        for path in self.paths:
            (self.source / path / "metadata").write_text("installed bytes\n")
        def changed_lock(source, target, hardlink):
            original_copy(source, target, hardlink)
            (self.source / "package-lock.json").write_text("changed lock")
        with patch.object(seed, "copy_tree", side_effect=changed_lock):
            with self.assertRaisesRegex(ValueError, "inputs are missing or differ"):
                seed.seed(self.target, self.source, env=self.env)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))

    def test_destination_race_keeps_competing_directory_and_rolls_back_guards(self):
        original_promote = seed.promote
        def raced_promote(staged, destination):
            destination.mkdir()
            (destination / "other-owner").write_text("do not overwrite")
            original_promote(staged, destination)
        with patch.object(seed, "require_stopped"), patch.object(seed, "promote", side_effect=raced_promote):
            with self.assertRaisesRegex(ValueError, "appeared during staging"):
                seed.seed(self.target, self.source, env=self.env, hardlink=True)
        self.assertEqual((self.target / self.paths[0] / "other-owner").read_text(), "do not overwrite")
        self.assertFalse((self.source / seed.SHARING_RECEIPT).exists())
        self.assertFalse((self.target / seed.SHARING_RECEIPT).exists())
        self.assertFalse((self.target / "node_modules").exists())

    def test_private_seed_cannot_publish_a_root_redirected_after_snapshot(self):
        outside = self.root / "outside dependencies"
        shutil.copytree(self.source / self.paths[0], outside)
        original_copy = seed.copy_tree
        def redirected_copy(source, target, hardlink):
            if source == self.source / self.paths[0]:
                shutil.rmtree(source)
                source.symlink_to(outside, target_is_directory=True)
            original_copy(source, target, hardlink)
        with patch.object(seed, "copy_tree", side_effect=redirected_copy):
            with self.assertRaisesRegex(ValueError, "staged dependency root is redirected"):
                seed.seed(self.target, self.source, env=self.env)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))

    def test_donor_changed_after_copy_is_rechecked_before_any_publication(self):
        original_copy = seed.copy_tree
        def changed_after_copy(source, target, hardlink):
            original_copy(source, target, hardlink)
            (source / "metadata").write_text("changed after copy")
        with patch.object(seed, "copy_tree", side_effect=changed_after_copy):
            with self.assertRaisesRegex(ValueError, "source changed during staging"):
                seed.seed(self.target, self.source, env=self.env)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))

    def test_hardlink_stage_must_still_share_the_current_canonical_donor_inode(self):
        original_copy = seed.copy_tree
        def replaced_inode(source, target, hardlink):
            original_copy(source, target, hardlink)
            file = source / "metadata"
            replacement = source / "metadata.new"
            replacement.write_bytes(file.read_bytes())
            replacement.chmod(file.stat().st_mode & 0o777)
            replacement.replace(file)
        with patch.object(seed, "require_stopped"), patch.object(seed, "copy_tree", side_effect=replaced_inode):
            with self.assertRaisesRegex(ValueError, "donor inode changed"):
                seed.seed(self.target, self.source, env=self.env, hardlink=True)
        self.assertFalse(any((self.target / path).exists() for path in self.paths))
        self.assertFalse((self.source / seed.SHARING_RECEIPT).exists())
        self.assertFalse((self.target / seed.SHARING_RECEIPT).exists())

    def test_custom_importmap_paths_are_verified_and_checkout_escapes_rejected(self):
        for checkout in (self.source, self.target):
            (checkout / "demo/map.php").write_text("custom map")
        (self.source / "demo/custom-assets").mkdir()
        (self.source / "demo/custom-assets/installed.php").write_text("metadata")
        seed.seed(self.target, self.source, env=dict(self.env, IMPORTMAP_FILE="map.php", IMPORTMAP_VENDOR_DIR="custom-assets"))
        self.assertTrue((self.target / "demo/custom-assets/installed.php").is_file())
        self.assertFalse((self.target / "demo/assets/vendor").exists())
        for environment in ({"IMPORTMAP_FILE": "../map.php"}, {"IMPORTMAP_FILE": "/map.php"}, {"IMPORTMAP_VENDOR_DIR": "../outside"}):
            with self.subTest(environment=environment), self.assertRaisesRegex(ValueError, "relative inside demo"):
                seed.seed(self.target, self.source, env=dict(self.env, **environment))


if __name__ == "__main__":
    unittest.main()
