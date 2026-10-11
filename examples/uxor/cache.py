#!/usr/bin/env python3
"""Isolated dependency snapshots with authenticated worktree/CI bundle imports."""
import argparse
from collections import deque
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager, nullcontext
import zipfile
import zlib

ARCHIVE_ERRORS = (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, zlib.error, RuntimeError)


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


@contextmanager
def authenticated_bundle(path, expected_sha256):
    # Verify the exact open bytes we will parse, not a path that another process
    # can replace between hashing and extraction. The digest comes from the
    # caller's trusted producer/CI channel, never from inside the bundle.
    with tempfile.TemporaryFile() as verified:
        value = hashlib.sha256()
        with path.open("rb") as incoming:
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                value.update(block)
                verified.write(block)
        if not hmac.compare_digest(value.hexdigest(), expected_sha256):
            raise ValueError("Dependency bundle SHA-256 differs from the trusted expected digest")
        verified.seek(0)
        with zipfile.ZipFile(verified) as bundle:
            yield bundle


def identity(project, kind, image="", runtime=None):
    runtime = runtime or subprocess.check_output(["php", "-r",
        '$e=get_loaded_extensions(); sort($e); echo json_encode([PHP_VERSION,PHP_OS_FAMILY,PHP_INT_SIZE,$e]);'], text=True)
    files = ["composer.json", "composer.lock"]
    if kind == "importmap":
        files.append(os.environ.get("IMPORTMAP_FILE", "importmap.php"))
    facts = {"schema": 1, "kind": kind, "runtime": runtime, "image": image,
             "inputs": {name: sha(project / name) for name in files}}
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


def tree_manifest(folder):
    result = {}
    for directory, dirs, files in os.walk(folder):
        # Directory links belong in the manifest, but are never traversed.
        links = [name for name in dirs if (Path(directory) / name).is_symlink()]
        dirs[:] = sorted(name for name in dirs if name not in links)
        for name in sorted(files + links):
            path = Path(directory) / name
            relative = path.relative_to(folder).as_posix()
            if path.is_symlink():
                result[relative] = {"link": os.readlink(path)}
            elif path.is_file():
                result[relative] = {"sha256": sha(path), "mode": path.stat().st_mode & 0o777}
    return result


def archive_manifest(source, key):
    manifest = json.loads(source.read("manifest.json"))
    if not isinstance(manifest, dict) or manifest.get("schema") != 1 or manifest.get("identity") != key:
        raise ValueError("Dependency cache identity differs from project/runtime inputs")
    entries = manifest.get("files")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Dependency snapshot has no file manifest")
    expected = {"manifest.json"}
    links = {name for name, entry in entries.items() if isinstance(entry, dict) and "link" in entry}
    for name, entry in entries.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise ValueError("Invalid dependency archive manifest")
        parts = PurePosixPath(name).parts
        if not parts or name.startswith("/") or ".." in parts or "\\" in name or str(PurePosixPath(name)) != name:
            raise ValueError("Unsafe dependency archive path")
        if any(PurePosixPath(name).is_relative_to(PurePosixPath(link)) and name != link for link in links):
            raise ValueError("Dependency archive contains files below a symlink")
        if "link" in entry:
            if set(entry) != {"link"} or not isinstance(entry["link"], str) or not entry["link"] or "\0" in entry["link"]:
                raise ValueError("Invalid dependency symlink manifest")
        else:
            if set(entry) != {"sha256", "mode"} or not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) or type(entry.get("mode")) is not int or not 0 <= entry["mode"] <= 0o777:
                raise ValueError("Invalid dependency file manifest")
            expected.add("files/" + name)
    members = source.namelist()
    if len(members) != len(set(members)) or set(members) != expected:
        raise ValueError("Dependency archive members differ from the manifest")
    return manifest


