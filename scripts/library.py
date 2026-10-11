#!/usr/bin/env python3
"""Definitions, verified records, deterministic discovery, and affected builds."""
import argparse
import copy
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from datetime import datetime
from image_inputs import TOOL_KEYS, files as input_files
from image_validation import affected_lines, matrix as validation_matrix

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def read(path):
    return json.loads(Path(path).read_text())


def validate_schemas(root=ROOT):
    import jsonschema
    for path in (root / "images").glob("*/definition.json"):
        jsonschema.validate(read(path), read(root / "schemas/definition.schema.json"))
    for path in (root / "release-records").rglob("*.json"):
        if path.relative_to(root / "release-records").parts[0] == "artifacts":
            continue
        jsonschema.validate(read(path), read(root / "schemas/release-record.schema.json"))
    for path in (root / "retired-records").glob("*.json"):
        jsonschema.validate(read(path), read(root / "schemas/image-retirement.schema.json"))
    jsonschema.validate(read(root / "catalog.json"), read(root / "schemas/catalog.schema.json"))
    from xorder.model import check as check_resources
    check_resources(root)


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def version(value):
    if not SEMVER.fullmatch(value):
        raise ValueError(f"Invalid image revision: {value}")
    return tuple(map(int, value.split(".")))


def definitions(root=ROOT):
    result = {}
    for path in sorted((root / "images").glob("*/definition.json")):
        definition = read(path)
        assert definition["schema_version"] == 1
        family = definition["family"]
        assert family == path.parent.name
        for line, inputs in definition["lines"].items():
            version(inputs["revision"])
            assert inputs["platforms"] == ["linux/amd64"], "Add platform build/test support before advertising it"
            base = inputs["base"]
            assert "parent" in base or DIGEST.fullmatch(base["digest"])
            item = copy.deepcopy(definition)
            del item["lines"]
            item.update(inputs)
            item["line_id"] = f"{family}/{line}"
            item["line"] = line
            result[item["line_id"]] = item
    completed = set()
    def inherit(line, visiting):
        assert line not in visiting, "Cyclic image parent"
        if line in completed:
            return
        item = result[line]
        parent = item["base"].get("parent")
        if parent:
            assert parent in result
            inherit(parent, visiting | {line})
            for key in ("capabilities", "extensions", "tools", "limitations"):
                item[key] = sorted(set(item[key] + result[parent][key]))
        completed.add(line)
    for line in result:
        inherit(line, set())
    return result


def root_line(line, defs):
    while defs[line]["base"].get("parent"):
        line = defs[line]["base"]["parent"]
    return line


def children(line, defs):
    return sorted(key for key, d in defs.items() if d["base"].get("parent") == line)


def validate_inventory(definition, inventory):
    assert inventory["platform"] in definition["platforms"]
    assert inventory["os"]["VERSION_CODENAME"] == "trixie"
    assert set(definition["extensions"]) <= set(inventory["extensions"])
    assert set(definition["tools"]) <= set(inventory["tools"])
    assert inventory["runtime_version"].startswith(definition["runtime_line"] + ".")
    if definition["family"] == "php-browser":
        browser = re.search(r"\d+", inventory["tools"]["chromium"])[0]
        driver = re.search(r"\d+", inventory["tools"]["chromedriver"])[0]
        assert browser == driver, "Chromium and driver major versions differ"
    if definition["family"] == "php-toolkit":
        projects = inventory["prepared_projects"]
        assert set(projects) == {"validator", "symfony-7.4"}
        for project in projects.values():
            assert project["packages"]["symfony/ux-toolkit"] == "v3.5.1"
            assert re.fullmatch(r"[a-f0-9]{64}", project["composer_lock_sha256"])
        assert projects["symfony-7.4"]["packages"]["symfony/framework-bundle"].startswith("v7.4.")
    if definition["family"] == "playwright-browser" and definition.get("playwright_version"):
        assert inventory["runtime_version"] == definition["playwright_version"], "Browser version does not match its authored line"
    if "node" in definition["capabilities"]:
        assert inventory["tools"]["node"].startswith("v22."), "The uxor Node line must match CI"
    if "wasm32-unknown-unknown" in definition["capabilities"]:
        assert "wasm32-unknown-unknown" in inventory["rust_targets"]


