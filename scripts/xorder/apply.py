"""Materialize a resolved selection while preserving target file ownership."""
import contextlib
import copy
import hashlib
import json
import os
import platform
import re
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid

from .transport import download, unpack


class Conflict(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".xorder-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Expected a relative POSIX file path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"Unsafe relative path: {value}")
    return path


def target_path(root, name):
    path = root.joinpath(*relative(name).parts)
    current = root
    for part in relative(name).parts:
        current = current / part
        if current.is_symlink():
            raise Conflict(f"Destination crosses a symbolic link: {name}")
        if current != path and current.exists() and not current.is_dir():
            raise Conflict(f"Destination parent is not a directory: {name}")
    if path.exists() and not path.is_file():
        raise Conflict(f"Destination is not a regular file: {name}")
    return path


def locations(root, state_dir=None, cache_dir=None):
    root = Path(root).expanduser().resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()
    state_base = Path(state_dir) if state_dir else Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "xorder"
    cache = Path(cache_dir) if cache_dir else Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "xorder/sha256"
    return root, state_base.expanduser().resolve() / key, cache.expanduser().resolve()


@contextlib.contextmanager
def target_lock(state):
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("The application helper currently requires a POSIX host") from error
    state.mkdir(parents=True, exist_ok=True)
    with (state / "target.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Conflict("Another application is changing this target") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def receipt(state, root):
    path = state / "receipt.json"
    value = json.loads(path.read_text()) if path.exists() else {"schema_version": 2, "target_root": str(root), "files": {}, "resources": {}}
    if value["target_root"] != str(root):
        raise ValueError("Receipt belongs to a different target root")
    from .model import validate_schema
    validate_schema(value, "installation-receipt.schema.json")
    return value


def mappings(resource):
    if resource["kind"] == "image":
        return []
    if resource["kind"] == "binary":
        return [{"source": resource["delivery"]["filename"], "destination": resource["details"]["executable"]}]
    return resource["details"]["files"]


def validate_lock(lock):
    if lock.get("schema_version") != 2 or not isinstance(lock.get("resources"), list):
        raise ValueError("Expected a schema-2 resolution lock")
    ids, destinations = set(), set()
    for item in lock["resources"]:
        if item["id"] in ids:
            raise ValueError(f"Duplicate resolved resource: {item['id']}")
        ids.add(item["id"])
        if item["kind"] != "image":
            delivery = item["delivery"]
            if not re.fullmatch(r"[a-f0-9]{64}", delivery["sha256"]):
                raise ValueError("Invalid payload checksum")
            if item["identity"] != "sha256:" + delivery["sha256"]:
                raise ValueError("Lock identity differs from its payload checksum")
        for mapping in mappings(item):
            relative(mapping["source"])
            relative(mapping["destination"])
            if mapping["destination"] in destinations:
                raise ValueError(f"Selected resources share a destination: {mapping['destination']}")
            destinations.add(mapping["destination"])
    return lock


def accepted_lock(lock, accepted_catalog=None):
    from .model import catalog
    from .resolve import validate_lock as validate_accepted
    validate_lock(lock)
    return validate_accepted(lock, accepted_catalog if accepted_catalog is not None else catalog())


def prerequisites(lock):
    machine = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
    actual = platform.system().lower() + "/" + machine
    failures = []
    expected = lock["target"].get("platform")
    if expected and expected != actual:
        failures.append({"code": "target_changed", "expected": expected, "actual": actual})
    elif not expected and any("any" not in item["targets"] for item in lock["resources"]):
        failures.append({"code": "target_fact_missing", "fact": "platform"})
    for item in lock["resources"]:
        missing = [command for command in item["prerequisites"]["commands"] if shutil.which(command) is None]
        if missing:
            failures.append({"code": "missing_prerequisite", "resource": item["id"], "commands": missing})
    return failures


def _plan(lock, root, previous, state):
    validate_lock(lock)
    actions = []
    for item in lock["resources"]:
        if item["kind"] == "image":
            actions.append({"resource": item["id"], "action": "external", "identity": item["identity"], "documentation": item["documentation"]})
            continue
        for mapping in mappings(item):
            name = mapping["destination"]
            try:
                path = target_path(root, name)
                if path.is_relative_to(state):
                    raise Conflict("Destination overlaps application state")
                owned = previous["files"].get(name)
                observed = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777} if path.exists() else None
                if observed and (not owned or observed != {"sha256": owned["sha256"], "mode": owned["mode"]}):
                    raise Conflict("Destination is unowned or has local edits")
                if owned and owned["resource"] != item["id"]:
                    raise Conflict("Destination belongs to another resource; remove it explicitly first")
                old_resource = previous["resources"].get(item["id"], {})
                same = observed and owned and old_resource.get("identity") == item["identity"]
                action = "unchanged" if same else ("update" if owned else "install")
                actions.append({"resource": item["id"], "destination": name, "source": mapping["source"], "action": action, "observed": observed})
            except Conflict as error:
                actions.append({"resource": item["id"], "destination": name, "action": "conflict", "reason": str(error)})
    return {"status": "conflict" if any(a["action"] == "conflict" for a in actions) else "ready", "target_root": str(root), "actions": actions}


def plan(lock, root, state_dir=None, accepted_catalog=None):
    accepted_lock(lock, accepted_catalog)
    missing = prerequisites(lock)
    if missing:
        return {"status": "prerequisite_missing", "gaps": missing}
    root, state, _ = locations(root, state_dir)
    if (state / "pending.json").exists():
        return {"status": "recovery_required", "target_root": str(root), "reason": "Run recover before another application"}
    return _plan(lock, root, receipt(state, root), state)


def _blob(path, cache):
    checksum = digest(path)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / checksum
    if not destination.exists() or digest(destination) != checksum:
        fd, temporary = tempfile.mkstemp(dir=cache, prefix=".blob-")
        os.close(fd)
        try:
            shutil.copyfile(path, temporary)
            if digest(temporary) != checksum:
                raise Conflict("File changed while being staged")
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return checksum


def _replace(root, name, cache, metadata):
    path = target_path(root, name)
    if metadata is None:
        path.unlink(missing_ok=True)
        return
    if not re.fullmatch(r"[a-f0-9]{64}", metadata["sha256"]):
        raise ValueError("Invalid retained content hash")
    source = cache / metadata["sha256"]
    if not source.is_file() or digest(source) != metadata["sha256"]:
        raise ValueError(f"Retained bytes are missing or corrupt: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".xorder-")
    os.close(fd)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, metadata["mode"])
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _recover(root, state, cache):
    journal_path = state / "pending.json"
    if not journal_path.exists():
        return {"status": "unchanged", "actions": []}
    journal = json.loads(journal_path.read_text())
    restored, conflicts = [], []
    for action in reversed(journal["actions"]):
        name, before, after = action["destination"], action["before"], action["after"]
        try:
            path = target_path(root, name)
            present = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777} if path.exists() else None
            if present == before:
                continue
            if present != after:
                raise Conflict("File was changed outside this application; recovery preserved it")
            _replace(root, name, cache, before)
            restored.append(name)
        except (Conflict, ValueError, OSError) as error:
            conflicts.append({"destination": name, "reason": str(error)})
    if conflicts:
        return {"status": "recovery_conflict", "restored": restored, "conflicts": conflicts}
    atomic_json(state / "receipt.json", journal["before_receipt"])
    journal_path.unlink()
    return {"status": "recovered", "restored": restored}


