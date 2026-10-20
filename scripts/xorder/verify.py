"""Stage exact HTTP resources and exercise the retrieved payload."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .transport import download, unpack

ROOT = Path(__file__).resolve().parents[2]


def prepare(definition, destination, root=ROOT):
    """Prepare reproducible payload bytes without claiming public availability."""
    from .model import relative_path
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    details = definition["details"]
    if definition["kind"] == "binary":
        filename = details["filename"]
        artifact = destination / filename
        facts = download(details["source_url"], artifact, details["sha256"])
        return artifact, {"filename": filename, "format": "file", **facts}
    payload = Path(root) / "artifacts" / definition["id"] / "payload"
    filename = definition["name"] + "-" + definition["revision"] + ".tar"
    artifact = destination / filename
    with tarfile.open(artifact, "w", format=tarfile.PAX_FORMAT) as archive:
        for source_name in sorted({item["source"] for item in details["files"]}):
            relative_path(source_name)
            source = payload / source_name
            if not source.resolve().is_relative_to(payload.resolve()) or source.is_symlink() or not source.is_file():
                raise ValueError(f"Bundle source is not a contained regular file: {source_name}")
            # Ancestor symlinks can still enter the input tree through another path.
            if any(parent.is_symlink() for parent in source.parents if parent.is_relative_to(payload)):
                raise ValueError(f"Bundle source has a symlink ancestor: {source_name}")
            info = tarfile.TarInfo(source_name)
            info.size = source.stat().st_size
            info.mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
            with source.open("rb") as data:
                archive.addfile(info, data)
    return artifact, {"filename": filename, "format": "tar", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "size_bytes": artifact.stat().st_size}


def exercise(definition, artifact, format, root=ROOT):
    with tempfile.TemporaryDirectory(prefix="xorder-verify-") as temporary:
        staged = unpack(artifact, format, Path(temporary) / "payload", filename=Path(artifact).name if format == "file" else None)
        command = definition["verification"]["command"]
        subprocess.run([*command, str(staged)], cwd=root, check=True)
    return [*command, "$ARTIFACT_ROOT"]


def affected(changed, definitions):
    selected = set()
    for path in changed:
        if path.startswith(("scripts/xorder/", "schemas/resource", "schemas/artifact-release", "schemas/profile", ".github/workflows/validate.yml", ".github/workflows/publish.yml")):
            if path.startswith(("scripts/xorder/verify-devenv", "scripts/xorder/bootstrap-devenv")):
                selected.update(key for key, d in definitions.items() if d["kind"] == "environment")
            elif path == "scripts/xorder/verify-composer.sh":
                selected.update(key for key, d in definitions.items() if d["kind"] == "binary")
            elif path == "scripts/xorder/verify-bundles.py":
                selected.update(key for key, d in definitions.items() if d["kind"] in ("configuration", "context"))
            else:
                selected.update(definitions)
        elif path.startswith(("tests/fixtures/devenv/", "tests/fixtures/artifacts/environment/", "examples/devenv/")):
            selected.update(key for key, d in definitions.items() if d["kind"] == "environment")
        elif path.startswith("tests/fixtures/php/"):
            selected.update(key for key, d in definitions.items() if d["kind"] in ("binary", "environment"))
        elif path.startswith("tests/fixtures/artifacts/application/"):
            selected.update(key for key, d in definitions.items() if d["kind"] in ("configuration", "context"))
        elif path.startswith(("tests/fixtures/artifacts/", "examples/resources/")):
            selected.update(definitions)
        else:
            selected.update(key for key in definitions if path.startswith("artifacts/" + key + "/"))
    return sorted(selected)


def main():
    from .model import definitions
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--base")
    matrix.add_argument("--head", default="HEAD")
    matrix.add_argument("--all", action="store_true")
    preparation = sub.add_parser("prepare")
    preparation.add_argument("id")
    preparation.add_argument("destination")
    validation = sub.add_parser("verify")
    validation.add_argument("id")
    validation.add_argument("--output", default=str(ROOT / "out" / "resources"))
    args = parser.parse_args()
    defs = definitions()
    if args.command == "matrix":
        changed = subprocess.check_output(["git", "diff", "--name-only", args.base, args.head], cwd=ROOT, text=True).splitlines() if args.base and not args.all else None
        ids = affected(changed, defs) if changed is not None else sorted(defs)
        print(json.dumps({"resource": [key for key in ids if defs[key]["kind"] != "environment"], "environment": [key for key in ids if defs[key]["kind"] == "environment"]}))
    else:
        definition = defs[args.id]
        destination = Path(args.destination) if args.command == "prepare" else Path(args.output) / args.id
        artifact, facts = prepare(definition, destination)
        if args.command == "verify":
            command = exercise(definition, artifact, facts["format"])
            (destination / "verification.json").write_text(json.dumps({"id": args.id, **facts, "commands": [command]}, indent=2) + "\n")
        print(str(artifact))


if __name__ == "__main__":
    main()
