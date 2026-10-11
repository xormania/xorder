#!/usr/bin/env python3
"""Check image-ledger additions against public durable release evidence."""
import argparse
import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from library import ROOT, DIGEST, read, validate_record
from registry import resolve
from xorder.transport import download


LIFECYCLE_FIELDS = {"lifecycle", "reason", "replacement", "lifecycle_date"}


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


def verify_image_record(record, repository):
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
    if base:
        paths = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", base, "HEAD", "--", "release-records"],
            cwd=root, text=True).splitlines()
    else:
        paths = [str(path.relative_to(root)) for path in (root / "release-records").rglob("*.json")]
    for relative in sorted(paths):
        path = Path(relative)
        if path.parts[1] == "artifacts" or path.suffix != ".json":
            continue
        if base and not (root / path).is_file():
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
    parser.add_argument("--base")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "xormania/xorder"))
    args = parser.parse_args()
    count = 0
    for record in changed_image_records(args.base):
        verify_image_record(record, args.repository)
        print(f"Verified public release evidence: {record['line_id']} v{record['version']}")
        count += 1
    print(f"Verified {count} image release records; no image builds requested.")


if __name__ == "__main__":
    main()