def validate_archive(archive, key, expected=None):
    """Check member bytes as well as the manifest before trusting a snapshot."""
    with zipfile.ZipFile(archive) as source:
        manifest = archive_manifest(source, key)
        for name, entry in manifest["files"].items():
            if "link" not in entry:
                value = hashlib.sha256()
                with source.open("files/" + name) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(block)
                if not hmac.compare_digest(value.hexdigest(), entry["sha256"]):
                    raise ValueError("Dependency snapshot checksum mismatch")
        return expected is None or manifest == expected


def write_archive(folder, archive, key):
    manifest = tree_manifest(folder)
    if not manifest:
        return False
    expected = {"schema": 1, "identity": key, "files": manifest}
    if archive.is_file():
        try:
            if validate_archive(archive, key, expected):
                return True
        except ARCHIVE_ERRORS:
            # Keep evidence of corruption without making it reusable. A fresh
            # verified local tree repairs the key atomically below.
            archive.replace(archive.with_name(archive.name + ".corrupt-" + uuid.uuid4().hex))
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as output:
            output.writestr("manifest.json", json.dumps(expected))
            for name, entry in manifest.items():
                if "link" not in entry:
                    output.write(folder / name, "files/" + name)
        if not validate_archive(temporary, key, expected):
            raise ValueError("Dependency source changed while storing its snapshot")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def validate_link_topology(folder, entries, workspace):
    """Resolve final symlink paths in OS order, including links from this archive.

    normpath before symlink expansion changes the meaning of alias/../file.
    The absent final tree cannot be checked by Path.resolve alone, and staged
    links live at a different depth, so resolve the final virtual tree here.
    """
    root, boundary = folder.resolve(), workspace.resolve()
    if not root.is_relative_to(boundary):
        raise ValueError("Dependency destination leaves the mounted workspace")
    virtual = {root / name: entry["link"] for name, entry in entries.items() if "link" in entry}
    for link in virtual:
        if Path(virtual[link]).is_absolute():
            raise ValueError("Dependency symlink leaves the mounted workspace")
        pending = deque(link.parts[1:])
        resolved = Path(link.anchor)
        expansions = 0
        while pending:
            part = pending.popleft()
            if part == "..":
                resolved = resolved.parent
                continue
            candidate = resolved / part
            target = virtual.get(candidate)
            if target is None and candidate.is_symlink():
                target = os.readlink(candidate)
            if target is None:
                resolved = candidate
                continue
            expansions += 1
            if expansions > 40:
                raise ValueError("Dependency symlink topology contains a loop or too many link expansions")
            target = Path(target)
            if target.is_absolute():
                resolved = Path(target.anchor)
                parts = target.parts[1:]
            else:
                parts = target.parts
            pending.extendleft(reversed(parts))
        if not resolved.is_relative_to(boundary):
            raise ValueError("Dependency symlink leaves the mounted workspace")


def restore_archive(archive, folder, key, workspace, *, final_folder=None):
    if folder.exists() or folder.is_symlink():
        return False
    with zipfile.ZipFile(archive) as source:
        entries = archive_manifest(source, key)["files"]
        validate_link_topology(final_folder or folder, entries, workspace)
        folder.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder.parent, prefix=".xorder-restore-") as directory:
            staged = Path(directory) / "payload"
            staged.mkdir()
            for name, entry in entries.items():
                path = staged / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if "link" in entry:
                    path.symlink_to(entry["link"])
                else:
                    with source.open("files/" + name) as incoming, path.open("wb") as output:
                        shutil.copyfileobj(incoming, output)
                    if sha(path) != entry["sha256"]:
                        raise ValueError("Dependency snapshot checksum mismatch")
                    path.chmod(entry["mode"] & 0o777)
            validate_link_topology(final_folder or folder, entries, workspace)
            staged.rename(folder)
    return True


SNAPSHOT_NAME = re.compile(r"(?:vendor|importmap)-[0-9a-f]{64}\.zip(?P<corrupt>\.corrupt-[0-9a-f]{32})?$")


