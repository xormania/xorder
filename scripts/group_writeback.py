#!/usr/bin/env python3
"""Propose a predictable, accepted-digest release group through a recoverable PR."""
import argparse
import copy
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess

import release_groups as groups
import writeback

ROOT = Path(__file__).resolve().parents[1]
POLICY = "lifecycle/release-groups.json"
PREFIX = "automation/group-"


def scheduled_slot(event_time):
    """Use the original event's Monday slot, including on later run attempts."""
    event = groups.clock(event_time)
    monday = event.replace(hour=6, minute=0, second=0, microsecond=0) - timedelta(days=event.weekday())
    if monday > event:
        monday -= timedelta(days=7)
    return groups.utc(monday)


def group_id(reason, slot):
    if reason == "scheduled":
        return "weekly-" + groups.timestamp(slot).date().isoformat()
    return reason + "-" + slot.lower().replace(":", "-").replace(".", "-")


def branch_name(group):
    key = json.dumps(group, sort_keys=True, separators=(",", ":")).encode()
    return PREFIX + hashlib.sha256(key).hexdigest()[:24]


def pending_group(identity):
    """Recover both open PRs and orphan branches left after push interrupted creation."""
    refs = writeback.output("git", "ls-remote", "--heads", "origin", "refs/heads/" + PREFIX + "*")
    matches = []
    for line in sorted(refs.splitlines()):
        branch = line.split()[1].removeprefix("refs/heads/")
        writeback.run("git", "fetch", "origin", branch)
        prior = subprocess.run(["git", "show", f"FETCH_HEAD:{POLICY}"], cwd=ROOT,
                               capture_output=True, text=True, check=True)
        policy = json.loads(prior.stdout)
        for group in policy.get("groups", []):
            if group.get("id") == identity:
                groups.validate_group(group, ROOT, available=True)
                matches.append((branch, group))
    if len(matches) > 1:
        raise RuntimeError(f"Multiple pending group branches select {identity}; inspect them before retrying")
    return matches[0] if matches else None


def prepare(branch, previous, candidate, existing):
    """Merge master without losing a pending cohort or another accepted group."""
    if existing:
        writeback.run("git", "fetch", "origin", branch)
        writeback.run("git", "checkout", "-B", branch, "FETCH_HEAD")
        merged = subprocess.run(["git", "merge", "origin/master", "--no-commit", "--no-edit"], cwd=ROOT,
                                capture_output=True, text=True)
        if merged.returncode:
            conflicts = writeback.output("git", "diff", "--name-only", "--diff-filter=U").splitlines()
            if conflicts != [POLICY]:
                raise RuntimeError("Group recovery needs manual authored-file conflict resolution: " + ", ".join(conflicts))
            # Only our owned policy conflict is regenerated below. Other authored
            # files and master commits remain part of the ordinary merge.
    else:
        writeback.prepare_branch(branch)
    # A concurrent master update during preparation must not lose an accepted
    # policy group. Use the fetched master revision that was actually merged.
    previous = json.loads(writeback.output("git", "show", f"origin/master:{POLICY}"))
    groups.validate_policy(previous, ROOT)
    if any(g["id"] == candidate["id"] for g in previous["groups"]):
        raise RuntimeError("Group was accepted while preparing; rerun to observe master")
    groups.validate_group(candidate, ROOT, available=True)
    policy = copy.deepcopy(previous)
    policy["revision"] += 1
    policy["groups"].append(candidate)
    groups.validate_policy(policy, ROOT, previous=previous)
    path = ROOT / POLICY
    path.write_text(writeback.encoded(policy))
    writeback.run("git", "add", "--", POLICY)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    merging = subprocess.run(["git", "rev-parse", "--quiet", "--verify", "MERGE_HEAD"],
                             cwd=ROOT, capture_output=True).returncode == 0
    if changed or merging:
        writeback.run("git", "commit", "-m", "Accept image release group " + candidate["id"])
    return policy


