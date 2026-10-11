"""Resolve small explicit profiles to verified resource identities without writes."""
import copy
import hashlib

from .model import ROOT, encoded, relative_path, validate_schema, version


def _source_hash(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def _pin_identity(pin):
    return {key: pin[key] for key in ("id", "version", "identity")}


def _overlay(profile, target, overlay):
    result, facts = copy.deepcopy(profile), copy.deepcopy(target)
    if overlay is None:
        return result, facts
    if not isinstance(overlay, dict) or set(overlay) - {"roles", "target"}:
        raise ValueError("Private overlay accepts only roles and target")
    overrides = overlay.get("roles", {})
    if not isinstance(overrides, dict):
        raise ValueError("Overlay roles must be keyed by existing role name")
    names = {role["name"] for role in result["roles"]}
    if set(overrides) - names:
        raise ValueError("Overlay references unknown roles: " + ", ".join(sorted(set(overrides) - names)))
    for role in result["roles"]:
        if role["name"] in overrides:
            values = overrides[role["name"]]
            if not isinstance(values, dict) or "name" in values:
                raise ValueError("Overlay role fields must be an object without name")
            role.update(copy.deepcopy(values))
    target_overrides = overlay.get("target", {})
    if not isinstance(target_overrides, dict) or set(target_overrides) - {"platform", "commands", "harness", "scope"}:
        raise ValueError("Overlay target accepts platform, commands, harness, and scope")
    facts.update(copy.deepcopy(target_overrides))
    return result, facts


def compatibility(resource, target):
    """Report missing facts separately from known prerequisite/platform mismatches."""
    gaps = []
    if resource["lifecycle"] != "available" or resource["verification"]["status"] != "passed":
        return [{"code": "release_unavailable", "id": resource["id"], "version": resource["version"]}]
    if "any" not in resource["targets"]:
        if not target.get("platform"):
            gaps.append({"code": "target_fact_missing", "fact": "platform"})
        elif target["platform"] not in resource["targets"]:
            gaps.append({"code": "untested_target", "platform": target["platform"], "tested": resource["targets"]})
    required = resource["prerequisites"].get("commands", [])
    if required and "commands" not in target:
        gaps.append({"code": "target_fact_missing", "fact": "commands", "required": required})
    elif required:
        missing = sorted(set(required) - set(target["commands"]))
        if missing:
            gaps.append({"code": "missing_prerequisite", "commands": missing})
    scope = resource["details"].get("scope")
    if scope:
        if not target.get("scope"):
            gaps.append({"code": "target_fact_missing", "fact": "scope"})
        elif scope != target["scope"]:
            gaps.append({"code": "scope_mismatch", "expected": scope, "actual": target["scope"]})
    if resource["kind"] == "context":
        audience = resource["details"]["audience"]
        audiences = audience if isinstance(audience, list) else [audience]
        if "any" not in audiences:
            if not target.get("harness"):
                gaps.append({"code": "target_fact_missing", "fact": "harness", "audience": audiences})
            elif target["harness"] not in audiences:
                gaps.append({"code": "audience_mismatch", "expected": audiences, "actual": target["harness"]})
    return gaps


def validate_lock(lock, cat, root=ROOT):
    """Validate a local lock against accepted release metadata before using it."""
    validate_schema(lock, "resolution-lock.schema.json", root)
    accepted = {(item["id"], item["version"], item["identity"]): item for item in cat["resources"]}
    identities, destinations = set(), {}
    for item in lock["resources"]:
        identity = (item["id"], item["version"], item["identity"])
        if item["id"] in identities:
            raise ValueError(f"Duplicate resource in lock: {item['id']}")
        identities.add(item["id"])
        record = accepted.get(identity)
        compact = {key: value for key, value in item.items() if key not in ("role", "roles")}
        if not record or compact != record:
            raise ValueError(f"Lock metadata disagrees with accepted release: {item['id']}")
        if compatibility(item, lock["target"]):
            raise ValueError(f"Locked resource is unavailable or incompatible: {item['id']}")
        paths = []
        if item["kind"] == "binary":
            paths.append(item["details"]["executable"])
        elif item["kind"] != "image":
            for mapping in item["details"]["files"]:
                relative_path(mapping["source"])
                paths.append(mapping["destination"])
        for destination in paths:
            path = relative_path(destination)
            for previous, owner in destinations.items():
                if path == previous or path in previous.parents or previous in path.parents:
                    raise ValueError(f"File destination conflict: {destination} ({owner}, {item['id']})")
            destinations[path] = item["id"]
    selected = {item["id"]: item for item in lock["resources"]}
    complete = set()

    def dependencies(item, visiting):
        if item["id"] in visiting:
            raise ValueError("Dependency cycle in lock: " + " -> ".join(visiting + (item["id"],)))
        if item["id"] in complete:
            return
        for dependency in item["prerequisites"].get("resources", []):
            child = selected.get(dependency["id"])
            if child is None or (dependency.get("version") and child["version"] != dependency["version"]):
                raise ValueError(f"Missing required dependency in lock: {item['id']} -> {dependency['id']}")
            dependencies(child, visiting + (item["id"],))
        complete.add(item["id"])

    for item in lock["resources"]:
        dependencies(item, ())
    return lock


def resolve(profile, cat, target, pins=None, overlay=None, profile_sha256=None, overlay_sha256=None, root=ROOT):
    """Return status/resolved lock or status/resolution_failed with precise gaps.

    pins may be a prior lock or its resources list. Existing pins are retained;
    asking for an upgrade means deliberately omitting/replacing those pins.
    """
    original = copy.deepcopy(profile)
    profile, target = _overlay(profile, target, overlay)
    validate_schema(profile, "profile.schema.json", root)
    # Reuse target validation from the lock schema without manufacturing facts.
    stub = {"schema_version": 2,
            "profile": {"id": profile["id"], "revision": profile["revision"], "sha256": _source_hash(original)},
            "target": target, "resources": []}
    validate_schema(stub, "resolution-lock.schema.json", root)
    validate_schema(cat, "catalog-v2.schema.json", root)
    names = [role["name"] for role in profile["roles"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate profile role")
    entries = cat["resources"]
    if len({(item["id"], item["version"]) for item in entries}) != len(entries):
        raise ValueError("Duplicate catalog release identity")
    pin_items = pins.get("resources", []) if isinstance(pins, dict) else (pins or [])
    pins_by_role, pins_by_id = {}, {}
    for pin in pin_items:
        for role in pin.get("roles", [pin.get("role")]):
            if role:
                if role in pins_by_role and _pin_identity(pins_by_role[role]) != _pin_identity(pin):
                    raise ValueError(f"Conflicting pins for role {role}")
                pins_by_role[role] = pin
        if pin["id"] in pins_by_id and _pin_identity(pins_by_id[pin["id"]]) != _pin_identity(pin):
            raise ValueError(f"Conflicting pins for {pin['id']}")
        pins_by_id[pin["id"]] = pin
    selected, gaps, skipped = {}, [], []

    def choose(alternatives, role, pin=None):
        candidates, mismatches = [], []
        # Role names describe assignments, not artifact identity. A renamed or
        # additional role still retains an existing pin for the same resource.
        retained = {pin["id"]: pin} if pin else {
            alternative["id"]: pins_by_id[alternative["id"]]
            for alternative in alternatives if alternative["id"] in pins_by_id
        }
        if pin and pin["id"] not in {alternative["id"] for alternative in alternatives}:
            mismatches.append({**_pin_identity(pin), "reasons": [{
                "code": "pin_resource_mismatch",
                "requested": [alternative["id"] for alternative in alternatives],
            }]})
        for alternative in alternatives:
            retained_pin = retained.get(alternative["id"])
            if retained and retained_pin is None:
                continue
            if retained_pin and alternative.get("version") and alternative["version"] != retained_pin["version"]:
                mismatches.append({**_pin_identity(retained_pin), "reasons": [{
                    "code": "pin_version_mismatch", "requested": alternative["version"],
                    "pinned": retained_pin["version"],
                }]})
                continue
            releases = [item for item in entries if item["id"] == alternative["id"]
                        and (not alternative.get("version") or item["version"] == alternative["version"])]
            if retained_pin:
                releases = [item for item in releases if item["version"] == retained_pin["version"]
                            and item["identity"] == retained_pin["identity"]]
                if not releases:
                    mismatches.append({**_pin_identity(retained_pin), "reasons": [{"code": "pin_not_accepted"}]})
            compatible = []
            for item in releases:
                reasons = compatibility(item, target)
                if reasons:
                    mismatches.append({"id": item["id"], "version": item["version"], "reasons": reasons})
                else:
                    compatible.append(item)
            if compatible:
                candidates.append(max(compatible, key=lambda item: version(item["version"])))
        unique = {}
        for item in candidates:
            previous = unique.get(item["id"])
            if previous is None or version(item["version"]) > version(previous["version"]):
                unique[item["id"]] = item
        if len(unique) == 1:
            return next(iter(unique.values())), None
        if len(unique) > 1:
            return None, {"role": role, "code": "ambiguous_resources",
                          "candidates": [{"id": item["id"], "version": item["version"]} for item in unique.values()]}
        error = {"role": role, "code": "pin_unverified_or_incompatible" if retained else "no_matching_resource",
                 "alternatives": copy.deepcopy(alternatives), "mismatches": mismatches}
        if retained:
            error["pins"] = [_pin_identity(item) for item in retained.values()]
        return None, error

    def add(item, role, visiting=()):
        if item["id"] in visiting:
            gaps.append({"role": role, "code": "dependency_cycle", "cycle": list(visiting) + [item["id"]]})
            return
        previous = selected.get(item["id"])
        if previous:
            if previous["identity"] != item["identity"] or previous["version"] != item["version"]:
                gaps.append({"role": role, "code": "conflicting_resources", "id": item["id"],
                             "versions": [previous["version"], item["version"]]})
            elif role not in previous["roles"]:
                previous["roles"].append(role)
            return
        dependencies = item["prerequisites"].get("resources", [])
        for dependency in dependencies:
            dependency_role = "dependency:" + dependency["id"]
            child, error = choose([dependency], dependency_role, pins_by_id.get(dependency["id"]))
            if error:
                gaps.append(error)
            else:
                add(child, dependency_role, visiting + (item["id"],))
        result = copy.deepcopy(item)
        result.update(role=role, roles=[role])
        selected[item["id"]] = result

    for role in profile["roles"]:
        applies = True
        for fact, expected in role.get("when", {}).items():
            if fact not in target:
                gaps.append({"role": role["name"], "code": "target_fact_missing", "fact": fact})
                applies = False
            elif target[fact] not in (expected if isinstance(expected, list) else [expected]):
                applies = False
        if not applies:
            skipped.append({"role": role["name"], "reason": "target_condition"})
            continue
        pin = pins_by_role.get(role["name"])
        item, error = choose(role["alternatives"], role["name"], pin)
        if error:
            if role.get("optional") and not pin and error["code"] == "no_matching_resource":
                skipped.append({"role": role["name"], "reason": error})
            else:
                gaps.append(error)
        else:
            add(item, role["name"])
    if gaps:
        return {"status": "resolution_failed", "gaps": gaps, "skipped": skipped}
    lock_profile = {"id": profile["id"], "revision": profile["revision"],
                    "sha256": profile_sha256 or _source_hash(original)}
    if overlay is not None:
        lock_profile["overlay_sha256"] = overlay_sha256 or _source_hash(overlay)
    lock = {"schema_version": 2, "profile": lock_profile, "target": target,
            "resources": list(selected.values())}
    try:
        validate_lock(lock, cat, root)
    except ValueError as error:
        return {"status": "resolution_failed", "gaps": [{"code": "file_destination_conflict", "reason": str(error)}], "skipped": skipped}
    return {"status": "resolved", "lock": lock, "skipped": skipped}