def record_usage(directory, selected, action):
    path = directory / "usage.json"
    if path.is_symlink():
        raise ValueError("Cache usage receipt must not be redirected by a symlink")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        value = {}
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("snapshots"), dict):
        value = {"schema": 1, "snapshots": {}}
    for archive in selected:
        value["snapshots"][archive.name] = {"last_used": time.time(), "action": action}
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as output:
        temporary = Path(output.name)
        json.dump(value, output, sort_keys=True)
        output.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def snapshot_usage(directory, current):
    snapshots, ignored = [], []
    try:
        usage = json.loads((directory / "usage.json").read_text()).get("snapshots", {})
    except (OSError, ValueError, AttributeError):
        usage = {}
    for path in sorted(directory.iterdir()):
        match = SNAPSHOT_NAME.fullmatch(path.name)
        if match and path.is_file() and not path.is_symlink() and path.stat().st_uid == os.getuid():
            size = path.stat().st_size
            snapshots.append({"name": path.name, "bytes": size,
                              "state": "quarantined" if match["corrupt"] else "current" if path.name in current else "obsolete",
                              "last_used": usage.get(path.name, {}).get("last_used") if isinstance(usage, dict) and isinstance(usage.get(path.name, {}), dict) else None})
        elif path.name not in {"snapshots.lock", "usage.json", "workspace.json"}:
            ignored.append(path.name)
    return {"schema": 1, "cache": str(directory), "snapshots": snapshots, "preserved": ignored,
            "snapshot_bytes": sum(item["bytes"] for item in snapshots),
            "reclaimable_bytes": sum(item["bytes"] for item in snapshots if item["state"] != "current")}


def register_workspace_cache(directory, workspace, repository, downloads=False):
    """Host registration enables conservative orphan discovery; legacy caches stay untouched."""
    value = {"schema": 1, "workspace": str(workspace), "repository": str(repository),
             "owned_directories": ["composer-downloads"] if downloads else []}
    path = directory / "workspace.json"
    if path.is_symlink():
        raise ValueError("Dependency cache workspace registration cannot be redirected")
    if path.exists():
        previous = json.loads(path.read_text())
        if not isinstance(previous, dict) or {key: previous.get(key) for key in ("schema", "workspace", "repository")} != {key: value[key] for key in ("schema", "workspace", "repository")} or previous.get("owned_directories") not in ([], ["composer-downloads"]):
            raise ValueError("Dependency cache workspace registration differs from this checkout")
        if previous["owned_directories"]:
            value["owned_directories"] = previous["owned_directories"]
        if previous == value:
            return
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as output:
        temporary = Path(output.name)
        json.dump(value, output, sort_keys=True)
        output.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def directory_bytes(directory):
    total = 0
    for base, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(base) / name).is_symlink()]
        total += sum((Path(base) / name).lstat().st_size for name in files)
    return total


def cache_containers(env):
    ids = subprocess.run(["docker", "ps", "-aq"], env=env, text=True, capture_output=True, check=True, timeout=15).stdout.split()
    return json.loads(subprocess.run(["docker", "inspect", *ids], env=env, text=True, capture_output=True, check=True, timeout=15).stdout) if ids else []


def cache_references(directory, workspace, containers):
    used = []
    for container in containers:
        labels = container.get("Config", {}).get("Labels") or {}
        binds = [Path(mount["Source"]).resolve() for mount in container.get("Mounts", [])
                 if mount.get("Type") == "bind" and mount.get("Source")]
        if labels.get("dev.xorder.workspace") == str(workspace) or any(
                source.is_relative_to(target) or target.is_relative_to(source)
                for source in binds for target in (directory, workspace)):
            used.append(container.get("Name") or container.get("Id", "unknown container"))
    return used