def validate_size_measurement(measurement):
    assert type(measurement["image_size_bytes"]) is int and measurement["image_size_bytes"] > 0
    assert measurement["size_method"] == "docker-image-inspect-size"
    assert re.fullmatch(r"[A-Za-z0-9._/-]+", measurement["image_store"])
    assert datetime.fromisoformat(measurement["measured_at"].replace("Z", "+00:00")).tzinfo is not None
    assert measurement["evidence"]


def validate_record(record):
    assert record["schema_version"] == 1
    version(record["version"])
    assert re.fullmatch(r"[a-f0-9]{40}", record["source_commit"])
    assert record["lifecycle"] in ("available", "deprecated", "withdrawn")
    if record["lifecycle"] != "available":
        assert record.get("reason") and record.get("replacement") and record.get("lifecycle_date")
    pub = record["publication"]
    assert DIGEST.fullmatch(pub["digest"])
    assert pub["public_pull_verified_at"] and pub["evidence"]
    assert record["verification"]["status"] == "passed"
    assert record["verification"]["surface"] == "github-actions-linux-amd64"
    assert record["definition"]["line_id"] == record["line_id"]
    assert record["definition"]["revision"] == record["version"]
    expected = f"{record['definition']['line']}-v{record['version']}"
    assert pub["exact_tag"] == expected
    assert record["source_tag"] == f"{record['line_id']}/v{record['version']}"
    assert record["platforms"], "No tested platforms"
    assert [p["platform"] for p in record["platforms"]] == record["definition"]["platforms"]
    for platform in record["platforms"]:
        assert DIGEST.fullmatch(platform["digest"])
        inventory = platform["inventory"]
        assert inventory["platform"] == platform["platform"]
        validate_inventory(record["definition"], inventory)
        if "metrics" in platform:
            metrics = platform["metrics"]
            validate_size_measurement(metrics)
            assert metrics["evidence"] == record["verification"]["evidence"]
            assert ("build_seconds" in metrics) == ("cache_source" in metrics)
            for key in ("verification_seconds", "build_seconds"):
                if key == "verification_seconds" or key in metrics:
                    assert type(metrics[key]) in (int, float) and math.isfinite(metrics[key]) and metrics[key] >= 0
            if "cache_source" in metrics:
                assert metrics["cache_source"] in ("disabled", "empty", "restored")
            if "baseline" in metrics:
                baseline = metrics["baseline"]
                validate_size_measurement(baseline)
                assert version(baseline["version"]) < version(record["version"])
                assert baseline["digest_reference"].startswith(pub["repository"] + "@")
                assert DIGEST.fullmatch(baseline["digest_reference"].split("@")[-1])
                assert baseline["size_method"] == metrics["size_method"] and baseline["image_store"] == metrics["image_store"]
    if "assurance" in record:
        from image_assurance import PREDICATE
        import urllib.parse
        summary = record["assurance"]
        expected_url = f"https://github.com/xormania/xorder/releases/download/{urllib.parse.quote(record['source_tag'], safe='')}/assurance.json"
        assert summary["receipt_url"] == expected_url
        assert re.fullmatch(r"[a-f0-9]{64}", summary["receipt_sha256"])
        assert summary["predicate_type"] == PREDICATE
    return record


