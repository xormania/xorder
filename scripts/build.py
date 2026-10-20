#!/usr/bin/env python3
"""Build a profile from locked inputs; browser requires an explicit parent."""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from library import ROOT, children, definitions, fingerprint, read, records, reusable_record, validate_inventory
from image_validation import prerequisites, supported_suites
from build_cache import current_branch, plan as registry_cache_plan


def reusable_artifact(line, parent=None):
    """Reuse an accepted exact artifact only when all current inputs match."""
    d = definitions()[line]
    record = reusable_record(d, records(), parent)
    if record is not None:
        return record["publication"]["repository"] + "@" + record["publication"]["digest"]
    return None


def pinned(base):
    return base["tag"] + "@" + base["digest"]


def build(line, image, source, parent=None, cache=None, registry_imports=()):
    d = definitions()[line]
    if d["base"].get("parent") and not parent:
        raise ValueError(f"{line} derives from {d['base']['parent']}; supply "
                         "--parent <accepted parent digest> or build the parent with --children")
    tools = read(ROOT / "images/tools.json")
    from artifact_identity import apt_refresh
    args = {"BASE_IMAGE": parent or pinned(d["base"]), "SOURCE_COMMIT": source,
            "IMAGE_VERSION": d["revision"], "APT_REFRESH": apt_refresh(tools), "IMAGE_LINE": d["line"]}
    if d["family"] in ("php-dev", "php-frankenphp"):
        args.update(COMPOSER_IMAGE=pinned(tools["composer"]), REDIS_VERSION=tools["redis_version"],
                    XDEBUG_VERSION=tools["xdebug_version"], PCOV_VERSION=tools["pcov_version"],
                    SYMFONY_URL=tools["symfony"]["url"], SYMFONY_SHA256=tools["symfony"]["sha256"])
        args.update(INFECTION_URL=tools["infection"]["url"], INFECTION_SHA256=tools["infection"]["sha256"])
    if d["family"] == "php-frankenphp":
        args["APCU_VERSION"] = tools["apcu_version"]
    if d["family"] in ("uxor-dev", "php-serena", "harness-live"):
        args["NODE_IMAGE"] = pinned(tools["node"])
    if d["family"] == "uxor-dev":
        args.update(TAILWIND_VERSION=tools["tailwind"]["version"],
                    TAILWIND_URL=tools["tailwind"]["url"], TAILWIND_SHA256=tools["tailwind"]["sha256"])
    if d["family"] == "python-dev":
        args["UV_IMAGE"] = pinned(tools["uv"])
    local_parent = parent and parent.startswith("image-library-")
    cmd = ["docker", "buildx", "build", "--load", "--platform", "linux/amd64", "-t", image,
           "-f", f"images/{d['family']}/Dockerfile"]
    ca = os.environ.get("CA_CERTIFICATE")
    if ca:
        path = Path(ca)
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.R_OK):
            raise ValueError("CA_CERTIFICATE must be a readable absolute PEM file")
        # BuildKit parses CSV, so quote the entire src field for comma-containing paths.
        import csv
        import io
        secret = io.StringIO()
        csv.writer(secret, lineterminator="").writerow(["id=xorder_ca", "src=" + str(path)])
        cmd += ["--secret", secret.getvalue()]
    if local_parent:
        # The daemon's implicit builder shares its local image store. A custom
        # Docker context (as in CI) need not be named "default".
        context = subprocess.check_output(["docker", "context", "show"], text=True).strip()
        cmd += ["--builder", context]
    for item in registry_imports:
        cmd += ["--cache-from", item]
    cache_path = None
    if cache and os.environ.get("LIBRARY_CACHE_DIR"):
        cache_path = Path(os.environ["LIBRARY_CACHE_DIR"]) / cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            cmd += ["--cache-from", f"type=local,src={cache_path}"]
        shutil.rmtree(str(cache_path) + "-next", ignore_errors=True)
        cmd += ["--cache-to", f"type=local,dest={cache_path}-next,mode=max"]
    for name, value in args.items():
        cmd += ["--build-arg", f"{name}={value}"]
    subprocess.run(cmd + ["."], cwd=ROOT, check=True)
    if cache_path:
        shutil.rmtree(cache_path, ignore_errors=True)
        Path(str(cache_path) + "-next").rename(cache_path)


def image_facts(image):
    return json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]