def orphan_cache_usage(root, env, apply=False):
    """Inspect/remove only registered caches of absent workspaces, never active mounts."""
    root = Path(root).resolve()
    report = {"schema": 1, "cache_root": str(root), "apply": apply,
              "workspaces": [], "removed": [], "blocked": [], "cache_bytes": 0, "reclaimable_bytes": 0}
    if not root.is_dir():
        print(json.dumps(report, sort_keys=True))
        return 0
    try:
        containers = cache_containers(env)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report["blocked"].append("Cannot establish container references: " + str(error))
        print(json.dumps(report, sort_keys=True))
        return 1
    for scope in sorted(root.iterdir()):
        if scope.is_symlink() or not scope.is_dir() or not re.fullmatch(r"[0-9a-f]{64}", scope.name):
            continue
        for directory in sorted(scope.iterdir()):
            marker = directory / "workspace.json"
            if directory.is_symlink() or not directory.is_dir() or not marker.is_file() or marker.is_symlink() or marker.stat().st_uid != os.getuid():
                continue
            try:
                registered = json.loads(marker.read_text())
                workspace = Path(registered["workspace"])
                repository = Path(registered["repository"])
                owned = registered["owned_directories"]
                if registered.get("schema") != 1 or not workspace.is_absolute() or not repository.is_absolute() or owned not in ([], ["composer-downloads"]):
                    raise ValueError("Invalid workspace cache registration")
                if scope.name != hashlib.sha256(str(repository).encode()).hexdigest() or directory.name != hashlib.sha256(str(workspace).encode()).hexdigest() or directory.resolve() != directory:
                    raise ValueError("Workspace cache registration differs from its path")
                current = snapshot_usage(directory, set())
                unknown = set(current["preserved"]) - set(owned)
                if any((directory / name).is_symlink() for name in owned) or unknown:
                    raise ValueError("Cache contains unowned entries; preserved")
                size = directory_bytes(directory)
                references = cache_references(directory, workspace, containers)
                orphan = not workspace.exists() and not workspace.is_symlink()
                item = {"cache": str(directory), "workspace": str(workspace), "bytes": size,
                        "orphaned": orphan, "referenced_by": references}
                report["workspaces"].append(item)
                report["cache_bytes"] += size
                if not orphan or references:
                    continue
                # A cache transaction still holds this lock if its one-shot
                # container disappeared from Docker's listing unexpectedly.
                lock_path = directory / "snapshots.lock"
                if any((directory / name).is_symlink() for name in ("snapshots.lock", "usage.json")):
                    raise ValueError("Cache metadata is redirected; preserved")
                with lock_path.open("a") if apply else lock_path.open("r") if lock_path.exists() else nullcontext() as lock:
                    try:
                        if lock is not None:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        report["blocked"].append(str(directory) + ": active snapshot transaction")
                        continue
                    report["reclaimable_bytes"] += size
                    if apply:
                        if marker.is_symlink() or json.loads(marker.read_text()) != registered or workspace.exists() or workspace.is_symlink():
                            report["blocked"].append(str(directory) + ": workspace or registration changed")
                            continue
                        if cache_references(directory, workspace, cache_containers(env)):
                            report["blocked"].append(str(directory) + ": container now references this cache")
                            continue
                        # Known regular metadata/snapshots and the explicitly
                        # registered download directory only. rmtree does not
                        # follow links inside the owned downloads directory.
                        fresh = snapshot_usage(directory, set())
                        if set(fresh["preserved"]) - set(owned) or any((directory / name).is_symlink() for name in owned):
                            report["blocked"].append(str(directory) + ": unowned entries appeared")
                            continue
                        for entry in directory.iterdir():
                            if entry.name in owned and entry.is_dir() and not entry.is_symlink():
                                shutil.rmtree(entry)
                            elif (SNAPSHOT_NAME.fullmatch(entry.name) or entry.name in {"snapshots.lock", "usage.json", "workspace.json"}) and entry.is_file() and not entry.is_symlink() and entry.stat().st_uid == os.getuid():
                                entry.unlink()
                        if not any(directory.iterdir()):
                            directory.rmdir()
                            report["removed"].append(str(directory))
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                report["blocked"].append(str(directory) + ": " + str(error))
    print(json.dumps(report, sort_keys=True))
    return 1 if report["blocked"] and apply else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["restore", "store", "export", "import", "usage", "prune"])
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path, default=Path(os.environ.get("XORDER_DEPENDENCY_CACHE", "/run/xorder-cache")))
    parser.add_argument("--image", default=os.environ.get("XORDER_CACHE_IMAGE", ""))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--sha256", help="Trusted expected SHA-256 of an imported bundle")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply explicitly selected obsolete snapshot pruning")
    mode.add_argument("--dry-run", action="store_true", help="List prune candidates without deleting (default)")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if (args.apply or args.dry_run) and args.action != "prune":
        parser.error("--apply and --dry-run are only valid with prune")
    if not args.cache.is_dir():
        if args.action in {"restore", "store"}:
            return 0
        parser.error("Cache directory is unavailable")
    if args.action == "export" and not args.output or args.action == "import" and not args.input:
        parser.error("export needs --output; import needs --input")
    if args.action == "import" and not re.fullmatch(r"[0-9a-fA-F]{64}", args.sha256 or ""):
        parser.error("import needs --sha256 from a trusted producer or CI artifact channel")
    vendor = os.environ.get("IMPORTMAP_VENDOR_DIR", "assets/vendor")
    folders = {"vendor": project / "vendor", "importmap": project / vendor}
    if not (project / os.environ.get("IMPORTMAP_FILE", "importmap.php")).is_file():
        del folders["importmap"]
    for folder in folders.values():
        if not folder.resolve().is_relative_to(project):
            raise ValueError("Dependency directory must be inside the project")
    with (args.cache / "snapshots.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action in {"usage", "prune"}:
            current = {kind + "-" + identity(project, kind, args.image) + ".zip" for kind in folders}
            report = snapshot_usage(args.cache, current)
            report["apply"] = args.apply
            report["removed"] = []
            if args.action == "prune" and args.apply:
                for item in report["snapshots"]:
                    if item["state"] in {"obsolete", "quarantined"}:
                        path = args.cache / item["name"]
                        # Only a direct, owned regular file observed in this plan.
                        if path.is_file() and not path.is_symlink() and path.stat().st_uid == os.getuid():
                            path.unlink()
                            report["removed"].append(item["name"])
            print(json.dumps(report, sort_keys=True))
            return 0
        if args.action == "import":
            with authenticated_bundle(args.input, args.sha256.lower()) as bundle, \
                    tempfile.TemporaryDirectory(dir=args.cache, prefix=".xorder-import-") as staging:
                selected_imports = []
                for kind in folders:
                    key = identity(project, kind, args.image)
                    name = kind + "-" + key + ".zip"
                    if bundle.namelist().count(name) != 1:
                        raise ValueError("Authenticated bundle lacks the exact " + kind + " snapshot for these inputs")
                    temporary = Path(staging) / name
                    with bundle.open(name) as incoming, temporary.open("wb") as output:
                        shutil.copyfileobj(incoming, output)
                    # Validate every selected archive before promoting any key.
                    with tempfile.TemporaryDirectory(dir=project) as directory:
                        restore_archive(temporary, Path(directory) / kind, key, project.parent,
                                        final_folder=folders[kind])
                    selected_imports.append((temporary, args.cache / name))
                for temporary, destination in selected_imports:
                    temporary.replace(destination)
        selected = []
        for kind, folder in folders.items():
            key = identity(project, kind, args.image)
            archive = args.cache / (kind + "-" + key + ".zip")
            if args.action in {"store", "export"} and folder.is_dir():
                write_archive(folder, archive, key)
            if args.action in {"restore", "import"} and archive.is_file():
                try:
                    if restore_archive(archive, folder, key, project.parent):
                        print(f"Restored verified {kind} snapshot")
                except ARCHIVE_ERRORS as error:
                    print(f"Ignoring unusable {kind} snapshot: {error}", file=__import__('sys').stderr)
            if archive.is_file():
                selected.append(archive)
        record_usage(args.cache, selected, args.action)
        if args.action == "export":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(args.output, "w", zipfile.ZIP_STORED) as bundle:
                for archive in selected:
                    bundle.write(archive, archive.name)
            print("Exported dependency snapshots to " + str(args.output))
            print("SHA-256: " + sha(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
