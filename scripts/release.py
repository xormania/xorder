#!/usr/bin/env python3
"""Build/test/publish once, persist a verified record, and stage docs through a PR."""
import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from build import build, cache_source, image_measurements, pinned, verify
from library import ROOT, children, definitions, encoded, fingerprint, read, records, validate_record, version
from registry import resolve


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def exact_guard(current, intended):
    if current is not None and current != intended:
        raise RuntimeError(f"Refusing exact-tag reassignment: {current} != {intended}")


def alias_eligible(candidate, accepted):
    peers = [r for r in accepted if r["line_id"] == candidate["line_id"] and r["lifecycle"] == "available" and version(r["version"])[0] == version(candidate["version"])[0]]
    return bool(peers) and version(candidate["version"]) == max(version(r["version"]) for r in peers)


def release_asset(tag, destination):
    # --clobber is intentionally absent; assets define the durable release identity.
    result = subprocess.run(["gh", "release", "download", tag, "--pattern", "record.json", "--dir", str(destination)], capture_output=True, text=True)
    if result.returncode == 0:
        return validate_record(read(destination / "record.json"))
    # Inspect via the API so a missing asset is distinguished from an API failure.
    releases = json.loads(gh("api", "--paginate", "--slurp", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases"))
    matching = [r for page in releases for r in page if r["tag_name"] == tag]
    if matching and any(a["name"] == "record.json" for a in matching[0]["assets"]):
        raise RuntimeError("A durable release record exists but could not be downloaded")
    return None


def release_measurements(line, revision, artifact, accepted, evidence, measured_at, verification_seconds,
                         anonymous_env, build_seconds=None, build_cache=None):
    measurements = {**image_measurements(artifact), "measured_at": measured_at, "evidence": evidence,
                    "verification_seconds": verification_seconds}
    if build_seconds is not None:
        measurements.update(build_seconds=build_seconds, cache_source=build_cache)
    peers = [r for r in accepted if r["line_id"] == line and r["lifecycle"] == "available"
             and version(r["version"]) < version(revision)]
    if peers:
        previous = max(peers, key=lambda r: version(r["version"]))
        prior_metrics = previous["platforms"][0].get("metrics", {})
        reference = previous["publication"]["repository"] + "@" + previous["publication"]["digest"]
        if (prior_metrics.get("size_method"), prior_metrics.get("image_store")) == (measurements["size_method"], measurements["image_store"]):
            baseline = {key: prior_metrics[key] for key in ("image_size_bytes", "size_method", "image_store", "measured_at", "evidence")}
        else:
            # Older records have no size measurements. Measure their published
            # digest in this same store, without rewriting the durable record.
            run("docker", "pull", "--platform", "linux/amd64", reference, env=anonymous_env)
            baseline = {**image_measurements(reference), "measured_at": now(), "evidence": evidence}
        measurements["baseline"] = {"version": previous["version"], "digest_reference": reference, **baseline}
    return measurements


def stage_assurance(source_tag, source, artifact, evidence, destination, *, release_target=None):
    """Persist evidence before its commit record; content-named assets survive retries."""
    from image_assurance import create, receipt_link, validate_receipt, verify_local
    target = release_target if release_target is not None else source
    releases = json.loads(gh("api", "--paginate", "--slurp", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases"))
    matching = [release for page in releases for release in page if release["tag_name"] == source_tag]
    if not matching:
        run("gh", "release", "create", source_tag, "--target", target, "--draft", "--title", source_tag,
            "--notes", "Exact image candidate is undergoing scan, signing, and public verification.")
        assets = {}
    else:
        release = matching[0]
        if release["target_commitish"] != target:
            raise RuntimeError("Assurance Release already names another target commit")
        assets = {asset["name"]: asset for asset in release["assets"]}
    destination.mkdir(parents=True, exist_ok=True)
    if "assurance.json" in assets:
        run("gh", "release", "download", source_tag, "--pattern", "assurance.json", "--dir", str(destination))
        receipt = validate_receipt(read(destination / "assurance.json"), artifact, source)
        if release_target is not None and receipt.get("assurance_workflow_commit") != release_target:
            raise RuntimeError("Assurance receipt producer differs from its evidence Release target")
        for facts in receipt["files"].values():
            run("gh", "release", "download", source_tag, "--pattern", facts["filename"], "--dir", str(destination))
        verify_local(receipt, destination)
    else:
        receipt = create(artifact, source, evidence, destination)
        if release_target is not None and receipt.get("assurance_workflow_commit") != release_target:
            raise RuntimeError("Assurance receipt producer differs from its evidence Release target")
        # A scan rerun may have newer database/time inputs. Content-addressed
        # filenames avoid overwriting partial earlier uploads; receipt uploads last.
        for facts in receipt["files"].values():
            asset = assets.get(facts["filename"])
            if asset:
                if asset.get("digest") != "sha256:" + facts["sha256"]:
                    raise RuntimeError("Existing assurance asset checksum differs")
            else:
                run("gh", "release", "upload", source_tag, str(destination / facts["filename"]))
        run("gh", "release", "upload", source_tag, str(destination / "assurance.json"))
    return receipt_link(receipt, source_tag, destination)


def publish(line, source, destination, parent=None, browser_evidence=None):
    d = definitions()[line]
    accepted = records()
    prior = [r for r in accepted if r["line_id"] == line and r["version"] == d["revision"]]
    fp = fingerprint(d)
    if parent:
        import hashlib
        fp = hashlib.sha256((fp + parent).encode()).hexdigest()
    if prior:
        if prior[0]["input_fingerprint"] != fp:
            raise RuntimeError(f"{line} changed without a new revision. Bump {d['revision']}.")
        return prior[0]
    source_tag = f"{line}/v{d['revision']}"
    destination.mkdir(parents=True, exist_ok=True)
    record = release_asset(source_tag, destination)
    if record:
        if record["input_fingerprint"] != fp:
            raise RuntimeError("Interrupted release has different inputs; use a new image revision")
        remote = resolve(record["publication"]["repository"] + "@" + record["publication"]["digest"])
        if not remote or remote["digest"] != record["publication"]["digest"]:
            raise RuntimeError("Recorded artifact is no longer publicly pullable")
        promote_exact(record)
        finalize_release(record)
        if record.get("assurance"):
            from image_assurance import verify_record
            verify_record(record, destination / "assurance")
        return record
    repository = "ghcr.io/xormania/" + d["family"]
    candidate = f"{repository}:{d['line']}-candidate-v{d['revision']}-{source}"
    # An existing exact tag without a durable record is ambiguous; never rebuild it.
    existing_exact = resolve(f"{repository}:{d['line']}-v{d['revision']}", authenticated=True)
    if existing_exact:
        raise RuntimeError("Exact tag exists without a durable record. Recover its record; do not rebuild.")
    existing = resolve(candidate, authenticated=True)
    inventory_path = destination / "inventory.json"
    resolved_base = parent or pinned(d["base"])
    browser_proof = None
    def verify_candidate(artifact):
        nonlocal browser_proof
        if d["family"] != "playwright-browser":
            verify(line, artifact, inventory_path)
            return
        if browser_evidence is None:
            raise ValueError("Browser publication requires anonymous parity evidence")
        from browser_release import accepted_evidence
        browser_proof = accepted_evidence(line, source, artifact, browser_evidence)
        inventory_path.write_text(encoded(browser_proof["inventory"]))
    build_seconds = build_cache = None
    if existing:
        artifact = repository + "@" + existing["digest"]
        run("docker", "pull", artifact)
        labels = json.loads(subprocess.check_output(["docker", "inspect", artifact, "--format", "{{json .Config.Labels}}"], text=True))
        if labels.get("org.opencontainers.image.revision") != source or labels.get("org.opencontainers.image.version") != d["revision"]:
            raise RuntimeError("Candidate metadata does not match this release")
        verify_candidate(artifact)
    else:
        if d["family"] == "playwright-browser":
            raise ValueError("Stage and anonymously verify the browser candidate before publication")
        build_cache = cache_source(line.replace("/", "-"))
        build_start = time.monotonic()
        build(line, candidate, source, parent, cache=line.replace("/", "-"))
        build_seconds = round(time.monotonic() - build_start, 2)
        verify_candidate(candidate)
        run("docker", "push", candidate)
    published = resolve(candidate, authenticated=True)
    if not published:
        raise RuntimeError("Pushed candidate not found")
    digest = published["digest"]
    artifact = repository + "@" + digest
    # This lookup must work without any credential. New GHCR packages are private by default.
    try:
        public = resolve(artifact)
    except Exception as error:
        raise RuntimeError(f"Make GHCR package {d['family']} public, then rerun this workflow to reuse the candidate") from error
    if not public or public["digest"] != digest:
        raise RuntimeError("Anonymous registry resolution failed")
    evidence = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    with tempfile.TemporaryDirectory() as config:
        env = dict(os.environ, DOCKER_CONFIG=config)
        run("docker", "pull", "--platform", "linux/amd64", artifact, env=env)
        verification_start = time.monotonic()
        verify_candidate(artifact)
        verification_seconds = browser_proof["verification_seconds"] if browser_proof else round(time.monotonic() - verification_start, 2)
        if browser_proof:
            build_seconds, build_cache = browser_proof.get("build_seconds"), browser_proof.get("cache_source")
        measurements = release_measurements(line, d["revision"], artifact, accepted, evidence, now(),
                                            verification_seconds, env, build_seconds, build_cache)
    assurance = stage_assurance(source_tag, source, artifact, evidence, destination / "assurance")
    date = now()
    record = {"schema_version": 1, "line_id": line, "version": d["revision"], "source_commit": source, "source_tag": source_tag,
              "created_at": date, "definition": d, "tools": read(ROOT / "images/tools.json"), "resolved_base": resolved_base,
              "input_fingerprint": fp, "lifecycle": "available", "assurance": assurance,
              "platforms": [{"platform": "linux/amd64", "digest": published["platforms"].get("linux/amd64", digest),
                             "inventory": read(inventory_path), "metrics": measurements}],
              "publication": {"repository": repository, "digest": digest, "exact_tag": f"{d['line']}-v{d['revision']}", "public_pull_verified_at": date, "evidence": evidence},
              "verification": {"status": "passed", "surface": "github-actions-linux-amd64",
                               "completed_at": browser_proof["completed_at"] if browser_proof else date, "evidence": evidence}}
    validate_record(record)
    (destination / "record.json").write_text(encoded(record))
    # Persist before exact promotion. A retry recovers this artifact, never rebuilds it.
    existing_release = json.loads(gh("api", "--paginate", "--slurp", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases"))
    if not any(r["tag_name"] == source_tag for page in existing_release for r in page):
        run("gh", "release", "create", source_tag, "--target", source, "--draft", "--title", source_tag,
            "--notes", "Verified artifact recorded. Exact promotion and catalog writeback are in progress.")
    tagged = subprocess.check_output(["git", "ls-remote", "--tags", "origin", f"refs/tags/{source_tag}"], text=True).split()
    if tagged and tagged[0] != source:
        raise RuntimeError("Source tag already names a different commit")
    run("gh", "release", "upload", source_tag, str(destination / "record.json"), str(inventory_path))
    promote_exact(record)
    finalize_release(record)
    from image_assurance import verify_record
    verify_record(record, destination / "public-assurance")
    return record


def promote_exact(record):
    p = record["publication"]
    target = p["repository"] + ":" + p["exact_tag"]
    current = resolve(target, authenticated=True)
    exact_guard(current["digest"] if current else None, p["digest"])
    if not current:
        run("docker", "buildx", "imagetools", "create", "--prefer-index=false", "--tag", target, p["repository"] + "@" + p["digest"])
    verified = resolve(target)
    if not verified or verified["digest"] != p["digest"]:
        raise RuntimeError("Exact tag does not identify the tested public artifact")


def finalize_release(record):
    d = record["definition"]
    notes = "\n".join("- " + x for x in d["changes"])
    notes += f"\n\nMigration: {d['migration']}\n\nDigest: `{record['publication']['repository']}@{record['publication']['digest']}`"
    notes += f"\n\n[Verification]({record['verification']['evidence']}). Catalog update is staged through a protected-branch PR; the compatibility alias moves only after that PR lands."
    run("gh", "release", "edit", record["source_tag"], "--draft=false", "--notes", notes)


def alias_plan(accepted):
    """List every alias before preflight so failures retain the full report."""
    groups = {}
    plan = []
    for r in accepted:
        p = r["publication"]
        alias = f"{p['repository']}:{r['definition']['line']}-v{version(r['version'])[0]}"
        groups.setdefault(alias, []).append(r)
    for alias, peers in groups.items():
        candidate = next((r for r in peers if alias_eligible(r, peers)), None)
        item = {"alias": alias, "digest": None, "status": "pending"}
        if candidate:
            p = candidate["publication"]
            item.update(exact=p["repository"] + ":" + p["exact_tag"],
                        reference=p["repository"] + "@" + p["digest"], digest=p["digest"])
        plan.append(item)
    return plan


def alias_preflight(plan):
    """Resolve all targets without writes, retaining each failed or pending entry."""
    # A withdrawal must not leave a stale recommendation silently successful,
    # or delete a shared exact digest. Check these groups before other lookups.
    blocked = []
    for item in plan:
        if "exact" in item:
            continue
        try:
            current = resolve(item["alias"], authenticated=True)
        except Exception as error:
            item.update(status="failed", error=str(error))
            raise
        if current is not None:
            item.update(status="failed", error="No available replacement for existing alias")
            blocked.append(item["alias"])
        else:
            item.update(status="unchanged", error="Retired alias is already absent")
    if blocked:
        raise RuntimeError("No available replacement for existing aliases: " + ", ".join(blocked)
                           + ". Restore a verified available release or retire these alias tags while preserving exact artifacts, then rerun.")
    for item in plan:
        if "exact" not in item:
            continue
        try:
            remote = resolve(item["exact"])
            if not remote or remote["digest"] != item["digest"]:
                raise RuntimeError(f"Accepted exact tag changed or is unavailable: {item['exact']}")
            current = resolve(item["alias"])
            item["status"] = "unchanged" if current and current["digest"] == item["digest"] else "pending"
        except Exception as error:
            item.update(status="failed", error=str(error))
            raise


def alias_report(plan):
    text = "## Alias promotion\n\n| Alias | Result | Target digest | Details |\n| --- | --- | --- | --- |\n"
    for item in plan:
        details = " ".join(item.get("error", "").splitlines()).replace("|", "&#124;")
        text += f"| `{item['alias']}` | {item['status']} | `{item['digest'] or '—'}` | {details} |\n"
    if not plan:
        text += "\nNo alias entries were planned.\n"
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write(text)


def aliases():
    # Fetch the latest accepted ledger when this queued workflow starts.
    run("git", "fetch", "origin", "master")
    run("git", "checkout", "--detach", "origin/master")
    plan = []
    try:
        plan = alias_plan(records())
        alias_preflight(plan)
        for item in plan:
            if item["status"] == "unchanged":
                continue
            try:
                run("docker", "buildx", "imagetools", "create", "--prefer-index=false",
                    "--tag", item["alias"], item["reference"])
                remote = resolve(item["alias"])
                if not remote or remote["digest"] != item["digest"]:
                    raise RuntimeError(f"Alias promotion verification failed: {item['alias']}")
                item["status"] = "updated"
            except Exception as error:
                item.update(status="failed", error=str(error))
                raise
    finally:
        alias_report(plan)


def publish_tree(line, source, parent=None, browser_evidence=None):
    output = ROOT / "out" / line.replace("/", "-")
    record = publish(line, source, output, parent, browser_evidence)
    output.mkdir(parents=True, exist_ok=True)
    (output / "record.json").write_text(encoded(record))
    reference = record["publication"]["repository"] + "@" + record["publication"]["digest"]
    for child in children(line, definitions()):
        publish_tree(child, source, reference)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("line", nargs="?"); parser.add_argument("--source", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--aliases", action="store_true")
    parser.add_argument("--browser-evidence", type=Path)
    args = parser.parse_args()
    if args.aliases:
        aliases()
    else:
        publish_tree(args.line, args.source, browser_evidence=args.browser_evidence)