def image_measurements(image):
    info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], text=True))
    driver_type = dict(info.get("DriverStatus") or []).get("driver-type", "classic")
    return {"image_size_bytes": image_facts(image)["Size"],
            "size_method": "docker-image-inspect-size", "image_store": info["Driver"] + "/" + driver_type}


def cache_source(cache):
    """Describe the external cache input, without claiming a layer cache hit."""
    directory = os.environ.get("LIBRARY_CACHE_DIR")
    if not cache or not directory:
        return "disabled"
    return "restored" if (Path(directory) / cache / "index.json").is_file() else "empty"


def cache_probe(line, image, source, parent=None):
    """A new source label must reuse the tested filesystem layers."""
    before = image_facts(image)
    probe = image + "-cache-probe"
    start = time.monotonic()
    build(line, probe, source + "-cache-probe", parent)
    after = image_facts(probe)
    assert before["RootFS"]["Layers"] == after["RootFS"]["Layers"], "Source labels invalidated filesystem layers"
    assert after["Config"]["Labels"]["org.opencontainers.image.revision"] == source + "-cache-probe"
    subprocess.run(["docker", "image", "rm", probe], check=True)
    return round(time.monotonic() - start, 2)


def inspect(line, image, destination):
    cmd = ["docker", "run", "--rm", "--mount", f"type=bind,src={ROOT / 'scripts'},dst=/inventory,readonly", image,
           "python3", "/inventory/inventory.py", line.split("/")[0]]
    if line.startswith("harness-live/"):
        # The immutable image inventory describes its runtime, not private,
        # independently managed harnesses initialized in an operator's HOME.
        cmd[3:3] = ["-e", "HARNESS_AUTO_INSTALL=0"]
    result = subprocess.check_output(cmd, text=True)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    try:
        validate_inventory(definitions()[line], json.loads(result))
    except (ValueError, AssertionError):
        Path(str(destination) + ".stdout").write_text(result)
        raise
    Path(destination).write_text(result)


