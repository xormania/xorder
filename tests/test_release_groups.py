import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_groups as groups


class ReleaseGroupsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = groups.load_policy(ROOT / "lifecycle/release-groups.json")
        self.policy["groups"] = []
        self.parent = self.add_image("php-dev/8.5-trixie", "1.0.0", "1")
        self.child = self.add_image("php-browser/8.5-trixie", "1.0.0", "2", self.parent["publication"])
        self.plan = groups.plan_group(self.policy, root=self.root, at="2026-10-19T06:00:00Z")
        self.accepted = groups.accept_group(self.policy, self.plan, root=self.root, accepted_at="2026-10-19T06:15:00Z")
        self.policy["groups"] = [self.accepted]
        member = self.accepted["resources"][1]
        self.lock = {"schema_version": 1, "group": self.accepted["id"], "resources": [{
            "line_id": member["line_id"], "version": member["version"],
            "identity": member["identity"], "platform": "linux/amd64", "service": "php"}]}
        self.actual = copy.deepcopy(self.lock["resources"])
        self.now = "2026-10-20T06:15:00Z"

    def add_image(self, line, version, digit, parent=None):
        publication = {"repository": f"ghcr.io/xormania/{line.split('/')[0]}",
                       "digest": "sha256:" + digit * 64, "public_pull_verified_at": "2026-10-14T08:00:00Z"}
        base = parent["repository"] + "@" + parent["digest"] if parent else "docker.io/library/php@sha256:" + "a" * 64
        item = {"line_id": line, "version": version, "lifecycle": "available", "publication": publication,
                "platforms": [{"platform": "linux/amd64", "digest": publication["digest"]}],
                "resolved_base": base, "verification": {"status": "passed"}, "source_commit": "a" * 40}
        path = self.root / "release-records" / line / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item))
        return item

    def check(self, now=None, fetched_at=None):
        moment = now or self.now
        return groups.check_selection(self.policy, self.lock, self.actual, root=self.root,
                                      now=moment, fetched_at=fetched_at or moment)

    def test_acceptance_calculates_dates_from_acceptance_not_build_age(self):
        self.assertEqual(self.accepted["support_ends_at"], "2026-11-16T06:15:00Z")
        self.assertEqual(self.accepted["warning_starts_at"], "2026-11-09T06:15:00Z")
        self.assertEqual(self.accepted["removal_eligible_at"], "2026-11-30T06:15:00Z")
        self.assertNotIn("support_ends_at", self.plan)
        self.assertNotIn("scheduled_at", self.accepted)

    def test_unchanged_artifacts_join_new_group_without_new_revision(self):
        second = groups.plan_group(self.policy, root=self.root, at="2026-10-26T06:00:00Z")
        self.assertEqual(second["resources"], self.plan["resources"])
        self.assertNotEqual(second["id"], self.plan["id"])

    def test_expiry_is_a_hard_boundary_even_when_same_digest_is_supported_elsewhere(self):
        second = groups.plan_group(self.policy, root=self.root, at="2026-10-26T06:00:00Z")
        self.policy["groups"].append(groups.accept_group(self.policy, second, root=self.root, accepted_at="2026-10-26T06:15:00Z"))
        self.assertEqual(self.check("2026-11-09T06:14:59Z")["status"], "supported")
        self.assertEqual(self.check("2026-11-09T06:15:00Z")["status"], "warning")
        report = self.check("2026-11-16T06:15:00Z")
        self.assertFalse(report["ok"])
        self.assertEqual(report["code"], "group-expired")
        self.assertEqual(report["replacement_group"], second["id"])

    def test_fresh_policy_required_and_future_receipt_rejected(self):
        for receipt in ("2026-10-19T06:15:00Z", "2026-10-21T06:15:00Z"):
            self.assertEqual(self.check(fetched_at=receipt)["code"], "policy-stale")
        report = groups.check_selection(self.policy, self.lock, self.actual, now=self.now)
        self.assertEqual(report["code"], "policy-not-fetched")

    def test_actual_digest_and_platform_are_checked(self):
        self.assertTrue(self.check()["ok"])
        for field, bad in (("identity", "ghcr.io/xormania/php-dev:latest"), ("platform", "linux/arm64")):
            original = self.actual[0][field]
            self.actual[0][field] = bad
            self.assertEqual(self.check()["code"], "actual-image-mismatch")
            self.actual[0][field] = original
        self.actual = []
        self.assertEqual(self.check()["code"], "actual-image-missing")

    def test_manifest_and_platform_identity_are_both_accepted(self):
        member = self.accepted["resources"][1]
        member["platforms"][0]["digest"] = "sha256:" + "f" * 64
        # This is the fetched policy-only execution path; repository gate checks records separately.
        self.actual[0]["identity"] = member["identity"].split("@")[0] + "@" + "sha256:" + "f" * 64
        report = groups.check_selection(self.policy, self.lock, self.actual, now=self.now, fetched_at=self.now)
        self.assertTrue(report["ok"], report)

    def test_unknown_group_and_cross_group_lock_fail(self):
        self.lock["resources"][0]["version"] = "9.9.9"
        self.assertEqual(self.check()["code"], "selection-outside-group")
        self.lock["group"] = "unknown"
        self.assertEqual(self.check()["code"], "group-unknown")

    def test_cohorts_cannot_omit_parent_or_mix_parent_revisions(self):
        bad = copy.deepcopy(self.plan)
        bad["resources"] = [r for r in bad["resources"] if r["parent"]]
        with self.assertRaisesRegex(ValueError, "Missing exact parent"):
            groups.validate_group(bad, self.root)
        self.add_image("php-dev/8.5-trixie", "1.0.1", "3")
        with self.assertRaisesRegex(ValueError, "Missing exact parent"):
            groups.plan_group(self.policy, root=self.root, at="2026-10-26T06:00:00Z")

    def test_explicit_child_selection_adds_exact_parent(self):
        proposal = groups.plan_group(self.policy, root=self.root, at="2026-10-26T06:00:00Z",
                                    selections={"php-browser/8.5-trixie": "1.0.0"})
        self.assertEqual(proposal["resources"], self.plan["resources"])

    def test_unknown_unverified_or_changed_release_evidence_rejected(self):
        bad = copy.deepcopy(self.plan)
        bad["resources"][0]["identity"] = bad["resources"][0]["identity"].split("@")[0] + "@sha256:" + "f" * 64
        with self.assertRaisesRegex(ValueError, "differs from accepted"):
            groups.validate_group(bad, self.root)
        path = self.root / "release-records/php-dev/8.5-trixie/1.0.0.json"
        item = json.loads(path.read_text())
        item["verification"]["status"] = "failed"
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(ValueError, "no accepted public verification"):
            groups.accept_group(self.policy, self.plan, root=self.root, accepted_at=self.now)

    def test_accepted_groups_cannot_be_extended_removed_or_rewritten(self):
        original = copy.deepcopy(self.policy)
        self.policy["revision"] += 1
        self.policy["groups"] = []
        with self.assertRaisesRegex(ValueError, "immutable"):
            groups.validate_policy(self.policy, previous=original)
        self.policy = copy.deepcopy(original)
        self.policy["groups"][0]["support_ends_at"] = "2026-11-17T06:15:00Z"
        with self.assertRaisesRegex(ValueError, "announced support periods"):
            groups.validate_policy(self.policy)

    def test_announced_legacy_deadline_cannot_move_or_disappear(self):
        for changed in (None, "2026-12-11T08:00:00Z", "2026-10-30T08:00:00Z"):
            prior = copy.deepcopy(self.policy)
            self.policy["revision"] += 1
            self.policy["legacy"]["enforce_after"] = changed
            with self.assertRaisesRegex(ValueError, "legacy support deadline is immutable"):
                groups.validate_policy(self.policy, previous=prior)
            self.policy = prior
        prior = copy.deepcopy(self.policy)
        prior["legacy"]["enforce_after"] = None
        self.policy["revision"] += 1
        groups.validate_policy(self.policy, previous=prior)

    def test_schedule_exception_requires_explicit_security_or_migration_reason(self):
        with self.assertRaisesRegex(ValueError, "release slot"):
            groups.plan_group(self.policy, root=self.root, at=self.now)
        proposal = groups.plan_group(self.policy, root=self.root, at=self.now, reason="security", group_id="security-2026-10-20")
        self.assertEqual(proposal["reason"], "security")

    def test_malformed_inputs_return_actionable_failures(self):
        for invalid in ([], {"schema_version": 1}, {**self.policy, "groups": ["broken"]}):
            report = groups.check_selection(invalid, self.lock, self.actual, now=self.now, fetched_at=self.now)
            self.assertFalse(report["ok"])
            self.assertEqual(report["code"], "policy-or-lock-invalid")

    def test_repository_proposal_and_schema_validate(self):
        import jsonschema
        policy = groups.load_policy(ROOT / "lifecycle/release-groups.json")
        proposal = groups.load_policy(ROOT / "lifecycle/bootstrap-group.json")
        groups.validate_policy(policy, ROOT)
        groups.validate_group(proposal, ROOT, available=True)
        schema = groups.load_policy(ROOT / "schemas/release-groups.schema.json")
        jsonschema.validate(policy, schema)
        jsonschema.validate(proposal, {"$ref": "#/$defs/planned", "$defs": schema["$defs"]})
        self.assertEqual(policy["legacy"]["enforce_after"], "2026-11-11T08:00:00Z")
        self.assertEqual(proposal["state"], "planned")
        self.assertNotIn("support_ends_at", proposal)

    def test_cli_accept_is_stdout_only(self):
        before = {p: p.read_bytes() for p in (ROOT / "lifecycle").glob("*.json")}
        proposal = groups.load_policy(ROOT / "lifecycle/bootstrap-group.json")
        proposal["id"] = "test-stdout-acceptance"
        source = self.root / "group.json"
        source.write_text(json.dumps(proposal))
        output = subprocess.run([sys.executable, str(ROOT / "scripts/release_groups.py"), "accept",
                                 str(source), "--accepted-at", "2026-10-14T08:00:00Z"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(output.stdout)["state"], "accepted")
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == "__main__":
    unittest.main()
