"""Authored resource intent and compact views of verified release facts."""
import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("binary", "environment", "configuration", "context")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def read(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def version(value):
    if not SEMVER.fullmatch(value):
        raise ValueError(f"Invalid resource revision: {value}")
    return tuple(map(int, value.split(".")))


def validate_schema(value, name, root=ROOT):
    from jsonschema import Draft202012Validator, FormatChecker
    schema = read(Path(root) / "schemas" / name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def relative_path(value):
    path = PurePosixPath(value)
    if (not value or str(path) != value or path.is_absolute()
            or any(part in ("..", ".") for part in value.split("/")) or "\\" in value):
        raise ValueError(f"Expected contained relative path: {value}")
    return path


def validate_definition(definition, root=ROOT):
    validate_schema(definition, "resource.schema.json", root)
    if definition["id"] != f"{definition['kind']}/{definition['name']}":
        raise ValueError("Resource id must equal kind/name")
    relative_path(definition["documentation"])
    if definition["kind"] == "binary":
        relative_path(definition["details"]["executable"])
        if len(relative_path(definition["details"]["filename"]).parts) != 1:
            raise ValueError("Binary download filename must be a leaf name")
    else:
        sources, destinations = [], []
        for item in definition["details"]["files"]:
            relative_path(item["source"])
            relative_path(item["destination"])
            sources.append(item["source"])
            destinations.append(item["destination"])
        if len(sources) != len(set(sources)):
            raise ValueError("Duplicate source in resource definition")
        if len(destinations) != len(set(destinations)):
            raise ValueError("Duplicate destination in resource definition")
        if any(first in second.parents
               for first in map(PurePosixPath, destinations) for second in map(PurePosixPath, destinations)):
            raise ValueError("Overlapping file destinations in resource definition")
    return definition


def definitions(root=ROOT):
    result = {}
    for path in sorted((Path(root) / "artifacts").glob("*/*/definition.json")):
        definition = validate_definition(read(path), root)
        if (path.parent.parent.name, path.parent.name) != (definition["kind"], definition["name"]):
            raise ValueError(f"Definition path disagrees with id: {path}")
        if definition["id"] in result:
            raise ValueError(f"Duplicate definition: {definition['id']}")
        result[definition["id"]] = definition
    return result


def profiles(root=ROOT):
    result = {}
    for path in sorted((Path(root) / "profiles").glob("*.json")):
        profile = read(path)
        validate_schema(profile, "profile.schema.json", root)
        if profile["id"] != f"profile/{path.stem}":
            raise ValueError(f"Profile path disagrees with id: {path}")
        names = [role["name"] for role in profile["roles"]]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate profile role: {path}")
        result[profile["id"]] = profile
    return result


def fingerprint(definition, root=ROOT):
    """Definition, payload, and referenced verification script content identity."""
    resource_root = Path(root) / "artifacts" / definition["kind"] / definition["name"]
    payload = resource_root / "payload"
    paths = set()
    payload_paths = set()
    if definition["kind"] != "binary":
        for mapping in definition["details"]["files"]:
            path = payload / relative_path(mapping["source"])
            if not path.resolve().is_relative_to(payload.resolve()) or not path.is_file():
                raise ValueError(f"Declared payload must be a contained file: {path}")
            paths.add(path)
            payload_paths.add(path)
    for argument in definition["verification"]["command"]:
        if argument.startswith("scripts/"):
            paths.add(Path(root) / relative_path(argument))
    digest = hashlib.sha256(encoded(definition).encode())
    for path in sorted(paths):
        if path.is_symlink():
            raise ValueError(f"Resource inputs must not be symlinks: {path}")
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            if path in payload_paths:
                # The archive normalizes executable files to 0755 and other
                # files to 0644; fingerprint the same published mode.
                mode = b"0755" if path.stat().st_mode & 0o111 else b"0644"
                digest.update(b"\0mode=" + mode + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_record(record, root=ROOT):
    validate_schema(record, "artifact-release-record.schema.json", root)
    definition = validate_definition(record["definition"], root)
    if record["id"] != definition["id"] or record["version"] != definition["revision"]:
        raise ValueError("Release identity disagrees with its definition snapshot")
    if record["source_tag"] != f"{record['id']}/v{record['version']}":
        raise ValueError("Release source tag disagrees with identity")
    if record["lifecycle"] != "available" and not all(record.get(key) for key in ("reason", "replacement", "lifecycle_date")):
        raise ValueError("Unavailable release needs reason, replacement, and lifecycle date")
    publication = record["publication"]
    if len(relative_path(publication["filename"]).parts) != 1:
        raise ValueError("Publication filename must be a leaf name")
    if definition["kind"] == "binary":
        if publication["format"] != "file" or publication["sha256"] != definition["details"]["sha256"]:
            raise ValueError("Binary publication must retain the reviewed source bytes")
        if publication["filename"] != definition["details"]["filename"]:
            raise ValueError("Binary publication filename disagrees with definition")
    elif publication["format"] != "tar":
        raise ValueError("Bundle publication must be a tar archive")
    return record


def records(root=ROOT):
    result = []
    for path in sorted((Path(root) / "release-records" / "artifacts").glob("*/*/*.json")):
        record = validate_record(read(path), root)
        expected = Path(root) / "release-records" / "artifacts" / record["id"] / f"{record['version']}.json"
        if path != expected:
            raise ValueError(f"Release path disagrees with identity: {path}")
        result.append(record)
    identities = [(record["id"], record["version"]) for record in result]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate resource release identity")
    return result


def image_entry(record):
    d, pub = record["definition"], record["publication"]
    item = {
        "id": "image/" + record["line_id"], "kind": "image", "version": record["version"],
        "purpose": d["purpose"], "capabilities": d["capabilities"],
        "targets": [item["platform"] for item in record["platforms"]],
        "prerequisites": {"commands": ["docker"]},
        "identity": pub["repository"] + "@" + pub["digest"],
        "documentation": f"docs/images/{record['line_id'].replace('/', '-')}.md",
        "release_record": f"release-records/{record['line_id']}/{record['version']}.json",
        "lifecycle": record["lifecycle"], "created_at": record["created_at"],
        "verification": copy.deepcopy(record["verification"]),
        "details": {"runtime_line": d["runtime_line"], "family": d["family"],
                    "extensions": d["extensions"], "tools": d["tools"],
                    "exact_reference": pub["repository"] + ":" + pub["exact_tag"]},
    }

    if record.get("assurance"):
        item["assurance"] = copy.deepcopy(record["assurance"])
    return item


def artifact_entry(record):
    d, pub = record["definition"], record["publication"]
    item = {key: copy.deepcopy(d[key]) for key in
            ("id", "kind", "purpose", "capabilities", "targets", "prerequisites", "documentation", "details")}
    item.update(version=record["version"], identity="sha256:" + pub["sha256"],
                release_record=f"release-records/artifacts/{record['id']}/{record['version']}.json",
                lifecycle=record["lifecycle"], created_at=record["created_at"],
                verification=copy.deepcopy(record["verification"]),
                delivery={key: pub[key] for key in ("url", "sha256", "filename", "format", "size_bytes")})
    return item


def catalog(root=ROOT, image_records=None):
    if image_records is None:
        from library import records as image_ledger
        image_records = image_ledger(root)
    artifact_records = records(root)
    entries = [image_entry(record) for record in image_records] + [artifact_entry(record) for record in artifact_records]
    entries.sort(key=lambda item: (item["id"], version(item["version"])))
    return {"schema_version": 2,
            "generated_at": max((item["created_at"] for item in entries), default=None),
            "resources": entries}


def latest_artifacts(cat):
    latest = {}
    for item in cat["resources"]:
        if item["kind"] != "image" and item["lifecycle"] == "available":
            previous = latest.get(item["id"])
            if previous is None or version(item["version"]) > version(previous["version"]):
                latest[item["id"]] = item
    return [item for _, item in sorted(latest.items())]


def availability_table(cat):
    available = latest_artifacts(cat)
    if not available:
        return "No verified non-image releases yet. Authored definitions are not available artifacts."
    rows = ["| Resource | Revision | Target | Prerequisites | Exact identity |",
            "| --- | --- | --- | --- | --- |"]
    for item in available:
        prerequisites = ", ".join(f"`{command}`" for command in item["prerequisites"]["commands"]) or "See usage"
        rows.append(f"| [{item['id']}]({item['documentation']}) | {item['version']} | {', '.join(item['targets'])} | {prerequisites} | `{item['identity']}` |")
    return "\n".join(rows)


def resource_index(cat):
    text = ("# Verified downloadable resources\n\n"
            "Generated from accepted release records. Read the prerequisites and usage before applying a resource. "
            "Targets describe compatibility; verification evidence records the actual execution surface. "
            "Do not infer behavior in every vendor cloud. "
            "Profiles select these exact releases; authored definitions without records remain unavailable.\n\n")
    available = latest_artifacts(cat)
    if not available:
        return text + "No verified non-image releases yet.\n"
    for item in available:
        doc = "../../" + item["documentation"]
        ledger = "../../" + item["release_record"]
        text += (f"## {item['id']} v{item['version']}\n\n{item['purpose']}\n\n"
                 f"Exact identity: `{item['identity']}`. Declared targets: {', '.join(item['targets'])}.\n\n")
        commands = item["prerequisites"]["commands"]
        text += "Required commands: " + (", ".join(f"`{command}`" for command in commands) if commands else "none") + ".\n\n"
        requirements = item["prerequisites"].get("requirements", [])
        if requirements:
            text += "\n".join(f"- {requirement}" for requirement in requirements) + "\n\n"
        text += (f"[Usage]({doc}) · [Download]({item['delivery']['url']}) "
                 f"({item['delivery']['format']}, {item['delivery']['size_bytes']:,} bytes) · [Release record]({ledger}) · "
                 f"[Verification evidence]({item['verification']['evidence']}) "
                 f"({item['verification']['surface']}).\n\n")
    return text


def generated(root=ROOT, image_records=None):
    """Only verified records produce available entries; authored profiles stay separate."""
    definitions(root)
    profiles(root)
    cat = catalog(root, image_records)
    return {Path(root) / "catalog-v2.json": encoded(cat),
            Path(root) / "docs/resources/index.md": resource_index(cat)}


def check(root=ROOT):
    definitions(root)
    profiles(root)
    records(root)
    expected = catalog(root)
    validate_schema(expected, "catalog-v2.schema.json", root)
    for path, content in generated(root).items():
        if not path.exists() or path.read_text() != content:
            raise ValueError("Stale generated file: " + str(path.relative_to(root)))