def body(group, details):
    members = "\n".join(f"| `{r['line_id']}` | {r['version']} | `{r['identity']}` |" for r in group["resources"])
    return (f"Proposes release group `{group['id']}` from already accepted public image evidence. "
            "No images are built and no image revisions are allocated. Unchanged digests are reused.\n\n"
            f"Reason: **{group['reason']}**.\n\n{details}\n\n"
            f"The announced support clock starts **{group['accepted_at']}**, expires **{group['support_ends_at']}**, "
            f"warns from **{group['warning_starts_at']}**, and permits retention planning from "
            f"**{group['removal_eligible_at']}**. Dates are anchored to this announced slot, "
            "and do not move if merging is delayed or the workflow is rerun. "
            "The group becomes authoritative only after this PR merges to master.\n\n"
            "| Image line | Revision | Accepted digest |\n| --- | --- | --- |\n" + members + "\n\n"
            "Validate and migrate downstream locks through their normal PRs. Retirement eligibility "
            "does not delete registry artifacts; retention checks protect still-supported cohorts, exact parents and assurance.\n\n"
            "Merge through the repository's permitted merge method. Group writeback does not enable automatic merge. "
            "If this PR was created with GITHUB_TOKEN, select Approve workflows to run in the PR's merge box. "
            "LIBRARY_BOT_TOKEN lets PR validation start automatically.")


def main(*, reason="scheduled", slot=None, event_time=None, details="", identity=None):
    if reason not in {"scheduled", "security", "migration"}:
        raise ValueError("Unknown group release reason")
    if reason != "scheduled" and (not slot or not details.strip()):
        raise ValueError("Security and migration proposals require an explicit UTC slot and details")
    if not slot:
        if event_time is None:
            repository, run_id = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_RUN_ID"]
            event_time = writeback.output("gh", "api", f"repos/{repository}/actions/runs/{run_id}", "--jq", ".created_at").strip()
        slot = scheduled_slot(event_time)
    groups.timestamp(slot)
    identity = identity or group_id(reason, slot)
    writeback.run("git", "config", "user.name", "xorder automation")
    writeback.run("git", "config", "user.email", "xorder@users.noreply.github.com")
    writeback.run("git", "fetch", "origin", "master")
    # Every proposed member comes from accepted master, rather than a stale
    # checkout or unmerged branch. Never reset an in-progress authored checkout.
    if writeback.output("git", "status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("Group writeback requires a clean tracked checkout")
    writeback.run("git", "checkout", "--detach", "origin/master")
    previous = groups.load_policy(ROOT / POLICY)
    groups.validate_policy(previous, ROOT)
    if any(group["id"] == identity for group in previous["groups"]):
        print(f"Release group {identity} is already accepted; no proposal needed.")
        return
    recovered = pending_group(identity)
    if recovered:
        branch, candidate = recovered
        if candidate["reason"] != reason or candidate["accepted_at"] != slot:
            raise RuntimeError("Recovered group differs from the requested reason or announced slot")
    else:
        planned = groups.plan_group(previous, root=ROOT, at=slot, group_id=identity, reason=reason)
        candidate = groups.accept_group(previous, planned, root=ROOT, accepted_at=slot)
        branch = branch_name(candidate)
    prepare(branch, previous, candidate, recovered is not None)
    writeback.run("git", "push", "origin", branch)
    writeback.upsert_pr(branch, "Accept image release group " + identity,
                       body(candidate, details or "Weekly accepted-digest cohort and scheduled support renewal."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", choices=["scheduled", "security", "migration"], default="scheduled")
    parser.add_argument("--slot", help="Explicit announced UTC slot; emergencies and migration require it")
    parser.add_argument("--event-time", help="Original schedule event time for deterministic local diagnosis")
    parser.add_argument("--details", default="")
    parser.add_argument("--id")
    args = parser.parse_args()
    main(reason=args.reason, slot=args.slot, event_time=args.event_time, details=args.details, identity=args.id)