def records(root=ROOT):
    result = []
    for path in sorted((root / "release-records").rglob("*.json")):
        if path.relative_to(root / "release-records").parts[0] == "artifacts":
            continue
        result.append(validate_record(read(path)))
    identities = [(r["line_id"], r["version"]) for r in result]
    assert len(identities) == len(set(identities)), "Duplicate release identity"
    by_identity = {(r["line_id"], r["version"]): r for r in result}
    for record in result:
        for platform in record["platforms"]:
            baseline = platform.get("metrics", {}).get("baseline")
            if baseline:
                prior = by_identity.get((record["line_id"], baseline["version"]))
                assert prior, "Measurement baseline is absent from the accepted ledger"
                assert baseline["digest_reference"] == prior["publication"]["repository"] + "@" + prior["publication"]["digest"]
                if baseline["evidence"] != record["verification"]["evidence"]:
                    prior_metrics = next(p for p in prior["platforms"] if p["platform"] == platform["platform"]).get("metrics", {})
                    assert all(baseline[key] == prior_metrics.get(key) for key in ("image_size_bytes", "size_method", "image_store", "measured_at", "evidence")), "Reused baseline differs from its verified measurement"
    return result


def catalog(releases):
    entries = []
    for r in sorted(releases, key=lambda r: (r["line_id"], version(r["version"]))):
        pub = r["publication"]
        item = copy.deepcopy(r)
        item["digest_reference"] = f"{pub['repository']}@{pub['digest']}"
        item["exact_reference"] = f"{pub['repository']}:{pub['exact_tag']}"
        item["documentation"] = f"docs/images/{r['line_id'].replace('/', '-')}.md"
        entries.append(item)
    return {"schema_version": 1, "generated_at": max((r["created_at"] for r in releases), default=None), "images": entries}


def select(cat, requirements):
    def compatible(item):
        d = item["definition"]
        platforms = [p["platform"] for p in item["platforms"]]
        return (item["lifecycle"] == "available"
                and d["runtime_line"] == requirements["runtime_line"]
                and (not requirements.get("family") or d["family"] == requirements["family"])
                and requirements.get("platform", "linux/amd64") in platforms
                and set(requirements.get("capabilities", [])) <= set(d["capabilities"])
                and set(requirements.get("extensions", [])) <= set(d["extensions"]))
    matches = [i for i in cat["images"] if compatible(i)]
    if requirements.get("pinned_digest"):
        pinned = [i for i in matches if i["digest_reference"] == requirements["pinned_digest"]]
        if pinned:
            return {"status": "selected", "preserved_pin": True, "image": pinned[0]}
        return {"status": "pin_unverified_or_incompatible", "reason": "The existing pin is absent, withdrawn, or does not meet these requirements. Do not replace it silently."}
    if not matches:
        return {"status": "no_matching_image", "requirements": requirements, "reason": "No verified available release satisfies every runtime, platform, capability, and extension requirement."}
    # Choose the smallest suitable capability profile, then latest revision in that line.
    minimum = min(len(i["definition"]["capabilities"]) for i in matches)
    matches = [i for i in matches if len(i["definition"]["capabilities"]) == minimum]
    chosen = sorted(matches, key=lambda i: (version(i["version"]), i["line_id"]), reverse=True)[0]
    return {"status": "selected", "preserved_pin": False, "image": chosen}


def measurement_markdown(platform):
    metrics = platform.get("metrics")
    if not metrics:
        return ""
    build_time = f"{metrics['build_seconds']:.2f}s" if "build_seconds" in metrics else "Not measured; artifact resumed"
    text = (f"### Release measurements — {platform['platform']}\n\n"
            "| Metric | Measured value |\n| --- | ---: |\n"
            f"| Local image size | {metrics['image_size_bytes']/1024**2:,.1f} MiB ({metrics['image_size_bytes']:,} bytes) |\n"
            f"| Build, cache export and image load | {build_time} |\n"
            f"| Public-artifact behavior and inventory verification | {metrics['verification_seconds']:.2f}s |\n\n"
            f"Size method: `{metrics['size_method']}`; image store: `{metrics['image_store']}`. "
            f"[Measurement evidence]({metrics['evidence']}); {metrics['measured_at']}.\n\n")
    # Budget compressed downloads and unpacked layers together. This is a
    # conservative planning estimate, not a measured download or quota guarantee.
    budget = math.ceil(2 * metrics['image_size_bytes'] / 1024**3)
    text += (f"Plan about **{budget} GiB free for a cold pull**, plus space for project dependencies and test output. "
             "This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, "
             "while the image store, temporary files and sandbox quotas can increase the requirement. "
             "Check free space on the Docker data filesystem; it may differ from the checkout filesystem.\n\n")
    if "cache_source" in metrics:
        text += f"External build cache at start: `{metrics['cache_source']}`. This does not assert that every layer was a cache hit.\n\n"
    baseline = metrics.get("baseline")
    if baseline:
        change = (metrics["image_size_bytes"] / baseline["image_size_bytes"] - 1) * 100
        text += (f"Size baseline: v{baseline['version']}, `{baseline['digest_reference']}`; "
                 f"{baseline['image_size_bytes']/1024**2:,.1f} MiB in the same image store. "
                 f"Change: **{change:+.1f}%**. [Baseline measurement]({baseline['evidence']}); {baseline['measured_at']}.\n\n")
    return text