def recover(root, state_dir=None, cache_dir=None):
    root, state, cache = locations(root, state_dir, cache_dir)
    with target_lock(state):
        return _recover(root, state, cache)


def _commit(root, state, cache, before, after, actions):
    if not actions and before == after:
        return {"status": "unchanged", "actions": []}
    journal = {"schema_version": 2, "target_root": str(root), "before_receipt": before, "after_receipt": after, "actions": actions}
    atomic_json(state / "pending.json", journal)
    completed = []
    try:
        for action in actions:
            path = target_path(root, action["destination"])
            current = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777} if path.exists() else None
            if current != action["before"]:
                raise Conflict(f"File changed after planning: {action['destination']}")
            _replace(root, action["destination"], cache, action["after"])
            completed.append(action["destination"])
        atomic_json(state / "receipt.json", after)
        history = state / "history"
        history.mkdir(exist_ok=True)
        os.replace(state / "pending.json", history / (uuid.uuid4().hex + ".json"))
        return {"status": "applied", "completed": completed}
    except Exception as error:
        recovered = _recover(root, state, cache)
        return {"status": "failed", "reason": str(error), "completed_before_recovery": completed, "recovery": recovered}


def apply(lock, root, state_dir=None, cache_dir=None, accepted_catalog=None):
    root, state, cache = locations(root, state_dir, cache_dir)
    accepted_lock(lock, accepted_catalog)
    missing = prerequisites(lock)
    if missing:
        return {"status": "prerequisite_missing", "gaps": missing}
    with target_lock(state):
        if (state / "pending.json").exists():
            return {"status": "recovery_required", "reason": "Run recover before another application"}
        before = receipt(state, root)
        proposal = _plan(lock, root, before, state)
        if proposal["status"] != "ready":
            return proposal
        resources = {r["id"]: r for r in lock["resources"]}
        after = copy.deepcopy(before)
        actions = []
        with tempfile.TemporaryDirectory(prefix="xorder-stage-") as temporary:
            staged = {}
            for action in proposal["actions"]:
                if action["action"] in ("unchanged", "external"):
                    continue
                item = resources[action["resource"]]
                if item["id"] not in staged:
                    delivery = item["delivery"]
                    cache.mkdir(parents=True, exist_ok=True)
                    payload = cache / delivery["sha256"]
                    if not payload.is_file() or digest(payload) != delivery["sha256"]:
                        download(delivery["url"], payload, delivery["sha256"])
                    destination = Path(temporary) / str(len(staged))
                    unpack(payload, delivery["format"], destination, filename=delivery["filename"] if delivery["format"] == "file" else None)
                    staged[item["id"]] = destination
                source = staged[item["id"]].joinpath(*relative(action["source"]).parts)
                if not source.is_file() or source.is_symlink():
                    raise ValueError(f"Declared payload file is absent: {action['source']}")
                target = target_path(root, action["destination"])
                observed = {"sha256": digest(target), "mode": target.stat().st_mode & 0o777} if target.exists() else None
                if observed != action["observed"]:
                    raise Conflict(f"Destination changed during staging: {action['destination']}")
                old = None
                if target.exists():
                    old = {"sha256": _blob(target, cache), "mode": target.stat().st_mode & 0o777}
                if old != action["observed"]:
                    raise Conflict(f"Destination changed while backing up: {action['destination']}")
                mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
                new = {"sha256": _blob(source, cache), "mode": mode}
                after["files"][action["destination"]] = {**new, "resource": item["id"]}
                if old != new:
                    actions.append({"destination": action["destination"], "before": old, "after": new})
            for item in lock["resources"]:
                if item["kind"] != "image":
                    after["resources"][item["id"]] = {"identity": item["identity"], "version": item["version"], "kind": item["kind"]}
            after["resolution"] = copy.deepcopy(lock)
            result = _commit(root, state, cache, before, after, actions)
            result["external"] = [a for a in proposal["actions"] if a["action"] == "external"]
            return result


