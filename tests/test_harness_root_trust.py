"""Root startup must preserve the prior persistent-state trust boundary."""
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "images/harness-live/root_trust.py"
SPEC = importlib.util.spec_from_file_location("harness_root_trust", SOURCE)
root_trust = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(root_trust)


def snapshot(directory):
    """Record actual ownership, permissions and bytes before a rejected startup."""
    result = {}
    for path in [directory, *sorted(directory.rglob("*"))]:
        info = path.lstat()
        value = {"uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}
        if path.is_symlink():
            value["link"] = os.readlink(path)
        elif path.is_file():
            value["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        result[str(path.relative_to(directory))] = value
    return result


@unittest.skipUnless(os.geteuid() == 0, "Requires actual root ownership and chown checks")
class HarnessRootTrustTests(unittest.TestCase):
    def setUp(self):
        # HOME itself cannot have a writable /tmp ancestor; test that rule separately.
        self.temporary = tempfile.TemporaryDirectory(prefix="xorder-root-trust-", dir="/root")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.home.mkdir(mode=0o700)
        self.store = self.home / ".local/share/xorder/harnesses"
        self.store.mkdir(parents=True)
        self.selected = self.store / "selected.json"
        self.selected.write_text('{"harnesses":{}}\n')
        self.environment = patch.dict(os.environ, {"PUID": "0", "HARNESS_ROOT": str(self.store)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def lower_uid_owns(self, path, *, link=False):
        try:
            (os.lchown if link else os.chown)(path, 1000, 1000)
        except OSError as error:
            if error.errno in (errno.EINVAL, errno.EPERM):
                self.skipTest("This runtime does not map UID/GID 1000; exercised in root container readiness")
            raise

    def rejected_without_mutation(self, expected):
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, expected):
            root_trust.startup(self.home)
        self.assertEqual(snapshot(self.base), before)

    def test_nonroot_home_is_rejected_before_ownership_or_bytes_change(self):
        self.lower_uid_owns(self.home)
        self.lower_uid_owns(self.selected)
        self.rejected_without_mutation("root-owned.*dedicated root-owned HOME")
        self.assertEqual(self.home.stat().st_uid, 1000)
        self.assertEqual(self.selected.stat().st_uid, 1000)

    def test_root_home_with_lower_uid_selected_file_is_rejected(self):
        self.lower_uid_owns(self.selected)
        self.rejected_without_mutation("root-owned")
        self.assertEqual(self.home.stat().st_uid, 0)

    def test_root_home_with_lower_uid_runtime_file_is_rejected(self):
        binary = self.store / "versions/codex/1.2.3/bin/codex"
        binary.parent.mkdir(parents=True)
        binary.write_text("forged executable")
        self.lower_uid_owns(binary)
        self.rejected_without_mutation("root-owned")

    def test_group_writable_home_is_rejected(self):
        self.home.chmod(0o770)
        self.rejected_without_mutation("group/other-writable")

    def test_other_writable_home_ancestor_is_rejected(self):
        self.base.chmod(0o707)
        self.rejected_without_mutation("group/other-writable")

    def test_group_writable_harness_state_is_rejected(self):
        self.selected.chmod(0o660)
        self.rejected_without_mutation("group/other-writable")

    def test_escape_link_is_rejected_even_with_root_owned_destination(self):
        external = self.base / "external"
        external.write_text("unrelated root-owned content")
        (self.home / "external-state").symlink_to(external)
        self.rejected_without_mutation("untrusted symlink")

    def test_lower_uid_internal_link_is_rejected(self):
        link = self.store / "selected-link"
        link.symlink_to("selected.json")
        self.lower_uid_owns(link, link=True)
        self.rejected_without_mutation("untrusted symlink")

    def test_internal_root_link_used_by_npm_is_allowed(self):
        link = self.store / "selected-link"
        link.symlink_to("selected.json")
        before = snapshot(self.base)
        root_trust.startup(self.home)
        self.assertEqual(snapshot(self.base), before)

    def test_external_link_chain_cannot_import_mutable_indirection(self):
        external = self.base / "external-pointer"
        external.symlink_to(self.selected)
        (self.home / "managed-state").symlink_to(external)
        self.rejected_without_mutation("untrusted symlink")

    def test_cli_rejects_numeric_root_before_mutation_with_exit_64(self):
        self.home.chmod(0o770)
        before = snapshot(self.base)
        result = subprocess.run([sys.executable, str(SOURCE), "--home", str(self.home)],
                                env={**os.environ, "PUID": "000"}, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 64, result.stderr)
        self.assertIn("group/other-writable", result.stderr)
        self.assertIn("dedicated root-owned HOME", result.stderr)
        self.assertEqual(snapshot(self.base), before)

    def test_numeric_puid_with_leading_zero_still_protects_root(self):
        self.lower_uid_owns(self.home)
        with patch.dict(os.environ, {"PUID": "000"}):
            self.rejected_without_mutation("root-owned")

    def test_custom_store_owned_by_lower_uid_is_rejected(self):
        custom = self.base / "custom-store"
        custom.mkdir(mode=0o700)
        (custom / "selected.json").write_text("lower uid state")
        self.lower_uid_owns(custom)
        with patch.dict(os.environ, {"HARNESS_ROOT": str(custom)}):
            self.rejected_without_mutation("root-owned")

    def test_manager_store_check_rejects_lower_uid_state(self):
        self.lower_uid_owns(self.selected)
        before = snapshot(self.base)
        with self.assertRaisesRegex(ValueError, "root-owned"):
            root_trust.validate_root_store(self.store)
        self.assertEqual(snapshot(self.base), before)

    def test_store_created_by_lower_uid_after_manager_construction_is_rejected(self):
        source = SOURCE.with_name("harnesses.py")
        spec = importlib.util.spec_from_file_location("root_store_manager", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        directory = Path(tempfile.mkdtemp(prefix="xorder-late-root-store-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, directory, True)
        directory.rmdir()
        manager = module.Manager(directory, self.base / "unused-pins.json")
        directory.mkdir(mode=0o700)
        selected = directory / "selected.json"
        selected.write_text('{"schema_version":1,"harnesses":{}}\n')
        self.lower_uid_owns(directory)
        self.lower_uid_owns(selected)
        before = snapshot(directory)
        with self.assertRaisesRegex(ValueError, "root-owned"):
            manager.state()
        self.assertEqual(snapshot(directory), before)

    def test_private_root_store_under_sticky_tmp_parent_is_allowed(self):
        with tempfile.TemporaryDirectory(prefix="xorder-private-root-store-", dir="/tmp") as temporary:
            store = Path(temporary) / "not-created-yet" / "harnesses"
            root_trust.validate_root_store(store)
            self.assertFalse(store.exists())
            store.mkdir(parents=True, mode=0o700)
            root_trust.validate_root_store(store)

    def test_home_under_sticky_tmp_parent_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="xorder-root-home-", dir="/tmp") as temporary:
            home = Path(temporary)
            with self.assertRaisesRegex(ValueError, "group/other-writable"):
                root_trust.startup(home)

    def test_pristine_and_repeated_root_startup_are_read_only(self):
        before = snapshot(self.base)
        root_trust.startup(self.home)
        root_trust.startup(self.home)
        self.assertEqual(snapshot(self.base), before)

    def test_nonroot_selected_uid_does_not_claim_root_state(self):
        self.lower_uid_owns(self.home)
        before = snapshot(self.base)
        root_trust.startup(self.home, selected_uid=1000)
        self.assertEqual(snapshot(self.base), before)


if __name__ == "__main__":
    unittest.main()
