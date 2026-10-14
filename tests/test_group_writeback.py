"""Recover cohort PRs after interruption using a real local Git remote."""
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
sys.path.insert(0, str(ROOT / "scripts"))
import group_writeback as staging
import release_groups as groups
import writeback


class GroupWritebackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote, self.seed, self.worker = [self.root / name for name in ("origin.git", "seed", "worker")]
        self.git(self.root, "init", "--bare", "--initial-branch=master", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.seed))
        self.git(self.seed, "config", "user.name", "Fixture")
        self.git(self.seed, "config", "user.email", "fixture@example.test")
        policy = groups.load_policy(ROOT / "lifecycle/release-groups.json")
        policy["groups"] = []
        policy["revision"] = 1
        path = self.seed / staging.POLICY
        path.parent.mkdir(parents=True)
        path.write_text(writeback.encoded(policy))
        self.add_image("1.0.0", "1")
        (self.seed / "README.md").write_text("Authored guidance.\n")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Initial accepted image")
        self.git(self.seed, "push", "origin", "master")
        self.git(self.root, "clone", str(self.remote), str(self.worker))
        self.requests, self.attempts = [], 0
        self.slot = "2026-10-19T06:00:00Z"
        self.identity = "weekly-2026-10-19"
        self.branch = None

    @staticmethod
    def git(cwd, *args):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE).strip()

    def add_image(self, revision, digit):
        item = {"line_id": "python-dev/3.14-trixie", "version": revision, "lifecycle": "available",
                "publication": {"repository": "ghcr.io/xormania/python-dev", "digest": "sha256:" + digit * 64,
                                "public_pull_verified_at": "2026-10-14T08:00:00Z"},
                "verification": {"status": "passed"}, "source_commit": "a" * 40,
                "platforms": [{"platform": "linux/amd64", "digest": "sha256:" + digit * 64}],
                "resolved_base": "docker.io/library/python@sha256:" + "f" * 64}
        path = self.seed / "release-records/python-dev/3.14-trixie" / (revision + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(writeback.encoded(item))

    def stage(self, interrupt=False, existing_prs=None, **kwargs):
        original_output = writeback.output

        def output(*args):
            if args[0] == "gh":
                if args[-2:] == ("--jq", ".created_at"):
                    return "2026-10-19T06:42:20Z\n"
                self.assertEqual(args[:4], ("gh", "api", "--method", "GET"))
                return json.dumps(existing_prs or [])
            return original_output(*args)

        def run(*args, **options):
            if args[0] == "gh":
                self.assertEqual(args[:3], ("gh", "api", "--method"))
                self.attempts += 1
                self.requests.append((args[3], args[4], groups.load_policy(args[-1])))
                if interrupt:
                    raise RuntimeError("PR creation interrupted after push")
                return
            return subprocess.run(args, cwd=self.worker, check=True, capture_output=True, **options)

        with patch.object(staging, "ROOT", self.worker), patch.object(writeback, "ROOT", self.worker), \
                patch.object(writeback, "output", side_effect=output), patch.object(writeback, "run", side_effect=run), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder", "GITHUB_RUN_ID": "42"}):
            staging.main(**kwargs)
        branches = self.git(self.worker, "ls-remote", "--heads", "origin", "refs/heads/" + staging.PREFIX + "*")
        self.branch = branches.split()[1].removeprefix("refs/heads/") if branches else None

    def pending(self):
        refs = self.git(self.seed, "ls-remote", "--heads", "origin", "refs/heads/" + staging.PREFIX + "*")
        self.branch = refs.split()[1].removeprefix("refs/heads/")
        self.git(self.seed, "fetch", "origin", self.branch)
        return json.loads(self.git(self.seed, "show", "FETCH_HEAD:" + staging.POLICY))

    def interrupt_after_push(self):
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            self.stage(interrupt=True)
        policy = self.pending()
        first = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        shutil.rmtree(self.worker)
        self.git(self.root, "clone", str(self.remote), str(self.worker))
        return first, policy

    def test_schedule_slot_is_stable_across_delays_and_before_monday_six(self):
        self.assertEqual(staging.scheduled_slot("2026-10-19T06:42:20Z"), self.slot)
        self.assertEqual(staging.scheduled_slot("2026-10-25T23:59:59Z"), self.slot)
        self.assertEqual(staging.scheduled_slot("2026-10-19T05:59:59Z"), "2026-10-12T06:00:00Z")

    def test_orphan_branch_recovers_same_content_keyed_pr_and_deadlines(self):
        first, policy = self.interrupt_after_push()
        self.stage()
        self.assertEqual(self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0], first)
        self.assertEqual(self.pending(), policy)
        self.assertEqual(policy["revision"], 2)
        group = policy["groups"][0]
        self.assertEqual(group["accepted_at"], self.slot)
        self.assertEqual(group["support_ends_at"], "2026-11-16T06:00:00Z")
        self.assertEqual(staging.branch_name(group), self.branch)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[-1][0], "POST")
        self.assertIn("does not enable automatic merge", self.requests[-1][2]["body"])

    def test_existing_pr_is_updated_through_rest(self):
        first, _ = self.interrupt_after_push()
        self.stage(existing_prs=[{"number": 61}])
        self.assertEqual(self.requests[-1][:2], ("PATCH", "repos/xormania/xorder/pulls/61"))
        self.assertEqual(self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0], first)

    def test_new_master_records_do_not_retarget_an_existing_cohort(self):
        first, policy = self.interrupt_after_push()
        self.add_image("1.0.1", "2")
        (self.seed / "README.md").write_text("Updated authored guidance.\n")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Accept another image and improve guidance")
        self.git(self.seed, "push", "origin", "master")
        self.stage()
        recovered = self.pending()
        self.assertEqual(recovered["groups"], policy["groups"])
        self.assertEqual(recovered["groups"][0]["resources"][0]["version"], "1.0.0")
        self.assertEqual((self.worker / "README.md").read_text(), "Updated authored guidance.\n")
        latest = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        self.git(self.worker, "merge-base", "--is-ancestor", first, latest)

    def test_policy_conflict_recovery_preserves_new_master_group(self):
        first, pending = self.interrupt_after_push()
        policy = groups.load_policy(self.seed / staging.POLICY)
        plan = groups.plan_group(policy, root=self.seed, at="2026-10-20T08:00:00Z", reason="security", group_id="security-fixture")
        policy["groups"].append(groups.accept_group(policy, plan, root=self.seed, accepted_at="2026-10-20T08:00:00Z"))
        policy["revision"] += 1
        (self.seed / staging.POLICY).write_text(writeback.encoded(policy))
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Accept an emergency group")
        self.git(self.seed, "push", "origin", "master")
        self.stage()
        recovered = self.pending()
        self.assertEqual(recovered["revision"], 3)
        self.assertEqual(recovered["groups"], policy["groups"] + pending["groups"])
        groups.validate_policy(recovered, self.worker, previous=policy)
        latest = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        self.git(self.worker, "merge-base", "--is-ancestor", first, latest)

    def test_already_merged_group_is_noop(self):
        self.stage()
        self.git(self.seed, "fetch", "origin", self.branch)
        self.git(self.seed, "merge", "--ff-only", "FETCH_HEAD")
        self.git(self.seed, "push", "origin", "master")
        requests = len(self.requests)
        self.stage()
        self.assertEqual(len(self.requests), requests)
        self.assertEqual(groups.load_policy(self.worker / staging.POLICY)["revision"], 2)

    def test_exception_dispatch_requires_explicit_slot_and_details(self):
        for kwargs in ({"reason": "security"}, {"reason": "migration", "slot": self.slot},
                       {"reason": "security", "details": "Urgent fix"}):
            with self.assertRaisesRegex(ValueError, "explicit UTC slot and details"):
                self.stage(**kwargs)
        self.stage(reason="security", slot="2026-10-20T08:15:00Z", details="Verified critical dependency replacement.")
        group = self.pending()["groups"][0]
        self.assertEqual(group["accepted_at"], "2026-10-20T08:15:00Z")
        self.assertIn("Verified critical dependency replacement.", self.requests[-1][2]["body"])

    def test_workflow_uses_minimal_permissions_env_inputs_and_original_event_receipt(self):
        workflow = (ROOT / ".github/workflows/release-groups.yml").read_text()
        self.assertIn("cron: '0 6 * * 1'", workflow)
        self.assertNotIn("packages:", workflow)
        self.assertIn("secrets.LIBRARY_BOT_TOKEN || github.token", workflow)
        self.assertIn('"$GROUP_DETAILS"', workflow)
        self.assertNotIn("pr merge", workflow)
        self.stage()
        self.assertEqual(self.pending()["groups"][0]["accepted_at"], self.slot)


if __name__ == "__main__":
    unittest.main()
