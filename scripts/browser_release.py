#!/usr/bin/env python3
"""Stage browsers with credentials; verify consumers on a separate anonymous runner."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

from build import build, cache_source, image_facts, verify
from library import ROOT, definitions, encoded, fingerprint, read, records, record_matches_inputs, reusable_record, validate_inventory
from registry import resolve


def fixture_hash(line):
    folder = ROOT / "tests/fixtures/playwright"
    path = folder / "consumers" / (line.split("/", 1)[1] + ".json")
    if not path.exists():
        path = folder / "consumer.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_parity_application(line):
    """Publication always resolves the fixture against accepted public records."""
    from playwright_fixture import inputs
    fixture = ROOT / "tests/fixtures/playwright/consumers" / (line.split("/", 1)[1] + ".json")
    return inputs(read(fixture), read(ROOT / "catalog-v2.json"))


def stage(line, source, destination):
    from release import release_asset, reserve_candidate
    from artifact_identity import build_key
    definition = definitions()[line]
    if definition["family"] != "playwright-browser":
        raise ValueError("Only browser images use staged parity verification")
    # A direct stage invocation must enforce the same allocation guard as
    # final publication, before reserving or building a redundant candidate.
    reusable_record(definition, records())
    repository = "ghcr.io/xormania/playwright-browser"
    fp = fingerprint(definition)
    measurements = {}
    with tempfile.TemporaryDirectory() as folder:
        prior = release_asset(f"{line}/v{definition['revision']}", Path(folder))
    if prior:
        if not record_matches_inputs(prior, definition):
            raise ValueError("Durable browser release has different inputs")
        artifact = repository + "@" + prior["publication"]["digest"]
        definition, source, fp = prior['definition'], prior['source_commit'], prior['input_fingerprint']
    else:
        if resolve(f"{repository}:{definition['line']}-v{definition['revision']}", authenticated=True):
            raise ValueError("Exact browser tag exists without durable evidence; recover it")
        attempt = reserve_candidate(definition, source, None, destination.parent / 'attempt', fp)
        definition, source, fp = attempt['definition'], attempt['source_commit'], attempt['input_fingerprint']
        candidate = attempt['candidate']
        existing = resolve(candidate, authenticated=True)
        if existing:
            artifact = repository + "@" + existing["digest"]
            subprocess.run(["docker", "pull", artifact], check=True)
            labels = image_facts(artifact)["Config"]["Labels"]
            if labels.get("org.opencontainers.image.revision") != source or labels.get("org.opencontainers.image.version") != definition["revision"]:
                raise ValueError("Candidate labels differ from the staged release")
        else:
            measurements["cache_source"] = cache_source(line.replace("/", "-"))
            started = time.monotonic()
            build(line, candidate, source, cache=line.replace("/", "-"))
            measurements["build_seconds"] = round(time.monotonic() - started, 2)
            subprocess.run(["docker", "push", candidate], check=True)
            existing = resolve(candidate, authenticated=True)
            if not existing:
                raise ValueError("Staged browser candidate was not published")
            artifact = repository + "@" + existing["digest"]
    if not resolve(artifact):
        raise ValueError("Staged browser must be publicly pullable before anonymous verification")
    value = {"line": line, "source": source, "version": definition["revision"], "artifact": artifact,
             "input_fingerprint": fp, "build_key_version": 1,
             "build_key": build_key(definition, root=ROOT, tools=attempt['tools']) if not prior else
                          build_key(definition, root=ROOT, tools=prior['tools']),
             "fixture_sha256": fixture_hash(line), **measurements}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(encoded(value))
    return value


def verify_candidate(candidate, destination):
    from release import now
    value = read(candidate)
    definition = definitions()[value["line"]]
    from artifact_identity import build_key
    matched_inputs = (value.get('input_fingerprint') == fingerprint(definition) or
                      value.get('build_key_version') == 1 and value.get('build_key') == build_key(definition, root=ROOT))
    if (definition["family"] != "playwright-browser" or value["version"] != definition["revision"]
            or not matched_inputs
            or value["fixture_sha256"] != fixture_hash(value["line"])):
        raise ValueError("Staged browser inputs differ from the verifying checkout")
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        raise ValueError("Consumer parity must run without GitHub publication credentials")
    if "XORDER_PARITY_LOCAL_APPLICATION" in os.environ:
        raise ValueError("Publication parity requires an accepted application resource; local overrides are source-validation only")
    public_parity_application(value["line"])
    subprocess.run(["docker", "pull", value["artifact"]], check=True)
    inventory = destination.with_suffix(".inventory.json")
    started = time.monotonic()
    verify(value["line"], value["artifact"], inventory)
    value.update(status="passed", inventory=read(inventory), completed_at=now(),
                 verification_seconds=round(time.monotonic() - started, 2))
    destination.write_text(encoded(value))
    return value


def accepted_evidence(line, source, artifact, path, *, definition=None, input_fingerprint=None):
    definition = definition or definitions()[line]
    value = read(path)
    expected = {"line": line, "source": source, "version": definition["revision"], "artifact": artifact,
                "input_fingerprint": input_fingerprint or fingerprint(definition), "fixture_sha256": fixture_hash(line), "status": "passed"}
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("Browser parity evidence does not match the exact publication inputs")
    public_parity_application(line)
    seconds = value["verification_seconds"]
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid browser verification duration")
    validate_inventory(definition, value["inventory"])
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("stage")
    prepare.add_argument("line")
    prepare.add_argument("--source", default=os.environ.get("GITHUB_SHA"))
    prepare.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("candidate", type=Path)
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "stage":
        stage(args.line, args.source, args.output)
    else:
        verify_candidate(args.candidate, args.output)
