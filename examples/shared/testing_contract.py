"""Project-owned sync checks and reversible named source faults."""
from contextlib import contextmanager
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile

from runtime import state_root


def _command(value, label):
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item or "\0" in item for item in value):
        raise ValueError(label + " must be a nonempty argument array")
    return value


def _assertion(value, label, require_content=False):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    _command(value.get("command"), label + ".command")
    for key in ("contains", "absent"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            raise ValueError(label + "." + key + " must be a nonempty literal")
    if require_content and "contains" not in value:
        raise ValueError(label + " must assert served content with a contains literal")
    return value


def _path(workspace, relative):
    if not isinstance(relative, str) or not relative or "\0" in relative:
        raise ValueError("Source paths must be nonempty relative strings")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("Source paths must stay inside the workspace")
    target = workspace / path
    if target.resolve() != target or not target.resolve().is_relative_to(workspace):
        raise ValueError("Source paths must not follow symlinks")
    return target


def load_contract(workspace, profile):
    """Read optional .xorder/testing.json; the selected profile owns defaults."""
    workspace = Path(workspace).resolve(strict=True)
    defaults = json.loads((Path(profile) / "profile.json").read_text())
    value = {"schema_version": 1, "sync": {"command": defaults["sync"], "check": defaults.get("sync_check")}, "plants": {}}
    configuration = _path(workspace, ".xorder/testing.json")
    if configuration.exists():
        override = json.loads(configuration.read_text())
        if not isinstance(override, dict) or override.get("schema_version") != 1:
            raise ValueError(".xorder/testing.json must declare schema_version 1")
        value.update(override)
    sync = value.get("sync")
    if not isinstance(sync, dict):
        raise ValueError("sync must be an object with command and check")
    _command(sync.get("command"), "sync.command")
    if sync.get("check") is not None:
        _assertion(sync["check"], "sync.check")
    if not isinstance(value.get("plants"), dict):
        raise ValueError("plants must be an object keyed by fault name")
    for name, plant in value["plants"].items():
        if not isinstance(name, str) or not name or name.startswith("-") or not isinstance(plant, dict):
            raise ValueError("Each plant must have a name and object definition")
        edits = plant.get("edits")
        if not isinstance(edits, list) or not edits:
            raise ValueError("Plant " + name + " needs at least one source edit")
        for edit in edits:
            if not isinstance(edit, dict):
                raise ValueError("Plant edits must be objects")
            _path(workspace, edit.get("path"))
            before, after, count = edit.get("search"), edit.get("replace"), edit.get("count", 1)
            if not isinstance(before, str) or not before or not isinstance(after, str) or before == after:
                raise ValueError("Plant edits need different search and replace literals")
            if type(count) is not int or count < 1:
                raise ValueError("Plant edit count must be a positive integer")
        _assertion(plant.get("confirm"), "plant " + name + ".confirm", require_content=True)
    return value


def _execute(assertion, execute, label, print_output=True):
    result = execute(assertion["command"])
    output = result.stdout or ""
    if output and print_output:
        print(output, end="" if output.endswith("\n") else "\n", flush=True)
    if result.returncode:
        raise ValueError(label + " failed: " + (result.stderr or "").strip())
    if "contains" in assertion and assertion["contains"] not in output:
        raise ValueError(label + " did not observe expected content: " + assertion["contains"])
    if "absent" in assertion and assertion["absent"] in output:
        raise ValueError(label + " reported differing synced copies")
    return result


def sync_contract(contract, execute, check=False):
    """execute receives an argv array and returns captured CompletedProcess."""
    sync = contract["sync"]
    if check:
        if not sync.get("check"):
            raise ValueError("This project has no sync.check contract; declare its read-only checker in .xorder/testing.json")
        _execute(sync["check"], execute, "Sync check")
        print("Synced copies match their project sources", flush=True)
    else:
        _execute({"command": sync["command"]}, execute, "Project sync")


def _replace(path, content, mode):
    """Replace an inode so an unexpected hardlink cannot mutate another copy."""
    descriptor, temporary = tempfile.mkstemp(prefix=".xorder-plant-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _workspace_lock(workspace, env):
    folder = state_root(env) / "plants" / hashlib.sha256(str(workspace).encode()).hexdigest()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / "lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another plant operation owns this workspace") from error
        yield folder / "recovery.json"


def _plan(workspace, edits, env):
    originals, planted = {}, {}
    for edit in edits:
        path = _path(workspace, edit["path"])
        relative = path.relative_to(workspace).as_posix()
        if relative not in originals:
            if not path.is_file():
                raise ValueError("Plant source is missing: " + relative)
            git = ["git", "--literal-pathspecs", "-C", str(workspace)]
            tracked = subprocess.run([*git, "ls-files", "--error-unmatch", "--", relative], env=env, capture_output=True)
            clean = subprocess.run([*git, "diff", "--quiet", "HEAD", "--", relative], env=env)
            if tracked.returncode or clean.returncode:
                raise ValueError("Plant source must be tracked and match Git HEAD: " + relative)
            content = path.read_bytes()
            originals[relative] = (content, stat.S_IMODE(path.stat().st_mode))
            planted[relative] = content.decode("utf-8")
        before, count = edit["search"], edit.get("count", 1)
        if planted[relative].count(before) != count:
            raise ValueError("Plant search count differs for " + relative + "; expected " + str(count))
        planted[relative] = planted[relative].replace(before, edit["replace"])
    if all(planted[relative].encode() == content for relative, (content, mode) in originals.items()):
        raise ValueError("Plant edits cancelled each other; no source fault would be applied")
    return [{"path": relative, "original": base64.b64encode(content).decode(), "mode": mode,
             "planted_sha256": hashlib.sha256(planted[relative].encode()).hexdigest(),
             "planted": planted[relative].encode()}
            for relative, (content, mode) in originals.items()]


def _restore(workspace, journal, contract, execute):
    recovery = json.loads(journal.read_text())
    if recovery.get("workspace") != str(workspace):
        raise ValueError("Plant recovery belongs to a different workspace")
    conflicts = []
    for entry in recovery["files"]:
        path = _path(workspace, entry["path"])
        original = base64.b64decode(entry["original"], validate=True)
        if not path.is_file():
            conflicts.append(entry["path"])
            continue
        current = path.read_bytes()
        if (stat.S_IMODE(path.stat().st_mode) != entry["mode"]
                or (current != original and hashlib.sha256(current).hexdigest() != entry["planted_sha256"])):
            conflicts.append(entry["path"])
            continue
        _replace(path, original, entry["mode"])
    if conflicts:
        raise ValueError("Plant recovery kept newer source edits in " + ", ".join(conflicts) + "; recovery retained at " + str(journal))
    sync_contract(contract, execute)
    sync_contract(contract, execute, check=True)
    journal.unlink()
    print("Restored source and resynced project copies", flush=True)


@contextmanager
def _interrupt_cleanup():
    def interrupt(signum, frame):
        raise KeyboardInterrupt("Plant interrupted by signal " + str(signum))
    previous = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_plant(workspace, env, contract, arguments, execute, test):
    """Caller holds the heavy-run lease; test(args) uses its normal test receipt."""
    workspace = Path(workspace).resolve(strict=True)
    if arguments == ["--list"]:
        print("\n".join(sorted(contract["plants"])) or "No named plants declared in .xorder/testing.json")
        return 0
    if not arguments:
        raise ValueError("Usage: xr plant NAME [Playwright arguments] | --list | --restore")
    if not contract["sync"].get("check"):
        raise ValueError("A plant needs sync.check to verify cleanup of generated copies")
    with _workspace_lock(workspace, env) as journal:
        if arguments == ["--restore"]:
            if not journal.exists():
                raise ValueError("No interrupted plant recovery exists for this workspace")
            _restore(workspace, journal, contract, execute)
            return 0
        name, *extra = arguments
        if name not in contract["plants"]:
            raise ValueError("Unknown plant: " + name + "; inspect plant --list")
        if journal.exists():
            raise ValueError("An interrupted plant needs recovery; run plant --restore first")
        definition = contract["plants"][name]
        files = _plan(workspace, definition["edits"], env)
        recovery = {"workspace": str(workspace), "name": name,
                    "files": [{key: value for key, value in entry.items() if key != "planted"} for entry in files]}
        _replace(journal, json.dumps(recovery).encode(), 0o600)
        with _interrupt_cleanup():
            outcome, failure, cleanup_safe = None, None, True
            try:
                for entry in files:
                    _replace(_path(workspace, entry["path"]), entry["planted"], entry["mode"])
                sync_contract(contract, execute)
                sync_contract(contract, execute, check=True)
                _execute(definition["confirm"], execute, "Served plant confirmation", print_output=False)
                print("Confirmed served plant: " + name, flush=True)
                previous = env.get("XORDER_PLANT_NAME")
                env["XORDER_PLANT_NAME"] = name
                try:
                    outcome = test(extra[1:] if extra[:1] == ["--"] else extra)
                    return outcome
                finally:
                    if previous is None:
                        env.pop("XORDER_PLANT_NAME", None)
                    else:
                        env["XORDER_PLANT_NAME"] = previous
            except BaseException as error:
                failure = error
                cleanup_safe = getattr(error, "plant_cleanup_safe", True)
                raise
            finally:
                if not cleanup_safe:
                    print("Plant cleanup deferred because the test payload may still be running; stop it before plant --restore. Recovery retained at " + str(journal), file=sys.stderr, flush=True)
                else:
                    try:
                        _restore(workspace, journal, contract, execute)
                    except Exception as error:
                        if failure is None and (outcome is None or outcome == 0):
                            raise
                        print("Plant cleanup failed: " + str(error) + "; recovery retained at " + str(journal), file=sys.stderr, flush=True)
