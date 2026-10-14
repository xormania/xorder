"""Stable image build inputs, separate from historical release fingerprints.

An image's descriptive contract and packaging revision do not allocate another
artifact. Compatibility/inventory validation remains the caller's responsibility.
Historical comparisons read the original committed inputs and retain provenance.
"""
import fnmatch
import hashlib
import json
import re
import shlex
import stat
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
KEY_VERSION = 1
MAX_FILES = 10000
MAX_BYTES = 64 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{64}")
COMMIT = re.compile(r"[a-f0-9]{40}")
ARG_TO_TOOL = {
    "COMPOSER_IMAGE": ("composer", None), "NODE_IMAGE": ("node", None),
    "UV_IMAGE": ("uv", None), "REDIS_VERSION": ("redis_version", None),
    "XDEBUG_VERSION": ("xdebug_version", None), "PCOV_VERSION": ("pcov_version", None),
    "APCU_VERSION": ("apcu_version", None), "SYMFONY_URL": ("symfony", "url"),
    "SYMFONY_SHA256": ("symfony", "sha256"), "INFECTION_URL": ("infection", "url"),
    "INFECTION_SHA256": ("infection", "sha256"), "TAILWIND_VERSION": ("tailwind", "version"),
    "TAILWIND_URL": ("tailwind", "url"), "TAILWIND_SHA256": ("tailwind", "sha256"),
}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _key(snapshot):
    return hashlib.sha256(_encoded(snapshot)).hexdigest()


def _path(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or value.startswith("/") or ".." in PurePosixPath(value).parts):
        raise ValueError(f"Unsafe build input path: {value!r}")
    return value


def _reference(value):
    """Ignore an informational tag, retaining repository and immutable digest."""
    if not isinstance(value, str):
        raise ValueError("An exact base or parent digest reference is required")
    match = re.fullmatch(r"([^@\s]+)@(sha256:[a-f0-9]{64})", value)
    if not match:
        raise ValueError(f"An exact base or parent digest reference is required: {value!r}")
    repository, digest = match.groups()
    # A colon in the final component names a tag; a registry port precedes '/'.
    final = repository.rsplit("/", 1)[-1]
    if ":" in final:
        repository = repository.rsplit(":", 1)[0]
    return repository + "@" + digest


def apt_refresh(tools):
    """Invalidate apt layers only when the observed package feeds change."""
    indexes = tools.get("apt_indexes")
    if (not isinstance(indexes, dict) or not indexes
            or any(not isinstance(url, str) or not isinstance(value, str)
                   or not SHA.fullmatch(value) for url, value in indexes.items())):
        raise ValueError("Build inputs require explicit SHA-256 apt package feed observations")
    return _key(indexes)


def _sources(recipe, line):
    sources = []
    for instruction in recipe.replace("\\\n", " ").splitlines():
        match = re.match(r"^\s*(COPY|ADD)\s+(.+)$", instruction, re.I)
        if not match:
            continue
        if match[1].upper() == "ADD":
            raise ValueError("Use explicit COPY and pinned downloads for build inputs")
        value, flags = match[2], []
        while value.startswith("--"):
            parts = value.split(None, 1)
            if len(parts) != 2:
                raise ValueError("Incomplete COPY instruction")
            flag, value = parts
            flags.append(flag)
        if any(flag.startswith("--from=") for flag in flags):
            continue
        tokens = json.loads(value) if value.startswith("[") else shlex.split(value)
        if not isinstance(tokens, list) or len(tokens) < 2:
            raise ValueError("Incomplete COPY instruction")
        for source in tokens[:-1]:
            source = source.replace("${IMAGE_LINE}", line).rstrip("/")
            _path(source)
            if "$" in source:
                raise ValueError(f"Unresolved COPY source: {source}")
            sources.append(source)
    return sorted(set(sources))


