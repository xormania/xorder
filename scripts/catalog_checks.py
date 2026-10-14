#!/usr/bin/env python3
"""Check image-ledger additions against public durable release evidence."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from library import ROOT, DIGEST, read, validate_record
from registry import resolve
from xorder.transport import download


LIFECYCLE_FIELDS = {"lifecycle", "reason", "replacement", "lifecycle_date"}


def retirement_records(base, root=ROOT):
    """Authorize explicit removals by exact historical bytes, never rename facts."""
    retired = {}
    folder = root / "retired-records"
    for path in sorted(folder.glob("*.json")):
        relative = path.relative_to(root).as_posix()
        manifest = read(path)
        if (set(manifest) != {"schema_version", "history_commit", "reason", "records"}
                or manifest["schema_version"] != 1 or not isinstance(manifest["reason"], str)
                or not manifest["reason"].strip() or not isinstance(manifest["records"], list)
                or not manifest["records"]):
            raise RuntimeError(f"Invalid image retirement declaration: {relative}")
        history = manifest["history_commit"]
        if not isinstance(history, str) or not re.fullmatch(r"[a-f0-9]{40}", history):
            raise RuntimeError(f"Invalid image retirement history: {relative}")
        if subprocess.run(["git", "merge-base", "--is-ancestor", history, base or "HEAD"],
                          cwd=root, capture_output=True).returncode:
            raise RuntimeError(f"Image retirement history is not an accepted ancestor: {relative}")
        previous = subprocess.run(["git", "show", f"{base}:{relative}"], cwd=root,
                                  capture_output=True) if base else None
        if previous and previous.returncode == 0 and previous.stdout != path.read_bytes():
            raise RuntimeError(f"Image retirement declarations are immutable: {relative}")
        historical_paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", history, "--", "release-records"],
            cwd=root, text=True).splitlines()
        historical = {}
        for old_path in historical_paths:
            parts = Path(old_path).parts
            if len(parts) != 4 or parts[1] == "artifacts" or not old_path.endswith(".json"):
                continue
            payload = subprocess.check_output(["git", "show", f"{history}:{old_path}"], cwd=root)
            historical[hashlib.sha256(payload).hexdigest()] = (old_path, payload)
        seen = set()
        for entry in manifest["records"]:
            if (not isinstance(entry, dict) or set(entry) != {"sha256", "source_commit"}
                    or not isinstance(entry["sha256"], str)
                    or entry["sha256"] in seen or entry["sha256"] not in historical):
                raise RuntimeError(f"Image retirement requires unique exact historical record hashes: {relative}")
            seen.add(entry["sha256"])
            old_path, payload = historical[entry["sha256"]]
            record = validate_record(json.loads(payload))
            if entry["source_commit"] != record["source_commit"]:
                raise RuntimeError(f"Image retirement source differs from historical evidence: {relative}")
            if (root / old_path).exists():
                raise RuntimeError(f"Retired image evidence remains in the live ledger: {old_path}")
            if old_path in retired:
                raise RuntimeError(f"Duplicate image retirement declaration: {old_path}")
            if base and (previous is None or previous.returncode):
                accepted = subprocess.run(["git", "show", f"{base}:{old_path}"], cwd=root,
                                          capture_output=True)
                if accepted.returncode or accepted.stdout != payload:
                    raise RuntimeError(f"New retirement must remove exact accepted base evidence: {old_path}")
            retired[old_path] = payload
    if base:
        deleted = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=D", "--no-renames", base, "HEAD", "--", "retired-records"],
            cwd=root, text=True).splitlines()
        if deleted:
            raise RuntimeError("Image retirement declarations cannot be deleted")
    return retired


def immutable_record(record):
    return {key: value for key, value in record.items() if key not in LIFECYCLE_FIELDS}


def github_json(repository, endpoint):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "xorder-catalog-check",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(f"https://api.github.com/repos/{repository}/{endpoint}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def public_release(record, repository):
    tag = urllib.parse.quote(record["source_tag"], safe="")
    return github_json(repository, "releases/tags/" + tag)


def verify_image_record(record, repository, *, require_assurance=True):
    if require_assurance and not record.get("assurance"):
        raise RuntimeError(f"New image release record requires verified assurance: {record['line_id']} v{record['version']}")
    validate_record(record)
    release = public_release(record, repository)
    if (release["draft"] or release["tag_name"] != record["source_tag"]
            or release["target_commitish"] != record["source_commit"]):
        raise RuntimeError(f"Source Release is unfinished or differs: {record['source_tag']}")
    assets = [item for item in release["assets"] if item["name"] == "record.json"]
    if len(assets) != 1 or not DIGEST.fullmatch(assets[0].get("digest") or ""):
        raise RuntimeError(f"Missing durable record or asset checksum: {record['source_tag']}")
    with tempfile.TemporaryDirectory(prefix="xorder-catalog-check-") as temporary:
        path = Path(temporary) / "record.json"
        # Transport sends no GitHub credentials, including on redirects.
        download(assets[0]["browser_download_url"], path, assets[0]["digest"].split(":", 1)[1])
        durable = validate_record(read(path))
    if immutable_record(durable) != immutable_record(record):
        raise RuntimeError(f"Image record differs from its durable Release asset: {record['line_id']} v{record['version']}")
    publication = record["publication"]
    exact = publication["repository"] + ":" + publication["exact_tag"]
    remote = resolve(exact)
    if not remote or remote["digest"] != publication["digest"]:
        raise RuntimeError(f"Public exact image digest differs or is unavailable: {exact}")
    for platform in record["platforms"]:
        actual = remote["platforms"].get(platform["platform"]) if remote["platforms"] else remote["digest"]
        if actual != platform["digest"]:
            raise RuntimeError(f"Public platform digest differs: {exact} ({platform['platform']})")
    if record.get("assurance"):
        from image_assurance import verify_record
        with tempfile.TemporaryDirectory(prefix="xorder-catalog-assurance-") as temporary:
            verify_record(record, Path(temporary))
    return record


def changed_image_records(base, root=ROOT):
    if base is not None:
        resolved = subprocess.run(["git", "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"],
                                  cwd=root, capture_output=True, text=True)
        if not base or resolved.returncode:
            raise RuntimeError("Image additions require a known base commit")
        base = resolved.stdout.strip()
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=root,
                          capture_output=True).returncode:
            raise RuntimeError("Image additions require a base commit that is an ancestor of HEAD")
        paths = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", base, "HEAD", "--", "release-records"],
            cwd=root, text=True).splitlines()
    else:
        paths = [str(path.relative_to(root)) for path in (root / "release-records").rglob("*.json")]
    retired = retirement_records(base, root)
    for relative in sorted(paths):
        path = Path(relative)
        if path.parts[1] == "artifacts" or path.suffix != ".json":
            continue
        if base and not (root / path).is_file():
            prior = subprocess.run(["git", "show", f"{base}:{path.as_posix()}"], cwd=root, capture_output=True)
            if retired.get(path.as_posix()) == prior.stdout and prior.returncode == 0:
                continue
            raise RuntimeError(f"Published release evidence cannot be deleted or renamed: {path}; use lifecycle fields to withdraw it")
        record = validate_record(read(root / path))
        expected = Path("release-records") / record["line_id"] / (record["version"] + ".json")
        if path != expected:
            raise RuntimeError(f"Release record path disagrees with its identity: {path}")
        if base:
            previous = subprocess.run(["git", "show", f"{base}:{path.as_posix()}"], cwd=root,
                                      capture_output=True, text=True)
            if previous.returncode == 0:
                if immutable_record(json.loads(previous.stdout)) != immutable_record(record):
                    raise RuntimeError(f"Published release evidence is immutable: {path}; allocate a new revision")
                # Lifecycle edits are intentional recommendation changes.
                continue
        yield record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--base", help="Trusted PR base commit; requires assurance for every added image record")
    mode.add_argument("--audit", action="store_true", help="Audit the full ledger under its original contracts; not an additions acceptance gate")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "xormania/xorder"))
    args = parser.parse_args()
    if args.audit:
        if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
            parser.error("PR additions require --base; --audit cannot serve as their acceptance gate")
        if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("GITHUB_REF") != "refs/heads/master":
            parser.error("Hosted full-ledger audits require master; feature-ref audits cannot satisfy catalog-evidence")
        print("Full-ledger audit verifies local records under their original public-facts contract; it does not establish acceptance or historical status of those records.")
    count = 0
    for record in changed_image_records(args.base):
        verify_image_record(record, args.repository, require_assurance=not args.audit)
        print(f"Verified public release evidence: {record['line_id']} v{record['version']}")
        count += 1
    print(f"Verified {count} image release records; no image builds requested.")


if __name__ == "__main__":
    main()