def metrics_document(latest):
    text = ("# Verified release measurements\n\n"
            "Generated from the verified release ledger. Sizes describe local Docker images, "
            "not registry transfer sizes. Comparisons use the same size method and image store. "
            "Build and verification times describe the recorded publication run, including its "
            "cache and runner conditions; they are not performance guarantees.\n\n")
    measured = [item for _, item in sorted(latest.items()) if any("metrics" in p for p in item["platforms"])]
    if not measured:
        return text + "No verified release measurements yet. PR build metrics remain validation evidence.\n"
    text += "| Line | Revision | Platform | Image size (MiB) | Baseline size (MiB) | Size change | Build (s) | Public verification (s) |\n| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |\n"
    for item in measured:
        for platform in item["platforms"]:
            metrics = platform.get("metrics")
            if not metrics:
                continue
            baseline = metrics.get("baseline")
            previous = f"{baseline['image_size_bytes']/1024**2:,.1f} (v{baseline['version']})" if baseline else "—"
            change = f"{(metrics['image_size_bytes']/baseline['image_size_bytes']-1)*100:+.1f}%" if baseline else "—"
            build_time = f"{metrics['build_seconds']:.2f}" if "build_seconds" in metrics else "Not measured"
            text += (f"| [{item['line_id']}](images/{item['line_id'].replace('/', '-')}.md) | {item['version']} | "
                     f"{platform['platform']} | {metrics['image_size_bytes']/1024**2:,.1f} | {previous} | {change} | "
                     f"{build_time} | {metrics['verification_seconds']:.2f} |\n")
    return text + "\nImage/release pages retain exact bytes, artifact identities, measurement methods, cache inputs and evidence links. Older records without measurements remain valid and are omitted from this table.\n"