def verify(root, state_dir=None):
    root, state, _ = locations(root, state_dir)
    if (state / "pending.json").exists():
        return {"status": "recovery_required", "reason": "Run recover before checking managed state"}
    value = receipt(state, root)
    failures = []
    for name, item in value["files"].items():
        try:
            path = target_path(root, name)
            if not path.exists() or digest(path) != item["sha256"] or path.stat().st_mode & 0o777 != item["mode"]:
                raise Conflict("Managed file is missing or changed")
        except Conflict as error:
            failures.append({"destination": name, "reason": str(error)})
    return {"status": "passed" if not failures else "changed", "checked_files": len(value["files"]), "failures": failures}


def remove(root, resource_ids, state_dir=None, cache_dir=None):
    root, state, cache = locations(root, state_dir, cache_dir)
    with target_lock(state):
        if (state / "pending.json").exists():
            return {"status": "recovery_required"}
        before = receipt(state, root)
        after = copy.deepcopy(before)
        actions, conflicts = [], []
        for name, item in before["files"].items():
            if item["resource"] not in resource_ids:
                continue
            try:
                path = target_path(root, name)
                if path.exists() and (digest(path) != item["sha256"] or path.stat().st_mode & 0o777 != item["mode"]):
                    raise Conflict("Locally edited file preserved")
                if path.exists():
                    old = {"sha256": _blob(path, cache), "mode": path.stat().st_mode & 0o777}
                    if old != {"sha256": item["sha256"], "mode": item["mode"]}:
                        raise Conflict("File changed while backing up; removal preserved it")
                    actions.append({"destination": name, "before": old, "after": None})
                del after["files"][name]
            except Conflict as error:
                conflicts.append({"destination": name, "reason": str(error)})
        if conflicts:
            return {"status": "conflict", "conflicts": conflicts}
        for identity in resource_ids:
            after["resources"].pop(identity, None)
        return _commit(root, state, cache, before, after, actions)


def rollback(root, state_dir=None, cache_dir=None):
    root, state, cache = locations(root, state_dir, cache_dir)
    with target_lock(state):
        if (state / "pending.json").exists():
            return {"status": "recovery_required"}
        history = sorted((state / "history").glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        if not history:
            return {"status": "unchanged", "reason": "No retained application to roll back"}
        last = history[-1]
        journal = json.loads(last.read_text())
        atomic_json(state / "pending.json", journal)
        result = _recover(root, state, cache)
        if result["status"] == "recovered":
            last.unlink()
        return result
