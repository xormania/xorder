#!/usr/bin/env python3
"""Plan GHCR retention from explicit inventory facts; never mutate the registry."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
PACKAGE = re.compile(r"ghcr\.io/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9._/-]*")


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("A timezone-qualified timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid timestamp: {value}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def identity(value):
    if not isinstance(value, str) or "@" not in value:
        raise ValueError(f"Exact GHCR digest required: {value}")
    package, digest = value.rsplit("@", 1)
    if not PACKAGE.fullmatch(package) or not DIGEST.fullmatch(digest):
        raise ValueError(f"Exact GHCR digest required: {value}")
    return package, digest


def positive_days(value, name):
    if type(value) is not int or not 1 <= value <= 365:
        raise ValueError(f"{name} must be an integer between 1 and 365")
    return value


def validate_snapshot(snapshot):
    """Reject inconsistent scope, duplicate objects and malformed observed facts."""
    if not isinstance(snapshot, dict):
        raise ValueError("Retention inventory must be an object")
    if snapshot.get("schema_version") != 1:
        raise ValueError("Unsupported retention inventory schema")
    timestamp(snapshot.get("observed_at"))
    scope = snapshot.get("scope", {})
    if scope.get("repository") != "xormania/xorder":
        raise ValueError("Inventory must explicitly name repository xormania/xorder")
    packages = scope.get("packages", [])
    if not isinstance(packages, list) or not packages or any(not isinstance(p, str) for p in packages) or len(packages) != len(set(packages)):
        raise ValueError("Inventory must declare distinct package scopes")
    for package in packages:
        if not PACKAGE.fullmatch(package) or not package.startswith("ghcr.io/xormania/"):
            raise ValueError(f"Package outside xormania inventory scope: {package}")
    for flag in ("versions_complete", "references_complete", "publications_complete"):
        if type(snapshot.get(flag)) is not bool:
            raise ValueError(f"Explicit boolean required: {flag}")
    seen, version_ids, tag_owners = set(), set(), {}
    if not isinstance(snapshot.get("items"), list):
        raise ValueError("Explicit registry item inventory is required")
    for item in snapshot["items"]:
        if not isinstance(item, dict):
            raise ValueError("Registry item must be an object")
        ref = item["identity"]
        package, _ = identity(ref)
        if package not in packages or ref in seen:
            raise ValueError(f"Duplicate digest or item outside declared scope: {ref}")
        seen.add(ref)
        if item.get("kind") not in ("image", "candidate", "cache", "evidence", "unknown"):
            raise ValueError(f"Unknown item kind: {ref}")
        timestamp(item["created_at"])
        for key in ("tags", "dependencies", "version_ids"):
            values = item.get(key)
            expected = int if key == "version_ids" else str
            if not isinstance(values, list) or any(type(v) is not expected for v in values) or len(values) != len(set(values)):
                raise ValueError(f"Distinct list required: {ref} {key}")
        if type(item.get("references_complete")) is not bool:
            raise ValueError(f"Explicit reference completeness required: {ref}")
        for version in item["version_ids"]:
            if type(version) is not int or version < 1 or (package, version) in version_ids:
                raise ValueError(f"Duplicate or invalid GHCR package version: {version}")
            version_ids.add((package, version))
        for tag in item["tags"]:
            if not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
                raise ValueError(f"Invalid registry tag: {tag}")
            if (package, tag) in tag_owners:
                raise ValueError(f"Tag claimed by multiple digests: {package}:{tag}")
            tag_owners[package, tag] = ref
        for dependency in item["dependencies"]:
            identity(dependency)
        owners = item.get("owners", [])
        if not isinstance(owners, list) or any(not isinstance(o, str) for o in owners) or len(owners) != len(set(owners)):
            raise ValueError(f"Distinct evidence owners required: {ref}")
        if owners and item["kind"] != "evidence":
            raise ValueError("Only evidence objects inherit owner retention")
        for owner in owners:
            identity(owner)
        if item["kind"] == "cache":
            timestamp(item["last_used_at"])
            branch = item.get("branch", {})
            if branch.get("state") not in ("open", "closed", "unknown"):
                raise ValueError(f"Cache needs observed branch state: {ref}")
            if branch["state"] == "closed":
                timestamp(branch["closed_at"])
    attempts = snapshot.get("publications")
    if not isinstance(attempts, list):
        raise ValueError("Explicit publication-attempt inventory is required")
    attempt_ids = set()
    for attempt in attempts:
        attempt_id = attempt.get("id")
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in attempt_ids:
            raise ValueError("Distinct publication attempt IDs are required")
        attempt_ids.add(attempt_id)
        if attempt.get("state") not in ("active", "abandoned"):
            raise ValueError("Publication state must be active or abandoned")
        if not isinstance(attempt.get("identities"), list) or not attempt["identities"]:
            raise ValueError("Publication attempts need exact observed identities")
        for ref in attempt["identities"]:
            package, _ = identity(ref)
            if package not in packages:
                raise ValueError(f"Publication outside inventory scope: {ref}")
        if attempt["state"] == "abandoned":
            timestamp(attempt["ended_at"])
    for pin in snapshot.get("pins", []):
        identity(pin["identity"])
        if not pin.get("consumer"):
            raise ValueError("Downstream pins need a consumer name")
    for blob in snapshot.get("blobs", []):
        if not DIGEST.fullmatch(blob["digest"]) or type(blob.get("size_bytes")) is not int or blob["size_bytes"] < 0:
            raise ValueError("Blob facts need an exact digest and nonnegative byte count")
        if type(blob.get("references_complete")) is not bool:
            raise ValueError("Explicit blob reference completeness is required")
        if not isinstance(blob.get("references"), list) or not blob["references"]:
            raise ValueError("Blob facts need manifest references")
        for ref in blob["references"]:
            identity(ref)
    return snapshot


def release_references(record):
    publication = record["publication"]
    package = publication["repository"]
    refs = {package + "@" + publication["digest"]}
    refs.update(package + "@" + item["digest"] for item in record["platforms"])
    return refs


def plan(snapshot, policy, releases, now=None, *, cache_days=14, closed_branch_days=2):
    """Return keep/expire/removal sets, with expiry never extended by a consumer pin."""
    validate_snapshot(snapshot)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Planning time needs a timezone")
    cache_days = positive_days(cache_days, "cache_days")
    closed_branch_days = positive_days(closed_branch_days, "closed_branch_days")
    items = {item["identity"]: item for item in snapshot["items"]}
    scope = set(snapshot["scope"]["packages"])
    blockers = []
    observed = timestamp(snapshot["observed_at"])
    if observed > now:
        raise ValueError("Inventory was observed after the planning time")
    max_age = policy.get("defaults", {}).get("max_policy_age_hours", 24)
    if type(max_age) is not int or max_age < 1:
        raise ValueError("Policy max_policy_age_hours must be a positive integer")
    if now - observed > timedelta(hours=max_age):
        blockers.append("Inventory is stale; refresh registry, references and publication states")
    for flag in ("versions_complete", "references_complete", "publications_complete"):
        if not snapshot[flag]:
            blockers.append(f"Inventory fact is incomplete: {flag}")
    graph = {ref: set(item["dependencies"]) for ref, item in items.items()}
    for ref, item in items.items():
        if timestamp(item["created_at"]) > observed:
            raise ValueError(f"Item creation is after observation: {ref}")
        if not item["references_complete"]:
            blockers.append(f"Dependencies/referrers were not completely observed: {ref}")
        if item["kind"] == "cache" and timestamp(item["last_used_at"]) > observed:
            raise ValueError(f"Cache usage is after observation: {ref}")
        for owner in item.get("owners", []):
            if owner not in items or items[owner]["kind"] == "evidence":
                blockers.append(f"Evidence owner is missing or not a retention root: {ref} -> {owner}")
            graph.setdefault(owner, set()).add(ref)
    # The ledger adds parent edges; a snapshot cannot silently omit these facts.
    release_by_ref = defaultdict(list)
    for record in releases:
        refs = release_references(record)
        parent = record.get("resolved_base", "")
        for ref in refs:
            release_by_ref[ref].append(record)
            graph.setdefault(ref, set()).update(refs - {ref})
            if parent.startswith("ghcr.io/"):
                identity(parent)
                graph[ref].add(parent)
    groups_by_ref = defaultdict(list)
    for group in policy.get("groups", []):
        for resource in group["resources"]:
            package, _ = identity(resource["identity"])
            refs = {resource["identity"]}
            refs.update(package + "@" + p["digest"] for p in resource["platforms"])
            for ref in refs:
                groups_by_ref[ref].append(group)
                graph.setdefault(ref, set()).update(refs - {ref})
                if resource.get("parent"):
                    identity(resource["parent"])
                    graph[ref].add(resource["parent"])
    attempts_by_ref = defaultdict(list)
    for attempt in snapshot["publications"]:
        if attempt["state"] == "abandoned" and timestamp(attempt["ended_at"]) > observed:
            raise ValueError("Publication ended after the inventory observation")
        for ref in attempt["identities"]:
            attempts_by_ref[ref].append(attempt)
            if ref not in items:
                blockers.append(f"Publication candidate missing from inventory: {ref}")
    decisions = {}
    legacy_end = policy.get("legacy", {}).get("enforce_after")
    legacy_removal = (timestamp(legacy_end) + timedelta(days=policy["defaults"]["removal_grace_days"])) if legacy_end else None
    protected_roots = set()
    for ref in set(release_by_ref) | set(groups_by_ref):
        groups = groups_by_ref[ref]
        protected = any(now < timestamp(g["removal_eligible_at"]) for g in groups)
        if not groups and release_by_ref[ref]:
            protected = not legacy_removal or now < legacy_removal
        if protected:
            protected_roots.add(ref)
            if identity(ref)[0] in scope and ref not in items:
                blockers.append(f"Protected release digest is absent from inventory: {ref}")
    for ref, deps in graph.items():
        if ref not in items and ref not in protected_roots:
            continue
        for dependency in deps:
            if identity(dependency)[0] in scope and dependency not in items:
                blockers.append(f"Referenced in-scope digest is missing: {ref} -> {dependency}")
    for ref, item in items.items():
        reason, status, remove_at = [], "keep", None
        groups = groups_by_ref[ref]
        active = [g for g in groups if now < timestamp(g["support_ends_at"])]
        publications = attempts_by_ref[ref]
        if active:
            reason.append("Supported release group: " + ", ".join(sorted(g["id"] for g in active)))
        elif any(a["state"] == "active" for a in publications):
            reason.append("Active publication attempt")
        elif groups:
            status = "expire"
            remove_at = max(timestamp(g["removal_eligible_at"]) for g in groups)
            reason.append("All release groups have reached their announced support deadline")
        elif release_by_ref[ref]:
            if not legacy_end or now < timestamp(legacy_end):
                reason.append("Legacy release protected until an announced migration deadline")
            else:
                status, remove_at = "expire", legacy_removal
                reason.append("Legacy migration deadline reached")
        elif publications:
            remove_at = max(timestamp(a["ended_at"]) + timedelta(days=7) for a in publications)
            status = "expire"
            reason.append("Abandoned publication; seven-day recovery window")
        elif item["kind"] == "cache":
            branch = item["branch"]
            if branch["state"] == "unknown":
                reason.append("Unknown branch state prevents proving cache retirement")
            else:
                remove_at = timestamp(item["last_used_at"]) + timedelta(days=cache_days)
                if branch["state"] == "closed":
                    if timestamp(branch["closed_at"]) > observed:
                        raise ValueError("Branch closed after observation")
                    remove_at = min(remove_at, timestamp(branch["closed_at"]) + timedelta(days=closed_branch_days))
                status = "expire" if now >= remove_at else "keep"
                reason.append("Bounded cache retention: inactivity or observed branch closure")
        else:
            reason.append("No announced release deadline or proven abandoned publication; ownership is unknown")
        if remove_at and publications and all(a["state"] == "abandoned" for a in publications):
            recovery = max(timestamp(a["ended_at"]) + timedelta(days=7) for a in publications)
            remove_at = max(remove_at, recovery)
        decisions[ref] = {"identity": ref, "kind": item["kind"], "version_ids": item["version_ids"],
                          "tags": item["tags"], "status": status, "reasons": reason,
                          "removal_eligible_at": remove_at.isoformat().replace("+00:00", "Z") if remove_at else None}
    for ref, item in items.items():
        owners = item.get("owners", [])
        if item["kind"] != "evidence" or not owners or any(owner not in decisions for owner in owners):
            continue
        owner_decisions = [decisions[owner] for owner in owners]
        if all(d["status"] == "expire" and d["removal_eligible_at"] for d in owner_decisions):
            decisions[ref].update(status="expire", removal_eligible_at=max(
                timestamp(d["removal_eligible_at"]) for d in owner_decisions).isoformat().replace("+00:00", "Z"),
                reasons=["Evidence follows all exact owner digests' retention deadlines"])
    # Every object being retained protects its transitive dependencies and evidence.
    retained = {ref for ref, d in decisions.items() if d["status"] == "keep" or
                (d["removal_eligible_at"] and now < timestamp(d["removal_eligible_at"]))}
    retained.update(protected_roots)
    pending = list(retained)
    while pending:
        ref = pending.pop()
        for dependency in graph.get(ref, ()):
            if dependency in decisions and dependency not in retained:
                retained.add(dependency)
                pending.append(dependency)
                decisions[dependency]["status"] = "keep"
                decisions[dependency]["reasons"].append(f"Dependency/evidence of retained digest: {ref}")
    for ref, decision in decisions.items():
        if decision["status"] == "expire" and decision["removal_eligible_at"] and now >= timestamp(decision["removal_eligible_at"]):
            if ref not in retained and not blockers:
                decision["status"] = "removal"
                decision["reasons"].append("Recovery/grace window complete and references accounted for")
            elif blockers:
                decision["reasons"].append("Removal cannot be proven: inventory has unresolved facts")
    notices = []
    for pin in snapshot.get("pins", []):
        ref = pin["identity"]
        groups = groups_by_ref[ref]
        active = [g for g in groups if now < timestamp(g["support_ends_at"])]
        if active:
            latest = max(active, key=lambda g: timestamp(g["support_ends_at"]))
            if now < timestamp(latest["warning_starts_at"]):
                continue
            state, deadline, replacement = "warning", latest["support_ends_at"], latest.get("replacement")
        elif groups:
            latest = max(groups, key=lambda g: timestamp(g["support_ends_at"]))
            state, deadline, replacement = "expired", latest["support_ends_at"], latest.get("replacement")
        elif legacy_end:
            state, deadline, replacement = ("expired" if now >= timestamp(legacy_end) else "migration"), legacy_end, None
        else:
            continue
        notices.append({"consumer": pin["consumer"], "identity": ref, "state": state,
                        "support_ends_at": deadline, "replacement_group": replacement,
                        "note": "Consumer pins do not extend the announced retention deadline"})
    removal = {ref for ref, d in decisions.items() if d["status"] == "removal"}
    exclusive, observed_blobs, unknown_blobs = 0, {}, []
    for blob in snapshot.get("blobs", []):
        key = blob["digest"]
        if key in observed_blobs:
            raise ValueError(f"Blob facts must be consolidated by unique digest: {key}")
        observed_blobs[key] = blob
        refs = set(blob["references"])
        if blob["references_complete"] and refs <= removal:
            exclusive += blob["size_bytes"]
        elif refs & removal and not blob["references_complete"]:
            unknown_blobs.append(key)
    rows = sorted(decisions.values(), key=lambda d: d["identity"])
    return {"schema_version": 1, "mode": "dry-run", "observed_at": snapshot["observed_at"],
            "planned_at": now.isoformat().replace("+00:00", "Z"), "policy_revision": policy.get("revision"),
            "sets": {state: [d for d in rows if d["status"] == state] for state in ("keep", "expire", "removal")},
            "migration_notices": notices, "unknown_facts": sorted(set(blockers)),
            "counts": {"distinct_package_digests": len(items), "tags": sum(len(i["tags"]) for i in items.values()),
                       "proposed_removal_digests": len(removal)},
            "reclaim": {"known_exclusive_blob_bytes": exclusive,
                        "total_reclaimable_bytes": None,
                        "unknown_blob_digests": sorted(unknown_blobs),
                        "note": "Exclusive observed blob bytes are a lower bound on unreferenced data; registry garbage collection and billing reclamation remain unknown. Compressed image sizes are never summed."}}


def readable(result):
    rows = ["# Registry retention plan", "", "Mode: dry-run. No registry or release records are changed.", "",
            f"Observed: {result['observed_at']}. Planned: {result['planned_at']}.", ""]
    for state, items in result["sets"].items():
        rows.extend([f"## {state.capitalize()} ({len(items)} digests)", ""])
        rows.extend(f"- `{item['identity']}`: {'; '.join(item['reasons'])}" for item in items)
        rows.append("")
    if result["migration_notices"]:
        rows.extend(["## Consumer migrations", ""])
        rows.extend(f"- {n['consumer']}: {n['state']} at {n['support_ends_at']}; replacement {n['replacement_group'] or 'not announced'}. Pins do not extend retention."
                    for n in result["migration_notices"])
        rows.append("")
    rows.extend(["## Unresolved facts", ""])
    rows.extend(f"- {fact}" for fact in result["unknown_facts"])
    rows.extend(["", f"Known exclusive blob bytes: {result['reclaim']['known_exclusive_blob_bytes']}.",
                 result["reclaim"]["note"], ""])
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--policy", type=Path, default=ROOT / "lifecycle/release-groups.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--now", help="Explicit timezone-qualified planning time")
    parser.add_argument("--cache-days", type=int, default=14)
    parser.add_argument("--closed-branch-days", type=int, default=2)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    from library import records
    from release_groups import load_policy, validate_policy
    policy = load_policy(args.policy)
    validate_policy(policy, args.root)
    result = plan(json.loads(args.inventory.read_text()), policy, records(args.root),
                  timestamp(args.now) if args.now else None, cache_days=args.cache_days,
                  closed_branch_days=args.closed_branch_days)
    print(json.dumps(result, indent=2, sort_keys=True) if args.format == "json" else readable(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, AssertionError) as error:
        print(f"retention: {error}", file=sys.stderr)
        sys.exit(2)
