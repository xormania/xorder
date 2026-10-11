"""Public evidence gates and immutable ledger edits, without image builds."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog_checks as checks
from test_library import record


class PublicEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record = record("php-dev/8.4-trixie")
        self.durable = copy.deepcopy(self.record)
        self.release = {"draft": False, "tag_name": self.record["source_tag"],
                        "target_commitish": self.record["source_commit"],
                        "assets": [{"name": "record.json", "digest": "sha256:" + "e" * 64,
                                    "browser_download_url": "https://example.test/record.json"}]}
        self.remote = {"digest": self.record["publication"]["digest"], "platforms": {}}

    def verify(self, *, require_assurance=False):
        def transfer(url, destination, expected):
            self.assertEqual(url, "https://example.test/record.json")
            self.assertEqual(expected, "e" * 64)
            destination.write_text(json.dumps(self.durable))
        with patch.object(checks, "public_release", return_value=self.release), \
                patch.object(checks, "download", side_effect=transfer) as download, \
                patch.object(checks, "resolve", return_value=self.remote) as resolve:
            result = checks.verify_image_record(self.record, "xormania/xorder", require_assurance=require_assurance)
            download.assert_called_once()
            resolve.assert_called_once_with("ghcr.io/xormania/php-dev:8.4-trixie-v1.0.0")
            return result

    def test_single_manifest_and_index_resolve_public_digests(self):
        self.assertEqual(self.verify(), self.record)
        self.remote["platforms"] = {"linux/amd64": self.record["platforms"][0]["digest"]}
        self.assertEqual(self.verify(), self.record)

    def test_new_unsigned_record_rejected_before_public_lookup(self):
        with patch.object(checks, "public_release") as release, self.assertRaisesRegex(RuntimeError, "requires verified assurance"):
            checks.verify_image_record(self.record, "xormania/xorder")
        release.assert_not_called()

    def add_assurance(self):
        from image_assurance import PREDICATE
        self.record["assurance"] = {
            "receipt_url": "https://github.com/xormania/xorder/releases/download/" + self.record["source_tag"].replace("/", "%2F") + "/assurance.json",
            "receipt_sha256": "a" * 64, "predicate_type": PREDICATE}
        self.durable = copy.deepcopy(self.record)

    def test_new_assured_record_requires_complete_assurance_verification(self):
        self.add_assurance()
        with patch("image_assurance.verify_record", return_value=self.record) as verify:
            self.assertEqual(self.verify(require_assurance=True), self.record)
        self.assertEqual(verify.call_args.args[0], self.record)
        verify.assert_called_once()
        with patch("image_assurance.verify_record", side_effect=ValueError("signature mismatch")), \
                self.assertRaisesRegex(ValueError, "signature mismatch"):
            self.verify(require_assurance=True)

    def test_lifecycle_change_can_differ_from_original_durable_record(self):
        self.record.update(lifecycle="withdrawn", reason="Regression", replacement="v1.0.1",
                           lifecycle_date="2026-10-09")
        self.verify()

    def test_durable_facts_must_equal_proposed_facts(self):
        self.durable["resolved_base"] = "test@sha256:" + "f" * 64
        with self.assertRaisesRegex(RuntimeError, "durable Release asset"):
            self.verify()

    def test_missing_checksum_or_ambiguous_asset_rejected_before_download(self):
        for assets in ([], [{"name": "record.json"}], self.release["assets"] * 2):
            with self.subTest(assets=assets), \
                    patch.object(checks, "public_release", return_value={**self.release, "assets": assets}), \
                    patch.object(checks, "download") as download:
                with self.assertRaisesRegex(RuntimeError, "asset checksum"):
                    checks.verify_image_record(self.record, "xormania/xorder", require_assurance=False)
                download.assert_not_called()

    def test_draft_or_wrong_source_release_rejected(self):
        for change in ({"draft": True}, {"target_commitish": "f" * 40}, {"tag_name": "wrong"}):
            with self.subTest(change=change), \
                    patch.object(checks, "public_release", return_value={**self.release, **change}), \
                    patch.object(checks, "download") as download:
                with self.assertRaisesRegex(RuntimeError, "Source Release"):
                    checks.verify_image_record(self.record, "xormania/xorder", require_assurance=False)
                download.assert_not_called()

    def test_unavailable_or_wrong_exact_digest_rejected(self):
        for remote in (None, {"digest": "sha256:" + "f" * 64, "platforms": {}}):
            self.remote = remote
            with self.subTest(remote=remote), self.assertRaisesRegex(RuntimeError, "exact image digest"):
                self.verify()

    def test_wrong_or_missing_index_platform_rejected(self):
        for platforms in ({"linux/amd64": "sha256:" + "f" * 64},
                          {"linux/arm64": self.record["platforms"][0]["digest"]}):
            self.remote["platforms"] = platforms
            with self.subTest(platforms=platforms), self.assertRaisesRegex(RuntimeError, "platform digest"):
                self.verify()

    def test_corrupt_download_fails_before_registry_query(self):
        with patch.object(checks, "public_release", return_value=self.release), \
                patch.object(checks, "download", side_effect=ValueError("download checksum mismatch")), \
                patch.object(checks, "resolve") as resolve:
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                checks.verify_image_record(self.record, "xormania/xorder", require_assurance=False)
            resolve.assert_not_called()


class LedgerChangeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "--initial-branch=master")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.test")
        self.original = record("php-dev/8.4-trixie")
        self.write(self.original)
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.PIPE)

    def write(self, value, relative=None):
        relative = relative or f"release-records/{value['line_id']}/{value['version']}.json"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", "Fixture")

    def test_only_new_images_selected_from_mixed_records(self):
        new = record("php-dev/8.4-trixie", "1.0.1")
        self.write(new)
        self.write({"not": "an image"}, "release-records/artifacts/configuration/test/1.0.0.json")
        self.commit()
        self.assertEqual(list(checks.changed_image_records(self.base, self.root)), [new])

    def test_lifecycle_changes_do_not_reverify_unavailable_artifacts(self):
        changed = copy.deepcopy(self.original)
        changed.update(lifecycle="withdrawn", reason="Regression", replacement="v1.0.1",
                       lifecycle_date="2026-10-09")
        self.write(changed)
        self.commit()
        self.assertEqual(list(checks.changed_image_records(self.base, self.root)), [])

    def test_existing_evidence_cannot_change(self):
        changed = copy.deepcopy(self.original)
        changed["source_commit"] = "f" * 40
        self.write(changed)
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "immutable"):
            list(checks.changed_image_records(self.base, self.root))

    def test_existing_image_record_cannot_be_deleted(self):
        original_path = f"release-records/{self.original['line_id']}/{self.original['version']}.json"
        self.git("rm", original_path)
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "cannot be deleted or renamed.*" + original_path):
            list(checks.changed_image_records(self.base, self.root))

    def test_existing_image_record_cannot_be_renamed(self):
        original_path = f"release-records/{self.original['line_id']}/{self.original['version']}.json"
        destinations = ("release-records/php-dev/8.4-trixie/renamed.json",
                        "release-records/artifacts/configuration/moved/1.0.0.json",
                        "archived-record.json")
        for destination in destinations:
            with self.subTest(destination=destination):
                self.git("reset", "--hard", self.base)
                (self.root / destination).parent.mkdir(parents=True, exist_ok=True)
                self.git("mv", original_path, destination)
                self.commit()
                self.assertTrue(self.git("diff", "--name-status", "--find-renames", self.base, "HEAD").startswith("R100"))
                with self.assertRaisesRegex(RuntimeError, "cannot be deleted or renamed.*" + original_path):
                    list(checks.changed_image_records(self.base, self.root))

    def test_new_revision_does_not_allow_removing_previous_record(self):
        original_path = f"release-records/{self.original['line_id']}/{self.original['version']}.json"
        self.git("rm", original_path)
        self.write(record("php-dev/8.4-trixie", "1.0.1"))
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "cannot be deleted or renamed.*" + original_path):
            list(checks.changed_image_records(self.base, self.root))

    def test_identity_must_match_record_path(self):
        self.write(record("php-dev/8.4-trixie", "1.0.1"), "release-records/other/1.0.1.json")
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "path disagrees"):
            list(checks.changed_image_records(self.base, self.root))

    def test_manual_scan_checks_existing_records(self):
        self.assertEqual(list(checks.changed_image_records(None, self.root)), [self.original])

    def test_unknown_empty_and_option_like_bases_fail_closed(self):
        for base in ("", "missing-commit", "--quiet"):
            with self.subTest(base=base), self.assertRaisesRegex(RuntimeError, "known base commit"):
                list(checks.changed_image_records(base, self.root))

    def test_unrelated_base_cannot_hide_additions(self):
        self.git("checkout", "--orphan", "unrelated")
        (self.root / "unrelated.txt").write_text("Distinct root commit\n")
        self.commit()
        with self.assertRaisesRegex(RuntimeError, "ancestor of HEAD"):
            list(checks.changed_image_records(self.base, self.root))

    def test_pr_addition_requires_assurance_while_unchanged_history_is_grandfathered(self):
        original_selector = checks.changed_image_records
        with patch.object(checks, "changed_image_records", side_effect=lambda base: original_selector(base, self.root)), \
                patch.object(checks, "public_release") as public, \
                patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request"}), \
                patch.object(sys, "argv", ["catalog_checks.py", "--base", self.base]):
            checks.main()  # The unchanged unsigned historical record needs no new assurance.
            self.write(record("php-dev/8.4-trixie", "1.0.1"))
            self.commit()
            with self.assertRaisesRegex(RuntimeError, "requires verified assurance"):
                checks.main()
            public.assert_not_called()


class CheckModeTests(unittest.TestCase):
    def test_missing_mode_or_empty_pr_base_cannot_become_an_audit(self):
        with patch.object(sys, "argv", ["catalog_checks.py"]), \
                patch.object(checks, "changed_image_records") as records, \
                self.assertRaises(SystemExit):
            checks.main()
        records.assert_not_called()
        with patch.object(sys, "argv", ["catalog_checks.py", "--base", ""]), \
                patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request"}), \
                patch.object(checks, "verify_image_record") as verify, \
                self.assertRaisesRegex(RuntimeError, "known base commit"):
            checks.main()
        verify.assert_not_called()

    def test_explicit_local_and_master_audits_keep_original_contracts(self):
        old = record("php-dev/8.4-trixie")
        for event, ref in (("", ""), ("workflow_dispatch", "refs/heads/master")):
            with self.subTest(event=event), \
                    patch.object(sys, "argv", ["catalog_checks.py", "--audit"]), \
                    patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref}), \
                    patch.object(checks, "changed_image_records", return_value=[old]) as records, \
                    patch.object(checks, "verify_image_record") as verify:
                checks.main()
                records.assert_called_once_with(None)
                self.assertEqual(verify.call_args.kwargs, {"require_assurance": False})

    def test_pr_and_feature_dispatch_cannot_use_audit_as_acceptance_context(self):
        for event, ref in (("pull_request", "refs/pull/1/merge"),
                           ("workflow_dispatch", "refs/heads/feature")):
            with self.subTest(event=event), \
                    patch.object(sys, "argv", ["catalog_checks.py", "--audit"]), \
                    patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref}), \
                    patch.object(checks, "changed_image_records") as records, \
                    self.assertRaises(SystemExit):
                checks.main()
            records.assert_not_called()