def generated(root=ROOT):
    defs = definitions(root)
    releases = records(root)
    cat = catalog(releases)
    latest = {}
    for item in cat["images"]:
        if item["lifecycle"] == "available":
            latest[item["line_id"]] = item
    rows = ["| Line | Revision | Verified platform | Exact reference |", "| --- | --- | --- | --- |"]
    for line, item in sorted(latest.items()):
        rows.append(f"| [{line}]({item['documentation']}) | {item['version']} | {', '.join(p['platform'] for p in item['platforms'])} | `{item['exact_reference']}` |")
    table = "\n".join(rows) if latest else "No verified public releases yet. Definitions are build inputs, not available images."
    readme = (root / "README.md").read_text()
    readme = re.sub(r"(?s)(<!-- catalog:start -->\n).*?(\n<!-- catalog:end -->)", lambda m: m[1] + table + m[2], readme)
    outputs = {root / "catalog.json": encoded(cat), root / "README.md": readme,
               root / "docs" / "metrics.md": metrics_document(latest)}
    for line, d in defs.items():
        item = latest.get(line)
        if item:
            d = item["definition"]
        text = f"# {line}\n\n{d['purpose']}\n\n"
        if item:
            text += f"Available revision: **{item['version']}**. Pin:\n\n```text\n{item['digest_reference']}\n```\n\n"
            text += f"[Verification evidence]({item['verification']['evidence']}); {item['verification']['completed_at']}.\n\n"
            for platform in item["platforms"]:
                inv = platform["inventory"]
                text += f"## Measured inventory — {platform['platform']}\n\nRuntime: {inv['runtime_version']}; OS: {inv['os']['PRETTY_NAME']}.\n\n"
                text += "| Tool | Version |\n| --- | --- |\n" + "\n".join(f"| {k} | {v.replace('|', '/')} |" for k, v in sorted(inv["tools"].items())) + "\n\n"
                if inv["extensions"]:
                    text += "Extensions: " + ", ".join(f"`{e}`" for e in sorted(inv["extensions"])) + ".\n\n"
                text += measurement_markdown(platform)
            text += f"[Release notes](../releases/{line.replace('/', '-')}-v{item['version']}.md).\n\n"
        else:
            text += "**Not available:** no verified public release. The following capabilities describe the intended profile.\n\n"
        text += "Capabilities: " + ", ".join(f"`{c}`" for c in d["capabilities"]) + ".\n\n"
        text += "Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.\n\n"
        if d["family"] == "php-toolkit":
            text += "[Toolkit validation and fresh-app recipe](../php-toolkit.md) · "
        if d["family"] == "php-serena":
            text += "[Serena MCP and Symfony recipe](../serena.md) · "
        text += "[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)\n\n"
        text += "## Limitations\n\n" + "\n".join(f"- {x}" for x in d["limitations"]) + "\n"
        outputs[root / "docs" / "images" / (line.replace("/", "-") + ".md")] = text
    for item in cat["images"]:
        d = item["definition"]
        text = f"# {item['line_id']} v{item['version']}\n\n" + "\n".join(f"- {c}" for c in d["changes"]) + "\n\n"
        text += f"Migration: {d['migration']}\n\nSource: `{item['source_commit']}` (`{item['source_tag']}`).\n\nArtifact: `{item['digest_reference']}`.\n\n"
        text += f"Base/parent: `{item['resolved_base']}`.\n\n[Verification]({item['verification']['evidence']}).\n\n"
        for platform in item["platforms"]:
            text += measurement_markdown(platform)
        text += "The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.\n"
        outputs[root / "docs" / "releases" / f"{item['line_id'].replace('/', '-')}-v{item['version']}.md"] = text
    from xorder.model import availability_table, catalog as resource_catalog, generated as generated_resources
    outputs.update(generated_resources(root, image_records=releases))
    outputs[root / "README.md"] = re.sub(
        r"(?s)(<!-- resources:start -->\n).*?(\n<!-- resources:end -->)",
        lambda match: match[1] + availability_table(resource_catalog(root, image_records=releases)) + match[2],
        outputs[root / "README.md"])
    return outputs


def affected(changed, defs, previous_tools=None):
    # Preserve the existing root-list interface; CI uses the precise plan below.
    selected = affected_lines(changed, defs, ROOT, previous_tools)
    return sorted({root_line(line, defs) for line in selected})


def fingerprint(d, root=ROOT):
    modern = d.get("input_fingerprint_version", 1) == 2
    paths = input_files(d["family"], root, d["line"]) if modern else list((root / "images" / d["family"]).glob("*")) + list((root / "images" / "shared").glob("*"))
    if d["family"] == "php-toolkit" and not modern:
        paths += [root / "examples/php-toolkit/validator" / name for name in ("composer.json", "composer.lock")]
        paths += list((root / "examples/php-toolkit/symfony-7.4").rglob("*"))
    h = hashlib.sha256(encoded(d).encode())
    tools = read(root / "images" / "tools.json")
    keys = TOOL_KEYS.get(d["family"], ()) if modern else {"php-dev": ("composer", "redis_version", "xdebug_version", "pcov_version", "symfony"),
            "php-frankenphp": ("composer", "redis_version", "xdebug_version", "pcov_version", "symfony", "apcu_version"),
            "uxor-dev": ("node", "tailwind"),
            "python-dev": ("uv",)}.get(d["family"], ())
    h.update(encoded({key: tools[key] for key in keys}).encode())
    for path in sorted(paths):
        if path.is_file() and path.name != "definition.json":
            h.update(str(path.relative_to(root)).encode())
            if modern:
                h.update(b"executable" if path.stat().st_mode & 0o111 else b"regular")
            h.update(path.read_bytes())
    return h.hexdigest()