def prepare_parity_application(fixture, source):
    """Build a pending authored app for source CI; accepted exact pins need no build."""
    from playwright_fixture import inputs
    selected = fixture.get("application_resource")
    if selected is None:
        return None
    if (not isinstance(selected, dict) or not isinstance(selected.get("id"), str)
            or not selected["id"].startswith("image/uxor-dev/")
            or not isinstance(selected.get("version"), str)):
        raise ValueError("Source parity requires an exact canonical application resource")
    catalog = read(ROOT / "catalog-v2.json")
    matching = [entry for entry in catalog["resources"]
                if entry["id"] == selected["id"] and entry["version"] == selected["version"]]
    accepted = [entry for entry in matching
                if entry["lifecycle"] == "available" and entry["verification"]["status"] == "passed"
                and "linux/amd64" in entry["targets"]]
    if accepted:
        # The same strict resolver used for publication validates the public pin.
        inputs(fixture, catalog)
        return None
    if matching:
        raise ValueError("Selected parity application record is not available and verified")
    defs = definitions()
    app_line = selected["id"].removeprefix("image/")
    if (app_line not in defs or defs[app_line]["family"] != "uxor-dev"
            or defs[app_line]["revision"] != selected["version"]):
        raise ValueError("Pending parity resource must match the exact authored application revision")
    if not source:
        raise ValueError("Source parity needs the validating checkout's source identity")
    root_line = app_line
    while defs[root_line]["base"].get("parent"):
        root_line = defs[root_line]["base"]["parent"]
    if root_line == app_line:
        raise ValueError("Canonical parity application needs its declared image prerequisite")
    folder = ROOT / "out/parity-application" / app_line.replace("/", "-")
    options = argparse.Namespace(line=root_line, image="image-library-parity:" + root_line.replace("/", "-"),
                                 source=source, parent=None, cache=None, registry_imports=(),
                                 inventory=str(folder / (defs[root_line]["family"] + ".json")),
                                 cache_probe=False, reuse_accepted=True, children=True)
    # The image matrix owns the app's full runtime fixture. Prepare only its
    # build inputs here; the browser parity run establishes app readiness.
    validate_tree(options, defs, set(), prerequisites(root_line, [app_line], defs))
    app_tag = "image-library-check:" + defs[app_line]["family"]
    facts = image_facts(app_tag)
    labels = facts.get("Config", {}).get("Labels") or {}
    if (labels.get("org.opencontainers.image.revision") != source
            or labels.get("org.opencontainers.image.version") != selected["version"]
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", facts.get("Id", ""))):
        raise ValueError("Local parity application does not match the validating source and revision")
    inspect(app_line, facts["Id"], folder / (defs[app_line]["family"] + ".json"))
    return facts["Id"]


def checked_suites(family, suites):
    """Reject incomplete or unsupported plans before any image action."""
    if (not isinstance(suites, list) or not suites
            or not all(isinstance(suite, str) for suite in suites)
            or len(suites) != len(set(suites))):
        raise ValueError("Verification suites must be a nonempty array of unique names")
    if "full" in suites and len(suites) != 1:
        raise ValueError("Full verification cannot be combined with partial suites")
    if not set(suites) <= supported_suites(family):
        raise ValueError(f"Unsupported verification suite for {family}: {suites}")
    return suites


def verify(line, image, destination, *, source_validation=False, source=None, suites=None):
    command = ["bash", str(ROOT / "scripts/verify-image.sh"), line, image]
    family = definitions()[line]["family"]
    suites = checked_suites(family, ["full"] if suites is None else suites)
    full = suites == ["full"]
    if not full:
        command += suites
    environment = dict(os.environ)
    # A caller cannot smuggle an unconstrained fixture exemption through the
    # builder. The trusted verify entry point authors its own observed proof.
    environment.pop("XORDER_SOURCE_VALIDATION_PROOF", None)
    if family == "playwright-browser":
        environment.pop("XORDER_PARITY_LOCAL_APPLICATION", None)
    if full and source_validation and family == "playwright-browser":
        fixture = read(ROOT / "tests/fixtures/playwright/consumers" / (line.split("/", 1)[1] + ".json"))
        local_app = prepare_parity_application(fixture, source)
        if local_app:
            environment["XORDER_PARITY_LOCAL_APPLICATION"] = local_app
    if full and family in ("uxor-dev", "playwright-browser"):
        from xorder.downstream import observe_source_images, source_commit, write_source_proof
        service = "browser" if family == "playwright-browser" else "php"
        with tempfile.TemporaryDirectory(prefix="xorder-source-proof-") as proof_directory:
            proof_path = Path(proof_directory) / "builder-proof.json"
            write_source_proof(proof_path, observe_source_images({service: image}), source_commit(ROOT))
            environment["XORDER_SOURCE_VALIDATION_PROOF"] = str(proof_path)
            subprocess.run(command, check=True, env=environment)
    else:
        subprocess.run(command, check=True, env=environment)
    inspect(line, image, destination)


def validate_tree(a, defs, selected=None, needed=None):
    """Prepare ancestor inputs, testing only selected nodes and visiting no siblings."""
    cache = cache_source(a.cache)
    reused = reusable_artifact(a.line, a.parent) if a.reuse_accepted else None
    start = time.monotonic()
    if reused:
        subprocess.run(["docker", "pull", "--platform", "linux/amd64", reused], check=True)
        a.image = reused
    else:
        imports = getattr(a, "registry_imports", ())
        if imports:
            build(a.line, a.image, a.source, a.parent, a.cache, registry_imports=imports)
        else:
            build(a.line, a.image, a.source, a.parent, a.cache)
    built = time.monotonic()
    should_verify = selected is None or a.line in selected
    requested_suites = (getattr(a, "verify_suites", None) or {}).get(a.line, ["full"])
    # A partial check extends existing release evidence; a new artifact has no
    # such evidence and must establish the complete readiness contract.
    actual_suites = requested_suites if reused else ["full"]
    if should_verify:
        if actual_suites != ["full"]:
            verify(a.line, a.image, a.inventory, suites=actual_suites)
        elif defs[a.line]["family"] == "playwright-browser":
            verify(a.line, a.image, a.inventory, source_validation=True, source=a.source)
        else:
            verify(a.line, a.image, a.inventory)
    verified = time.monotonic()
    verification_status = "prerequisite"
    if should_verify:
        verification_status = "passed" if actual_suites == ["full"] else "partial-passed"
    metrics = {"line": a.line, **image_measurements(a.image), "cache_source": cache,
               "artifact_reused": bool(reused),
               "verification_status": verification_status,
               "verification_suites": actual_suites if should_verify else []}
    if should_verify:
        metrics["requested_verification_suites"] = requested_suites
        metrics["verify_seconds"] = round(verified-built, 2)
    metrics["pull_seconds" if reused else "build_seconds"] = round(built-start, 2)
    if a.cache_probe and not reused and should_verify:
        metrics["source_label_rebuild_seconds"] = cache_probe(a.line, a.image, a.source, a.parent)
    destination = Path(a.inventory).with_suffix(".metrics.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        scope = ("full behavior" if actual_suites == ["full"]
                 else "selected fixtures (" + ", ".join(actual_suites) + ")")
        verification = (f"{scope}/inventory: {metrics['verify_seconds']}s.\n" if should_verify
                        else "build prerequisite only; behavior not requested.\n")
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write(f"\n### {a.line}\n\nImage: {metrics['image_size_bytes']/1024**2:.1f} MiB; "
                          f"{'pull (accepted artifact reused)' if reused else 'build'}: {round(built-start, 2)}s; "
                          + verification)
            if a.cache_probe and not reused and should_verify:
                summary.write(f"Source-label-only rebuild: {metrics['source_label_rebuild_seconds']}s; filesystem layers unchanged.\n")
    if a.children:
        for child in children(a.line, defs):
            if needed is not None and child not in needed:
                continue
            family = defs[child]["family"]
            child_args = argparse.Namespace(**vars(a))
            child_args.line = child
            child_args.image = "image-library-check:" + family
            child_args.parent = a.image
            child_args.inventory = str(Path(a.inventory).with_name(family + ".json"))
            if a.cache:
                child_args.cache = child.replace("/", "-")
            validate_tree(child_args, defs, selected, needed)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("line"); p.add_argument("image")
    p.add_argument("--source", default="local"); p.add_argument("--parent"); p.add_argument("--cache")
    p.add_argument("--registry-cache", help="Read-only GHCR build cache owned by GitHub owner/name")
    p.add_argument("--cache-branch", help="Registry cache branch; defaults to this checkout's branch")
    p.add_argument("--cache-default-branch", default="master", help="Registry cache default branch")
    p.add_argument("--cache-scope", default="", help="Registry cache scope, matching the consuming CI build")
    p.add_argument("--inventory", default="out/inventory.json")
    p.add_argument("--cache-probe", action="store_true")
    p.add_argument("--reuse-accepted", action="store_true", help="Pull unchanged accepted artifacts and run behavior without rebuilding")
    p.add_argument("--children", action="store_true", help="Build and verify derived profiles with this exact local parent")
    p.add_argument("--verify-lines", help="JSON array of exact behavior targets; other ancestors supply build inputs only")
    p.add_argument("--verify-suites", help="JSON object mapping every --verify-lines target to its full or independent fixture suites")
    a = p.parse_args(argv)
    defs = definitions()
    if a.line not in defs:
        p.error(f"Unknown image line: {a.line}")
    if a.registry_cache:
        try:
            a.registry_imports = registry_cache_plan(a.registry_cache, a.cache_branch or current_branch(ROOT),
                                                    a.cache_default_branch, scope=a.cache_scope)["cache-from"]
        except ValueError as error:
            p.error(str(error))
    elif a.cache_branch or a.cache_scope:
        p.error("--cache-branch and --cache-scope require --registry-cache")
    selected, needed = None, None
    if a.verify_lines is not None:
        try:
            selected = json.loads(a.verify_lines)
            if not isinstance(selected, list) or not selected or not all(isinstance(line, str) for line in selected):
                raise ValueError("--verify-lines must be a nonempty JSON array of image lines")
            needed = prerequisites(a.line, selected, defs)
            if len(needed) > 1 and not a.children:
                raise ValueError("Descendant checks require --children")
            selected = set(selected)
        except ValueError as error:
            p.error(str(error))
    if a.verify_suites is not None:
        try:
            if selected is None:
                raise ValueError("--verify-suites requires --verify-lines")
            suites = json.loads(a.verify_suites)
            if not isinstance(suites, dict) or set(suites) != selected:
                raise ValueError("--verify-suites must name every selected image and no other images")
            a.verify_suites = {line: checked_suites(defs[line]["family"], names)
                               for line, names in suites.items()}
        except ValueError as error:
            p.error(str(error))
    try:
        validate_tree(a, defs, selected, needed)
    except ValueError as error:
        p.error(str(error))


if __name__ == "__main__":
    main()