def _glob_matches(value, pattern):
    def segments(parts, tokens):
        if not tokens:
            return not parts
        if tokens[0] == "**":
            return segments(parts, tokens[1:]) or bool(parts) and segments(parts[1:], tokens)
        return bool(parts) and fnmatch.fnmatchcase(parts[0], tokens[0]) and segments(parts[1:], tokens[1:])
    return segments(value.split("/"), pattern.split("/"))


def _matches(path, source):
    return any(_glob_matches(value, source)
               for value in [path, *(str(p) for p in PurePosixPath(path).parents if str(p) != ".")])


def _ignored(path, patterns):
    ignored = False
    ancestors = [path, *(str(p) for p in PurePosixPath(path).parents if str(p) != ".")]
    for original in patterns:
        pattern = original.strip()
        if not pattern or pattern.startswith("#") or pattern == ".":
            continue
        negative = pattern.startswith("!")
        pattern = pattern.removeprefix("!").strip("/")
        if any(_glob_matches(value, pattern) for value in ancestors):
            ignored = not negative
    return ignored


def _files_current(root, recipe_path, recipe, line, ignore):
    selected = {recipe_path, ".dockerignore"}
    for source in _sources(recipe, line):
        matches = list(root.glob(source))
        if not matches:
            raise ValueError(f"Missing COPY source: {source}")
        for match in matches:
            paths = match.rglob("*") if match.is_dir() else [match]
            selected.update(str(path.relative_to(root)) for path in paths
                            if not path.is_dir() and not _ignored(str(path.relative_to(root)), ignore))
    result, total = {}, 0
    if len(selected) > MAX_FILES:
        raise ValueError("Build input file limit exceeded")
    for name in sorted(selected):
        path = root / _path(name)
        if any(candidate.is_symlink() for candidate in [path, *path.parents] if candidate != root.parent):
            raise ValueError(f"Symlink build input is not supported: {name}")
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError(f"Build input must be a regular file: {name}")
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError("Build input byte limit exceeded")
        result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "mode": "0755" if mode & 0o111 else "0644"}
    return result


def _git(root, *args, binary=False, input=None):
    result = subprocess.run(["git", *args], cwd=root, input=input, capture_output=True,
                            text=not binary, timeout=20)
    if result.returncode:
        raise ValueError("Original build source history is unavailable; artifact equivalence cannot be proved")
    return result.stdout


def _files_historical(root, source, recipe_path, line):
    if not isinstance(source, str) or not COMMIT.fullmatch(source):
        raise ValueError("Original build source requires a complete commit SHA")
    if _git(root, "cat-file", "-t", source).strip() != "commit":
        raise ValueError("Original build source must identify a commit")
    tree = _git(root, "ls-tree", "-r", "-z", source, binary=True)
    if tree.count(b"\0") > MAX_FILES:
        raise ValueError("Historical build input file limit exceeded")
    entries = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        entries[_path(name.decode())] = (mode, kind, oid)
    def content(name):
        if name not in entries or entries[name][1] != "blob" or entries[name][0] == "120000":
            raise ValueError(f"Missing or unsupported historical build input: {name}")
        oid = entries[name][2]
        if int(_git(root, "cat-file", "-s", oid)) > MAX_BYTES:
            raise ValueError("Historical build input byte limit exceeded")
        return _git(root, "cat-file", "blob", oid, binary=True)
    recipe = content(recipe_path).decode()
    ignore = content(".dockerignore").decode().splitlines()
    selected = {recipe_path, ".dockerignore"}
    for pattern in _sources(recipe, line):
        matches = {name for name in entries if _matches(name, pattern)}
        if not matches:
            raise ValueError(f"Missing historical COPY source: {pattern}")
        selected.update(name for name in matches if not _ignored(name, ignore))
    result, total = {}, 0
    for name in sorted(selected):
        data = content(name)
        total += len(data)
        if total > MAX_BYTES:
            raise ValueError("Historical build input byte limit exceeded")
        mode = entries[name][0]
        if mode not in ("100644", "100755"):
            raise ValueError(f"Unsupported historical build input mode: {name}")
        result[name] = {"sha256": hashlib.sha256(data).hexdigest(), "mode": mode[-4:]}
    return recipe, result


