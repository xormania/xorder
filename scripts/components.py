#!/usr/bin/env python3
"""Internal prepared build inputs: exact keys, component dependencies and publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys

from artifact_identity import _files_current, _path, _sources, _matches, apt_refresh
from build_cache import cache_image, current_branch, github_plan, plan as cache_plan
from registry import resolve

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
ARGUMENT = re.compile(r"[A-Z][A-Z0-9_]*")
PREPARED = {}


def _read(path):
    return json.loads(Path(path).read_text())


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def definitions(root=ROOT):
    root = Path(root)
    result = {}
    paths = sorted((root / "images/components").glob("*/definition.json"))
    if not paths:
        return {}
    schema_path = root / "schemas/component.schema.json"
    schema = _read(schema_path if schema_path.is_file() else ROOT / "schemas/component.schema.json")
    import jsonschema
    for path in paths:
        item = _read(path)
        jsonschema.validate(item, schema)
        name = item["id"]
        if name != path.parent.name or name in result:
            raise ValueError(f"Component identity does not match its unique path: {path}")
        groups = [item.get(key, {}) for key in ("build_args", "tool_args", "image_bases", "components")]
        names = [argument for group in groups for argument in group]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate component build argument: {name}")
        if set(names).intersection({"SOURCE_COMMIT", "IMAGE_VERSION", "XORDER_COMPONENT_KEY"}):
            raise ValueError("Component provenance arguments are reserved")
        _path(item["dockerfile"])
        result[name] = item
    _ordered(result, result)
    return result


def _ordered(selected, defs):
    order, done = [], set()
    def visit(name, active):
        if name not in defs:
            raise ValueError(f"Unknown build component: {name}")
        if name in active:
            raise ValueError(f"Cyclic build component: {name}")
        if name in done:
            return
        for dependency in defs[name].get("components", {}).values():
            visit(dependency, active | {name})
        done.add(name)
        order.append(name)
    for name in sorted(selected):
        visit(name, set())
    return order


def _arguments(item, root, tools):
    result = dict(item.get("build_args", {}))
    for argument, dotted in item.get("tool_args", {}).items():
        value = tools
        for part in dotted.split("."):
            value = value[part]
        if dotted == "apt_indexes":
            value = apt_refresh(tools)
        elif isinstance(value, dict) and set(value) >= {"tag", "digest"}:
            value = value["tag"] + "@" + value["digest"]
        if not isinstance(value, str) or not value:
            raise ValueError(f"Component tool argument is not a string or image pin: {dotted}")
        result[argument] = value
    for argument, line in item.get("image_bases", {}).items():
        family, variant = line.split("/", 1)
        definition = _read(Path(root) / "images" / family / "definition.json")
        base = definition["lines"][variant]["base"]
        if "parent" in base:
            raise ValueError(f"Component image_bases needs an upstream digest, not a derived image: {line}")
        result[argument] = base["tag"] + "@" + base["digest"]
    return result


def clear_prepared():
    PREPARED.clear()


def _recipe_inputs(recipe, arguments, component_arguments):
    """Reject implicit/mutable image donors and undeclared manifest arguments."""
    declared = set(re.findall(r"^\s*ARG\s+([A-Z][A-Z0-9_]*)(?:=|\s|$)", recipe, re.M))
    supplied = set(arguments) | set(component_arguments)
    reserved = {"SOURCE_COMMIT", "IMAGE_VERSION", "XORDER_COMPONENT_KEY"}
    if declared - supplied - reserved:
        raise ValueError("Unbound component build arguments: " + ", ".join(sorted(declared - supplied - reserved)))
    if supplied - declared:
        raise ValueError("Component arguments absent from Dockerfile: " + ", ".join(sorted(supplied - declared)))
    for instruction in recipe.replace("\\\n", " ").splitlines():
        if (re.search(r"\$(?:\{(?:SOURCE_COMMIT|IMAGE_VERSION)\}|(?:SOURCE_COMMIT|IMAGE_VERSION)\b)", instruction)
                and not re.match(r"^\s*(LABEL|#)\b", instruction, re.I)):
            raise ValueError("Component source/revision arguments may only affect labels")
    stages = set()
    for line in recipe.replace("\\\n", " ").splitlines():
        match = re.match(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, re.I)
        if not match:
            continue
        value, stage = match.groups()
        variable = re.fullmatch(r"\$\{?([A-Z][A-Z0-9_]*)\}?", value)
        if variable:
            name = variable[1]
            if name not in component_arguments:
                value = arguments.get(name, "")
            else:
                value = "scratch"  # Exact dependency output is bound by its key and resolved before building.
        if value.lower() not in stages and value != "scratch" and not re.fullmatch(r"[^@\s]+@sha256:[a-f0-9]{64}", value):
            raise ValueError("Component FROM input requires an exact digest: " + value)
        if stage:
            stages.add(stage.lower())
    for donor in re.findall(r"^\s*COPY\s+(?:--\S+\s+)*?--from=(\S+)", recipe, re.M | re.I):
        if donor.lower() not in stages and not donor.isdigit() and not re.fullmatch(r"[^@\s]+@sha256:[a-f0-9]{64}", donor):
            raise ValueError("Component COPY donor requires an exact digest or declared stage: " + donor)


def build_inputs(component_id, root=ROOT, platform="linux/amd64", tools=None):
    root = Path(root)
    defs = definitions(root)
    tools = _read(root / "images/tools.json") if tools is None else tools
    snapshots = {}
    for name in _ordered([component_id], defs):
        item = defs[name]
        if platform not in item["platforms"]:
            raise ValueError(f"Unsupported component platform: {name}/{platform}")
        recipe_path = _path(item["dockerfile"])
        recipe = (root / recipe_path).read_text()
        arguments = _arguments(item, root, tools)
        _recipe_inputs(recipe, arguments, item.get("components", {}))
        files = _files_current(root.resolve(), recipe_path, recipe,
                               arguments.get("IMAGE_LINE", name),
                               (root / ".dockerignore").read_text().splitlines())
        snapshots[name] = {"schema_version": 1, "id": name, "platform": platform,
                           "abi": item["abi"], "dockerfile": recipe_path,
                           "target": item.get("target", ""), "files": files,
                           "build_arguments": arguments,
                           "components": {argument: {"id": dependency, "key": _hash(snapshots[dependency])}
                                          for argument, dependency in item.get("components", {}).items()}}
    return snapshots[component_id]


def build_key(component_id, root=ROOT, platform="linux/amd64", tools=None):
    return _hash(build_inputs(component_id, root, platform, tools))


def image_inputs(definition, root=ROOT):
    defs = definitions(root)
    result = {}
    for argument, name in definition.get("build_components", {}).items():
        if name not in defs:
            raise ValueError(f"Unknown component for {definition.get('line_id')}: {name}")
        platform = definition["platforms"][0]
        result[argument] = {"id": name, "key": build_key(name, root, platform),
                            "abi": defs[name]["abi"], "platform": platform}
    return result


def affected_components(changed, root=ROOT, previous_tools=None):
    root = Path(root)
    defs = definitions(root)
    chosen = set()
    for name, item in defs.items():
        snapshot = build_inputs(name, root)
        manifest = f"images/components/{name}/definition.json"
        for path in changed:
            if path == "images/tools.json":
                if previous_tools is None or build_key(name, root, tools=previous_tools) != _hash(snapshot):
                    chosen.add(name)
            elif (path == manifest or path in snapshot["files"]
                  or any(_matches(path, source) for source in _sources(
                      (root / item["dockerfile"]).read_text(), snapshot["build_arguments"].get("IMAGE_LINE", name)))):
                chosen.add(name)
            elif path in {
                    "scripts/components.py", "schemas/component.schema.json", "scripts/artifact_identity.py"}:
                chosen.add(name)
            elif any(path == f"images/{line.split('/', 1)[0]}/definition.json"
                     for line in item.get("image_bases", {}).values()):
                chosen.add(name)
    while True:
        consumers = {name for name, item in defs.items()
                     if set(item.get("components", {}).values()).intersection(chosen)}
        if consumers <= chosen:
            break
        chosen.update(consumers)
    return sorted(chosen)


def affected_images(changed, image_defs, root=ROOT, previous_tools=None):
    chosen = set(affected_components(changed, root, previous_tools))
    return {line for line, definition in image_defs.items()
            if chosen.intersection(definition.get("build_components", {}).values())}


def repository(env=None):
    env = os.environ if env is None else env
    return env.get("GITHUB_REPOSITORY", "xormania/xorder")


def reference(name, root=ROOT, platform="linux/amd64", env=None):
    return cache_image(repository(env)) + ":component-" + name[:40] + "-" + build_key(name, root, platform)


def _cache(name, item, env):
    scope = "c-" + _hash({"id": name, "abi": item["abi"], "platform": "linux/amd64"})[:20]
    if env.get("GITHUB_EVENT_PATH"):
        return github_plan(dict(env, XORDER_CACHE_SCOPE=scope))
    return cache_plan(repository(env), current_branch(ROOT), "master", scope=scope)


def _run(command, root=ROOT, **kwargs):
    return subprocess.run(command, cwd=root, check=True, **kwargs)


def _trusted_publication(env):
    if not (env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_EVENT_NAME") == "push"
            and env.get("GITHUB_REF") == "refs/heads/master"):
        return False
    event = _read(env["GITHUB_EVENT_PATH"])
    return (not event.get("deleted", False)
            and event.get("repository", {}).get("full_name", "").lower() == repository(env).lower())


def prepare(selected, source="local", root=ROOT, publish=False, env=None, require_published=False):
    """Resolve or build each input once; publish a completed input immediately."""
    root = Path(root)
    env = dict(os.environ if env is None else env)
    if publish and not _trusted_publication(env):
        raise ValueError("Component publication requires the repository's real master push event")
    defs = definitions(root)
    refs = {}
    for name in _ordered(selected, defs):
        item = defs[name]
        key = build_key(name, root)
        identity = (str(root.resolve()), name, key, publish, require_published, repository(env), source, _hash(item.get("verify", [])))
        if identity in PREPARED:
            refs[name] = PREPARED[identity]
            continue
        tag = reference(name, root, env=env)
        try:
            existing = resolve(tag, authenticated=publish or require_published)
        except Exception as error:
            if publish:
                raise
            # A cache outage must not prevent a verified build from authored inputs.
            print(f"Component cache unavailable for {name}: {error}; building authored inputs", file=sys.stderr)
            existing = None
        if existing:
            ref = tag.split(":component-", 1)[0] + "@" + existing["digest"]
            try:
                _run(["docker", "pull", "--platform", "linux/amd64", ref], root)
            except subprocess.CalledProcessError:
                if publish or require_published:
                    raise
                print(f"Component pull unavailable for {name}; building authored inputs", file=sys.stderr)
                existing = None
            if existing:
                labels = json.loads(subprocess.check_output(
                    ["docker", "image", "inspect", ref, "--format", "{{json .Config.Labels}}"], cwd=root, text=True)) or {}
                if labels.get("io.xorder.component.key") != key or labels.get("io.xorder.component.id") != name:
                    raise ValueError(f"Component cache identity mismatch: {name}")
                _verify(item, ref, root)
                _receipt(name, key, ref, source, root)
                refs[name] = ref
                PREPARED[identity] = ref
                continue
        if require_published:
            raise ValueError(f"Prepared component is not published: {name}; publish its trusted master inputs first")
        local = "image-library-component:" + name + "-" + key[:16]
        args = _arguments(item, root, _read(root / "images/tools.json"))
        args.update({argument: refs[dependency] for argument, dependency in item.get("components", {}).items()})
        command = ["docker", "buildx", "build", "--load", "--platform", "linux/amd64", "-t", local,
                   "-f", item["dockerfile"], "--label", "io.xorder.component.key=" + key,
                   "--label", "io.xorder.component.id=" + name,
                   "--label", "org.opencontainers.image.source=https://github.com/" + repository(env)]
        if item.get("target"):
            command += ["--target", item["target"]]
        # Local FROM donors must remain visible to the daemon's builder.
        if any(value.startswith("image-library-component:") for value in args.values()):
            context = subprocess.check_output(["docker", "context", "show"], text=True).strip()
            command += ["--builder", context]
        cache = _cache(name, item, env)
        for value in cache["cache-from"]:
            command += ["--cache-from", value]
        if publish and cache["write-enabled"]:
            command += ["--cache-to", cache["cache-to"]]
        local_cache = None
        if env.get("LIBRARY_CACHE_DIR"):
            local_cache = Path(env["LIBRARY_CACHE_DIR"]) / "components" / (name + "-" + key)
            local_cache.parent.mkdir(parents=True, exist_ok=True)
            if (local_cache / "index.json").is_file():
                command += ["--cache-from", "type=local,src=" + str(local_cache)]
            shutil.rmtree(str(local_cache) + "-next", ignore_errors=True)
            command += ["--cache-to", "type=local,dest=" + str(local_cache) + "-next,mode=max"]
        certificate = env.get("CA_CERTIFICATE")
        if certificate:
            import csv
            import io
            path = Path(certificate)
            if not path.is_absolute() or not path.is_file():
                raise ValueError("CA_CERTIFICATE must be an absolute readable PEM file")
            option = io.StringIO()
            csv.writer(option, lineterminator="").writerow(["id=xorder_ca", "src=" + str(path)])
            command += ["--secret", option.getvalue()]
        for argument, value in sorted(args.items()):
            command += ["--build-arg", argument + "=" + value]
        _run(command + ["."], root)
        if local_cache:
            shutil.rmtree(local_cache, ignore_errors=True)
            Path(str(local_cache) + "-next").rename(local_cache)
        _verify(item, local, root)
        ref = local
        if publish:
            # The singleton publishing workflow is the only writer. Recheck an
            # existing identity before pushing so recovery never reassigns it.
            published = resolve(tag, authenticated=True)
            if not published:
                _run(["docker", "tag", local, tag], root)
                _run(["docker", "push", tag], root)
                published = resolve(tag, authenticated=True)
            if not published:
                raise ValueError(f"Published component cannot be resolved: {name}")
            ref = tag.split(":component-", 1)[0] + "@" + published["digest"]
        refs[name] = ref
        PREPARED[identity] = ref
        _receipt(name, key, ref, source, root)
    return refs


def _verify(item, ref, root):
    if item.get("verify"):
        first, *rest = item["verify"]
        _run(["docker", "run", "--rm", "--entrypoint", first, ref, *rest], root)


def _receipt(name, key, ref, source, root):
    output = root / "out/components" / (name + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"id": name, "key": key, "reference": ref,
                                  "request_source_commit": source, "inputs": build_inputs(name, root)}, indent=2) + "\n")


def arguments(definition, source="local", root=ROOT, require_published=False):
    bindings = definition.get("build_components", {})
    if not bindings:
        return {}
    refs = prepare(bindings.values(), source, root, require_published=require_published)
    return {argument: refs[name] for argument, name in bindings.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "publish", "plan"))
    parser.add_argument("--base")
    parser.add_argument("--source", default=os.environ.get("GITHUB_SHA", "local"))
    args = parser.parse_args(argv)
    clear_prepared()
    defs = definitions()
    if args.command == "check":
        for name in defs:
            build_inputs(name)
        return
    changed = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", args.base, "HEAD"], text=True).splitlines() if args.base and set(args.base) != {"0"} else None
    selected = affected_components(changed) if changed is not None else list(defs)
    if args.command == "plan":
        print(json.dumps({"component": selected}))
    else:
        prepare(selected, args.source, publish=True)


if __name__ == "__main__":
    main()
