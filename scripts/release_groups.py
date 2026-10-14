#!/usr/bin/env python3
"""Read-only release cohort planning and current support checks (no registry writes)."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
IDENTITY = re.compile(r"^ghcr\.io/xormania/[a-z0-9][a-z0-9-]*@sha256:[a-f0-9]{64}$")
LINE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-zA-Z0-9][a-zA-Z0-9.-]*$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


def timestamp(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ValueError(f"Expected an explicit UTC timestamp ending in Z: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def clock(now=None):
    value = timestamp(now) if isinstance(now, str) else now or datetime.now(UTC)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Evaluation time must be timezone-aware UTC")
    return value


def load_policy(path):
    return json.loads(Path(path).read_text())


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f"Expected fields {sorted(required)} with optional {sorted(optional)}")


def record(root, line_id, version, available=False):
    if not LINE.fullmatch(line_id) or not VERSION.fullmatch(version):
        raise ValueError("Invalid image line or revision")
    relative = f"release-records/{line_id}/{version}.json"
    path = Path(root) / relative
    if path.exists():
        item = load_policy(path)
    else:
        item = None
        # A retired recommendation still has immutable, checksum-bound publication facts.
        for retirement in (Path(root) / "retired-records").glob("*.json"):
            declaration = load_policy(retirement)
            result = subprocess.run(["git", "show", f"{declaration['history_commit']}:{relative}"],
                                    cwd=root, capture_output=True, timeout=10)
            if result.returncode:
                continue
            historical = json.loads(result.stdout)
            if any(entry["sha256"] == hashlib.sha256(result.stdout).hexdigest()
                   and entry["source_commit"] == historical["source_commit"]
                   for entry in declaration["records"]):
                item = historical
                break
        if item is None:
            raise ValueError(f"Unknown accepted image: {line_id} v{version}")
        if available:
            raise ValueError(f"Retired recommendation cannot join a new group: {line_id} v{version}")
    if item.get("line_id") != line_id or item.get("version") != version:
        raise ValueError("Release record identity does not match its path")
    if (item.get("verification", {}).get("status") != "passed"
            or not item.get("publication", {}).get("public_pull_verified_at")):
        raise ValueError(f"Image has no accepted public verification: {line_id} v{version}")
    if available and item.get("lifecycle") != "available":
        raise ValueError(f"Image is unavailable: {line_id} v{version}")
    return item


def resource(item):
    return {"line_id": item["line_id"], "version": item["version"],
            "identity": item["publication"]["repository"] + "@" + item["publication"]["digest"],
            "platforms": [{"platform": p["platform"], "digest": p["digest"]} for p in item["platforms"]],
            "parent": item["resolved_base"] if item["resolved_base"].startswith("ghcr.io/xormania/") else None}


def validate_group(group, root=None, available=False):
    if not isinstance(group, dict):
        raise ValueError("Group must be an object")
    shared = {"schema_version", "id", "state", "reason", "resources"}
    accepted = {"accepted_at", "support_ends_at", "warning_starts_at", "removal_eligible_at", "replacement"}
    planned = {"scheduled_at"}
    _keys(group, shared | (accepted if group.get("state") == "accepted" else planned))
    if type(group["schema_version"]) is not int or group["schema_version"] != 1 or group["state"] not in {"planned", "accepted"}:
        raise ValueError("Unsupported group schema or state")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,79}", group["id"]):
        raise ValueError("Invalid release group id")
    if group["reason"] not in {"scheduled", "security", "migration"}:
        raise ValueError("Invalid release group reason")
    if group["state"] == "planned":
        scheduled = timestamp(group["scheduled_at"])
        if group["reason"] == "scheduled" and (scheduled.weekday() != 0 or (scheduled.hour, scheduled.minute, scheduled.second, scheduled.microsecond) != (6, 0, 0, 0)):
            raise ValueError("Ordinary groups must use the Monday 06:00 UTC release slot")
    else:
        dates = [timestamp(group[k]) for k in ("accepted_at", "warning_starts_at", "support_ends_at", "removal_eligible_at")]
        if not dates[0] <= dates[1] < dates[2] < dates[3]:
            raise ValueError("Group dates must order acceptance, warning, expiry, then removal")
        if group["replacement"] is not None and not isinstance(group["replacement"], str):
            raise ValueError("Replacement must be a release group id or null")
    if not isinstance(group["resources"], list) or not group["resources"]:
        raise ValueError("A release group must contain accepted images")
    lines, identities = set(), set()
    for member in group["resources"]:
        _keys(member, {"line_id", "version", "identity", "platforms", "parent"})
        if not LINE.fullmatch(member["line_id"]) or not VERSION.fullmatch(member["version"]) or not IDENTITY.fullmatch(member["identity"]):
            raise ValueError("Release group must pin exact accepted image identities")
        if member["identity"].split("@")[0] != "ghcr.io/xormania/" + member["line_id"].split("/")[0]:
            raise ValueError("Image family and registry identity differ")
        if member["line_id"] in lines or member["identity"] in identities:
            raise ValueError("A group cannot select multiple revisions of one image line")
        lines.add(member["line_id"])
        identities.add(member["identity"])
        platforms = member["platforms"]
        if (not isinstance(platforms, list) or not platforms
                or len({p.get("platform") for p in platforms}) != len(platforms)):
            raise ValueError("Group must list unique verified platforms")
        for p in platforms:
            _keys(p, {"platform", "digest"})
            if not re.fullmatch(r"linux/[a-z0-9_]+(?:/[a-z0-9]+)?", p["platform"]) or not re.fullmatch(r"sha256:[a-f0-9]{64}", p["digest"]):
                raise ValueError("Invalid verified platform or digest")
        if member["parent"] is not None and not IDENTITY.fullmatch(member["parent"]):
            raise ValueError("Xorder parent must be an exact digest identity")
        if root is not None and member != resource(record(root, member["line_id"], member["version"], available)):
            raise ValueError(f"Member differs from accepted release evidence: {member['line_id']}")
    for member in group["resources"]:
        if member["parent"] is not None and member["parent"] not in identities:
            raise ValueError(f"Missing exact parent for {member['line_id']}: {member['parent']}")
    by_identity = {m["identity"]: m for m in group["resources"]}
    for member in group["resources"]:
        if member["parent"] and not {p["platform"] for p in member["platforms"]} <= {p["platform"] for p in by_identity[member["parent"]]["platforms"]}:
            raise ValueError("Child platform is unavailable in its exact parent")
    parents = {m["identity"]: m["parent"] for m in group["resources"]}
    for identity in parents:
        visited, current = set(), identity
        while current is not None:
            if current in visited:
                raise ValueError("Cyclic group parent dependency")
            visited.add(current)
            current = parents[current]
    return group


def validate_policy(policy, root=None, previous=None):
    _keys(policy, {"schema_version", "revision", "cadence", "defaults", "legacy", "groups"})
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or type(policy["revision"]) is not int or policy["revision"] < 1:
        raise ValueError("Invalid support policy revision")
    _keys(policy["cadence"], {"interval_days", "anchor"})
    anchor = timestamp(policy["cadence"]["anchor"])
    if policy["cadence"]["interval_days"] != 7 or anchor.weekday() != 0 or (anchor.hour, anchor.minute, anchor.second) != (6, 0, 0):
        raise ValueError("Scheduled groups use Monday 06:00 UTC weekly cadence")
    _keys(policy["defaults"], {"support_days", "warning_days", "removal_grace_days", "max_policy_age_hours"})
    if any(type(v) is not int or v < 1 for v in policy["defaults"].values()):
        raise ValueError("Policy periods must be positive integer durations")
    if policy["defaults"]["support_days"] <= policy["defaults"]["warning_days"]:
        raise ValueError("Warning duration must be shorter than support")
    if policy["defaults"]["max_policy_age_hours"] > 24:
        raise ValueError("Support checks require policy fetched within 24 hours")
    _keys(policy["legacy"], {"enforce_after"})
    if policy["legacy"]["enforce_after"] is not None:
        timestamp(policy["legacy"]["enforce_after"])
    if not isinstance(policy["groups"], list):
        raise ValueError("Policy groups must be a list")
    ids = set()
    for group in policy["groups"]:
        validate_group(group, root)
        if group["state"] != "accepted" or group["id"] in ids:
            raise ValueError("Policy contains only unique accepted groups")
        accepted_at = timestamp(group["accepted_at"])
        expiry = accepted_at + timedelta(days=policy["defaults"]["support_days"])
        if (timestamp(group["support_ends_at"]) != expiry
                or timestamp(group["warning_starts_at"]) != expiry - timedelta(days=policy["defaults"]["warning_days"])
                or timestamp(group["removal_eligible_at"]) != expiry + timedelta(days=policy["defaults"]["removal_grace_days"])):
            raise ValueError("Group dates differ from the announced support periods")
        ids.add(group["id"])
    for group in policy["groups"]:
        if group["replacement"] is not None and (group["replacement"] not in ids or group["replacement"] == group["id"]):
            raise ValueError("Replacement must identify another accepted group")
    if previous is not None:
        deadline = previous["legacy"]["enforce_after"]
        if deadline is not None and policy["legacy"]["enforce_after"] != deadline:
            raise ValueError("Announced legacy support deadline is immutable")
        if policy != previous and policy["revision"] <= previous["revision"]:
            raise ValueError("Changed policy requires an increased revision")
        by_id = {g["id"]: g for g in policy["groups"]}
        if previous["groups"] and policy["defaults"] != previous["defaults"]:
            raise ValueError("Accepted support periods require a new policy schema to change")
        for old in previous["groups"]:
            if by_id.get(old["id"]) != old:
                raise ValueError(f"Accepted group is immutable: {old['id']}")
    return policy


def plan_group(policy, *, root=ROOT, at=None, group_id=None, reason="scheduled", selections=None):
    validate_policy(policy, root)
    scheduled = clock(at)
    if reason == "scheduled":
        anchor = timestamp(policy["cadence"]["anchor"])
        if (scheduled - anchor).total_seconds() % (7 * 86400):
            raise ValueError("Ordinary groups must use the Monday 06:00 UTC release slot")
    records = {}
    for path in (Path(root) / "release-records").glob("*/*/*.json"):
        item = load_policy(path)
        if item.get("lifecycle") == "available":
            key = item["line_id"]
            if key not in records or tuple(map(int, item["version"].split("."))) > tuple(map(int, records[key]["version"].split("."))):
                records[key] = item
    if selections:
        records = {line: record(root, line, version, True) for line, version in selections.items()}
    # Missing parents join the same group; a conflicting selected parent fails validation.
    queue = list(records.values())
    while queue:
        item = queue.pop()
        parent = item["resolved_base"]
        if not parent.startswith("ghcr.io/xormania/"):
            continue
        matching = [load_policy(p) for p in (Path(root) / "release-records").glob("*/*/*.json")
                    if resource(load_policy(p))["identity"] == parent]
        if len(matching) != 1:
            raise ValueError(f"Exact parent has no unique accepted record: {parent}")
        parent_record = matching[0]
        if parent_record["line_id"] not in records:
            records[parent_record["line_id"]] = parent_record
            queue.append(parent_record)
    group = {"schema_version": 1, "id": group_id or f"weekly-{scheduled.date().isoformat()}",
             "state": "planned", "reason": reason, "scheduled_at": utc(scheduled),
             "resources": [resource(records[line]) for line in sorted(records)]}
    return validate_group(group, root, available=True)


def accept_group(policy, planned, *, root=ROOT, accepted_at=None):
    validate_policy(policy, root)
    validate_group(planned, root, available=True)
    if planned["state"] != "planned":
        raise ValueError("Only a planned group may be accepted")
    accepted = clock(accepted_at)
    if accepted < timestamp(planned["scheduled_at"]):
        raise ValueError("Acceptance cannot precede the announced release slot")
    if any(g["id"] == planned["id"] for g in policy["groups"]):
        raise ValueError("Group id has already been accepted")
    result = copy.deepcopy(planned)
    del result["scheduled_at"]
    result.update(state="accepted", accepted_at=utc(accepted), replacement=None)
    expiry = accepted + timedelta(days=policy["defaults"]["support_days"])
    result.update(support_ends_at=utc(expiry),
                  warning_starts_at=utc(expiry - timedelta(days=policy["defaults"]["warning_days"])),
                  removal_eligible_at=utc(expiry + timedelta(days=policy["defaults"]["removal_grace_days"])))
    return validate_group(result, root, available=True)


def group_status(group, now=None):
    value = clock(now)
    if group["state"] != "accepted":
        return "planned"
    if value < timestamp(group["accepted_at"]):
        return "not-yet-supported"
    if value >= timestamp(group["support_ends_at"]):
        return "unsupported"
    if value >= timestamp(group["warning_starts_at"]):
        return "warning"
    return "supported"


def check_selection(policy, lock, observed, *, now=None, fetched_at=None, root=None):
    result = {"ok": False, "status": "unsupported", "code": "support-check-failed", "errors": [], "warnings": []}
    def error(code, message, action, **fields):
        result["errors"].append(dict(code=code, message=message, action=action, **fields))
    try:
        validate_policy(policy, root)
        value = clock(now)
        if fetched_at is None:
            error("policy-not-fetched", "No current policy fetch receipt supplied", "Fetch current support policy before running")
        else:
            fetched = clock(fetched_at)
            if fetched > value or value - fetched >= timedelta(hours=policy["defaults"]["max_policy_age_hours"]):
                error("policy-stale", "Policy fetch receipt is stale or in the future", "Fetch current support policy again")
        _keys(lock, {"schema_version", "group", "resources"})
        if lock["schema_version"] != 1 or not isinstance(lock["resources"], list) or not lock["resources"]:
            raise ValueError("Lock requires schema version 1 and nonempty resources")
        group = next((g for g in policy["groups"] if g["id"] == lock["group"]), None)
        if group is None:
            error("group-unknown", f"Group is not accepted: {lock['group']}", "Select and validate an accepted release group")
        else:
            status = group_status(group, value)
            result.update(status=status, support_ends_at=group["support_ends_at"], removal_eligible_at=group["removal_eligible_at"])
            replacements = [g for g in policy["groups"] if group_status(g, value) in {"supported", "warning"}]
            replacement = group["replacement"] or (max(replacements, key=lambda g: timestamp(g["accepted_at"]))["id"] if replacements else None)
            result["replacement_group"] = replacement
            if status in {"unsupported", "not-yet-supported"}:
                error("group-expired" if status == "unsupported" else "group-not-yet-supported",
                      f"Release group {group['id']} is {status}", "Validate a supported replacement and update the group lock", replacement_group=replacement)
            elif status == "warning":
                result["warnings"].append({"code": "group-expiring", "message": f"Group expires at {group['support_ends_at']}", "action": "Validate replacement before expiry", "replacement_group": replacement})
            members = {m["line_id"]: m for m in group["resources"]}
            actual = observed.get("resources") if isinstance(observed, dict) else observed
            if not isinstance(actual, list):
                raise ValueError("Actual images must be a resources list")
            seen = set()
            for expected in lock["resources"]:
                _keys(expected, {"line_id", "version", "identity", "platform"}, {"service"})
                key = (expected["line_id"], expected.get("service"))
                if key in seen:
                    raise ValueError("Duplicate locked resource/service")
                seen.add(key)
                member = members.get(expected["line_id"])
                if (member is None or expected["version"] != member["version"] or expected["identity"] != member["identity"]
                        or expected["platform"] not in {p["platform"] for p in member["platforms"]}):
                    error("selection-outside-group", f"Selection differs from group: {expected['line_id']}", "Pin exact group identity, revision and verified platform")
                    continue
                matches = [a for a in actual if isinstance(a, dict) and a.get("line_id") == expected["line_id"]
                           and a.get("service") == expected.get("service")]
                if len(matches) != 1:
                    error("actual-image-missing", f"No unique actual image for {expected['line_id']}", "Inspect the image or running container before use")
                    continue
                valid = {member["identity"], member["identity"].split("@")[0] + "@" + next(p["digest"] for p in member["platforms"] if p["platform"] == expected["platform"])}
                if matches[0].get("identity") not in valid or matches[0].get("platform") != expected["platform"]:
                    error("actual-image-mismatch", f"Actual artifact differs from locked image: {expected['line_id']}", "Use the accepted group digest for the verified platform")
        result["ok"] = not result["errors"]
        if not result["ok"]:
            result["status"] = "unsupported"
        result["code"] = "support-check-passed" if result["ok"] else result["errors"][0]["code"]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        error("policy-or-lock-invalid", str(exc), "Repair the policy or selection lock; aliases and unverified identities are rejected")
        result["code"] = "policy-or-lock-invalid"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path, default=ROOT / "lifecycle/release-groups.json")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--previous", type=Path)
    validate.add_argument("--group", type=Path)
    plan = commands.add_parser("plan")
    plan.add_argument("--at", required=True)
    plan.add_argument("--id")
    plan.add_argument("--reason", choices=["scheduled", "security", "migration"], default="scheduled")
    plan.add_argument("--selections", type=Path, help="JSON line_id-to-version map (exact parents added)")
    accept = commands.add_parser("accept")
    accept.add_argument("group", type=Path)
    accept.add_argument("--accepted-at", required=True)
    check = commands.add_parser("check")
    check.add_argument("--lock", type=Path, required=True)
    check.add_argument("--actual", type=Path, required=True)
    check.add_argument("--fetched-at", required=True, help="Operator-supplied test receipt; integrated checks use actual bounded HTTP fetch")
    check.add_argument("--now")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        if args.command == "validate":
            validate_policy(policy, args.root, load_policy(args.previous) if args.previous else None)
            if args.group:
                validate_group(load_policy(args.group), args.root, available=True)
            output = {"ok": True, "code": "release-groups-valid"}
        elif args.command == "plan":
            output = plan_group(policy, root=args.root, at=args.at, group_id=args.id, reason=args.reason,
                                selections=load_policy(args.selections) if args.selections else None)
        elif args.command == "accept":
            output = accept_group(policy, load_policy(args.group), root=args.root, accepted_at=args.accepted_at)
        else:
            output = check_selection(policy, load_policy(args.lock), load_policy(args.actual), root=args.root,
                                     now=args.now, fetched_at=args.fetched_at)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if output.get("ok", True) else 2
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"ok": False, "code": "release-groups-invalid", "message": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