def _inputs(definition, recipe, files, tools, parent, *, historical=False):
    family, line = definition["family"], definition["line"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", family) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", line):
        raise ValueError("Build identity requires a safe family and line")
    if definition.get("line_id", family + "/" + line) != family + "/" + line:
        raise ValueError("Build identity line does not match its family")
    base = definition["base"]
    if base.get("parent") and not parent:
        raise ValueError("Derived build identity requires the exact resolved parent digest")
    resolved = _reference(parent or (base["tag"] + "@" + base["digest"]))
    for instruction in recipe.replace("\\\n", " ").splitlines():
        if (re.search(r"\$(?:\{(?:SOURCE_COMMIT|IMAGE_VERSION)\}|(?:SOURCE_COMMIT|IMAGE_VERSION)\b)", instruction)
                and not re.match(r"^\s*(LABEL|#)\b", instruction, re.I)):
            raise ValueError("Release provenance arguments may only affect image labels")
    arguments = set(re.findall(r"^\s*ARG\s+([A-Z_][A-Z0-9_]*)(?:\s|=|$)", recipe, re.M))
    pins = {}
    for argument, (key, field) in ARG_TO_TOOL.items():
        if argument not in arguments:
            continue
        try:
            value = tools[key][field] if field else tools[key]
            if argument.endswith("_IMAGE"):
                value = _reference(value["tag"] + "@" + value["digest"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"Missing consumed build tool pin: {argument}") from error
        if not isinstance(value, str) or not value:
            raise ValueError(f"Invalid consumed build tool pin: {argument}")
        pins[argument] = value
    if "APT_REFRESH" in arguments:
        # Early releases did not record the feed. They cannot match a release
        # whose package feed is explicitly tracked; do not invent an observation.
        pins["APT_REFRESH"] = None if historical and "apt_indexes" not in tools else apt_refresh(tools)
    return {"build_key_version": KEY_VERSION, "line_id": family + "/" + line,
            "platforms": sorted(definition["platforms"]), "resolved_base": resolved,
            "parent_line": base.get("parent"), "files": files, "build_arguments": pins}


def build_inputs(definition, root=ROOT, parent=None, tools=None):
    """Return the actual local build input snapshot, excluding release metadata."""
    root = Path(root).resolve()
    family, line = definition["family"], definition["line"]
    recipe_path = _path(f"images/{family}/Dockerfile")
    recipe = (root / recipe_path).read_text()
    ignore = (root / ".dockerignore").read_text().splitlines()
    files = _files_current(root, recipe_path, recipe, line, ignore)
    if tools is None:
        tools = json.loads((root / "images/tools.json").read_text())
    return _inputs(definition, recipe, files, tools, parent)


def build_key(definition, root=ROOT, parent=None, tools=None):
    return _key(build_inputs(definition, root, parent, tools))


def recorded_build_key(record, root=ROOT):
    """Read new identities or prove legacy identity from its exact original source."""
    if "build_key" in record:
        if record.get("build_key_version") != KEY_VERSION or not isinstance(record["build_key"], str) or not SHA.fullmatch(record["build_key"]):
            raise ValueError("Unsupported or malformed recorded build identity")
        return record["build_key"]
    definition = record["definition"]
    recipe_path = _path(f"images/{definition['family']}/Dockerfile")
    recipe, files = _files_historical(Path(root), record["source_commit"], recipe_path, definition["line"])
    return _key(_inputs(definition, recipe, files, record["tools"], record["resolved_base"], historical=True))


def existing_record_match(record, current_definition, root=ROOT, parent=None):
    if record["line_id"] != current_definition["line_id"]:
        return False
    return recorded_build_key(record, root) == build_key(current_definition, root, parent)