def cache_key(line, defs):
    # One CI job owns the PHP parent and browser caches. Neither source commit
    # nor unrelated tool pins belong in their immutable Actions cache key.
    peers = []
    def visit(item):
        peers.append(item)
        for child in children(item, defs):
            visit(child)
    visit(line)
    return hashlib.sha256("".join(fingerprint(defs[peer]) for peer in peers).encode()).hexdigest()


def pending_releases(defs, accepted):
    """Skip accepted inputs, but retain missing browser peers and guard failures."""
    current = {(r["line_id"], r["version"]): r for r in accepted}
    pending = set()
    for line, d in defs.items():
        fp = fingerprint(d)
        parent_line = d["base"].get("parent")
        if parent_line:
            parent = current.get((parent_line, defs[parent_line]["revision"]))
            if not parent:
                pending.add(root_line(line, defs))
                continue
            parent_ref = parent["publication"]["repository"] + "@" + parent["publication"]["digest"]
            fp = hashlib.sha256((fp + parent_ref).encode()).hexdigest()
        prior = current.get((line, d["revision"]))
        if not prior or prior["input_fingerprint"] != fp:
            pending.add(root_line(line, defs))
    return sorted(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("check")
    s = sub.add_parser("select"); s.add_argument("requirements"); s.add_argument("--catalog", default=str(ROOT / "catalog.json"))
    for command in ("affected", "validation-matrix"):
        a = sub.add_parser(command)
        a.add_argument("--base")
        a.add_argument("--all", action="store_true")
    sub.add_parser("cache-key").add_argument("line")
    sub.add_parser("release-matrix")
    sub.add_parser("definitions")
    args = parser.parse_args()
    if args.command in ("generate", "check"):
        if args.command == "check":
            validate_schemas()
        errors = []
        for path, content in generated().items():
            if args.command == "generate":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            elif not path.exists() or path.read_text() != content:
                errors.append(str(path.relative_to(ROOT)))
        if errors:
            raise SystemExit("Stale generated files: " + ", ".join(errors))
    elif args.command == "definitions":
        print(encoded(definitions()), end="")
    elif args.command == "select":
        result = select(read(args.catalog), read(args.requirements))
        print(encoded(result), end="")
        if result["status"] != "selected":
            raise SystemExit(2)
    elif args.command in ("affected", "validation-matrix"):
        defs = definitions()
        if args.all or not args.base:
            selected = sorted(defs)
        else:
            changed = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", args.base, "HEAD"], cwd=ROOT, text=True).splitlines()
            previous_tools = json.loads(subprocess.check_output(["git", "show", f"{args.base}:images/tools.json"], cwd=ROOT, text=True))
            previous_definitions = {}
            for path in changed:
                if path.startswith("images/") and path.endswith("/definition.json"):
                    previous = subprocess.run(["git", "show", f"{args.base}:{path}"], cwd=ROOT, capture_output=True, text=True)
                    if previous.returncode == 0:
                        previous_definitions[path] = json.loads(previous.stdout)
            selected = affected_lines(changed, defs, ROOT, previous_tools, previous_definitions)
        result = validation_matrix(selected, defs) if args.command == "validation-matrix" else {"line": sorted({root_line(line, defs) for line in selected})}
        print(json.dumps(result))
    elif args.command == "cache-key":
        print(cache_key(args.line, definitions()))
    elif args.command == "release-matrix":
        print(json.dumps({"line": pending_releases(definitions(), records())}))


if __name__ == "__main__":
    main()
