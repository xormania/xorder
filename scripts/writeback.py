#!/usr/bin/env python3
"""Stage generated changes through a PR; never push to protected master."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from urllib.error import URLError
from pathlib import Path
from library import ROOT, encoded, generated, read, validate_record
from registry import resolve
from refresh import refresh as refresh_inputs
from xorder import model as resource_model
from xorder.transport import download
from catalog_summary import catalog_body, proposed_records, source_prs
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def authored_readme(text):
    """Remove only the two generator-owned tables before merging prose."""
    for section in ("catalog", "resources"):
        pattern = rf"(?s)(<!-- {section}:start -->\n).*?(\n<!-- {section}:end -->)"
        text, count = re.subn(pattern, lambda match: match[1] + match[2], text)
        if count != 1:
            raise RuntimeError(f"README needs manual recovery: expected one {section} section")
    return text


def recover_generated_conflicts():
    conflicts = output("git", "diff", "--name-only", "--diff-filter=U").splitlines()
    if not conflicts:
        raise RuntimeError("Master merge failed without generated-file conflicts; inspect the Git failure")
    try:
        owned = {str(path.relative_to(ROOT)) for path in generated(ROOT)}
    except (ValueError, AssertionError) as error:
        raise RuntimeError("Release inputs need manual conflict recovery: " + ", ".join(conflicts)) from error
    authored = sorted(set(conflicts) - owned)
    if authored:
        raise RuntimeError("Authored files need manual conflict recovery: " + ", ".join(authored))
    if "README.md" in conflicts:
        with tempfile.TemporaryDirectory(prefix="xorder-readme-merge-") as temporary:
            versions = []
            for stage in (2, 1, 3):  # automation branch, merge base, current master
                path = Path(temporary) / str(stage)
                path.write_text(authored_readme(output("git", "show", f":{stage}:README.md")))
                versions.append(str(path))
            merged = subprocess.run(["git", "merge-file", "-p", *versions], cwd=ROOT,
                                    capture_output=True, text=True)
            if merged.returncode:
                raise RuntimeError("Authored README prose needs manual conflict recovery")
            (ROOT / "README.md").write_text(merged.stdout)
    # The ledger and authored inputs have merged cleanly. Regenerate their views,
    # including the README tables, rather than selecting either stale snapshot.
    outputs = generated(ROOT)
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    run("git", "add", "--", *(str(path.relative_to(ROOT)) for path in outputs))
    run("git", "commit", "--no-edit")


def prepare_branch(branch):
    run("git", "fetch", "origin", "master")
    exists = output("git", "ls-remote", "--heads", "origin", branch).strip()
    if exists:
        run("git", "fetch", "origin", branch)
        run("git", "checkout", "-B", branch, "FETCH_HEAD")
        try:
            run("git", "merge", "origin/master", "--no-edit")
        except subprocess.CalledProcessError:
            recover_generated_conflicts()
    else:
        run("git", "checkout", "-b", branch, "origin/master")


def upsert_pr(branch, title, body):
    # gh pr edit reads unrelated organization/team metadata through GraphQL,
    # requiring read:org even when only title/body change. REST needs only the
    # repository permissions used to push this branch and create/update its PR.
    repository = os.environ["GITHUB_REPOSITORY"]
    endpoint = f"repos/{repository}/pulls"
    owner = repository.split("/", 1)[0]
    prs = json.loads(output("gh", "api", "--method", "GET", endpoint,
                            "-f", f"head={owner}:{branch}", "-f", "base=master",
                            "-f", "state=open"))
    payload = {"title": title, "body": body}
    if prs:
        endpoint += f"/{prs[0]['number']}"
        method = "PATCH"
    else:
        payload.update(base="master", head=branch)
        method = "POST"
    request_path = ROOT / "out" / "pr-request.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(encoded(payload))
    run("gh", "api", "--method", method, endpoint, "--input", str(request_path))


def release_record(value):
    return resource_model.validate_record(value, ROOT) if value.get("schema_version") == 2 else validate_record(value)


class PublicResourceUnavailable(RuntimeError):
    """A single resource failed anonymous availability or identity verification."""


def accepted_resource(record):
    release = json.loads(output("gh", "release", "view", record["source_tag"], "--json", "isDraft,targetCommitish,assets"))
    if release["isDraft"] or release["targetCommitish"] != record["source_commit"]:
        return False
    publication = record["publication"]
    assets = [asset for asset in release["assets"] if asset["name"] == publication["filename"]]
    durable = [asset for asset in release["assets"] if asset["name"] == "record.json"]
    if len(assets) != 1 or len(durable) != 1 or assets[0]["url"] != publication["url"]:
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="xorder-writeback-") as temporary:
            facts = download(publication["url"], Path(temporary) / publication["filename"], publication["sha256"])
            download(durable[0]["url"], Path(temporary) / "record.json", hashlib.sha256(resource_model.encoded(record).encode()).hexdigest())
    except (ValueError, URLError) as error:
        raise PublicResourceUnavailable(str(error)) from error
    return facts["size_bytes"] == publication["size_bytes"]


def record_path(record):
    if record.get("schema_version") == 2:
        return Path("release-records/artifacts") / record["id"] / (record["version"] + ".json")
    return Path("release-records") / record["line_id"] / (record["version"] + ".json")


def catalog_identity(release_inputs):
    """Bind complete durable facts, including original source and verification evidence."""
    keyed = {}
    for record in release_inputs:
        path = record_path(record).as_posix()
        if path in keyed and keyed[path] != record:
            raise RuntimeError("Conflicting publication records for " + path)
        keyed[path] = record
    return hashlib.sha256(json.dumps(keyed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def catalog_branch(release_inputs):
    branch = "automation/catalog-" + catalog_identity(release_inputs)[:24]
    if output("git", "ls-remote", "--heads", "origin", branch).strip():
        return branch
    # Recover pending branches produced by older run-ID automation as well as
    # content-keyed proposals that contain a superset of this run's records.
    repository = os.environ["GITHUB_REPOSITORY"]
    pages = json.loads(output("gh", "api", "--paginate", "--slurp", "--method", "GET",
                              f"repos/{repository}/pulls", "-f", "base=master", "-f", "state=open", "-f", "per_page=100"))
    for pull in (pull for page in pages for pull in page):
        head = pull.get("head", {})
        candidate = head.get("ref", "")
        if head.get("repo", {}).get("full_name") != repository or not candidate.startswith("automation/catalog-"):
            continue
        run("git", "fetch", "origin", candidate)
        matches = True
        for record in release_inputs:
            prior = subprocess.run(["git", "show", f"FETCH_HEAD:{record_path(record).as_posix()}"],
                                   cwd=ROOT, capture_output=True, text=True)
            if prior.returncode or json.loads(prior.stdout) != record:
                matches = False
                break
        if matches:
            return candidate
    return branch


def main(refresh=False):
    release_inputs = [release_record(read(p)) for p in (ROOT / "out/releases").rglob("record.json")]
    if not refresh and not release_inputs:
        print("No completed records to stage. Inspect the publication jobs for the incomplete step.")
        return
    run("git", "config", "user.name", "image-library automation")
    run("git", "config", "user.email", "image-library@users.noreply.github.com")
    branch = "automation/refresh-" + os.environ["GITHUB_RUN_ID"] if refresh else catalog_branch(release_inputs)
    prepare_branch(branch)
    if refresh:
        # Resolve after checkout. Allocate from master so a rerun of the same
        # pending refresh does not increment the proposal's revision again.
        refresh_inputs(base_ref="origin/master")
    else:
        for record in release_inputs:
            if record.get("schema_version") == 2:
                try:
                    accepted = accepted_resource(record)
                except PublicResourceUnavailable as error:
                    # Public availability is a per-resource gate. A broken
                    # payload/record must not block independently verified releases.
                    # API authentication and local filesystem errors stay global.
                    print(f"Skipping unverified public resource release for {record['id']}: {error}")
                    continue
                if not accepted:
                    print(f"Skipping unfinished public resource release for {record['id']}")
                    continue
                path = ROOT / "release-records" / "artifacts" / record["id"] / (record["version"] + ".json")
                if path.exists() and read(path) != record:
                    raise RuntimeError("Existing resource identity differs from the publication record")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(encoded(record))
                continue
            p = record["publication"]
            remote = resolve(p["repository"] + ":" + p["exact_tag"])
            if not remote or remote["digest"] != p["digest"]:
                print(f"Skipping incomplete exact promotion for {record['line_id']}")
                continue
            release = json.loads(output("gh", "release", "view", record["source_tag"], "--json", "isDraft,targetCommitish"))
            if release["isDraft"] or release["targetCommitish"] != record["source_commit"]:
                print(f"Skipping unfinished source release for {record['line_id']}")
                continue
            path = ROOT / "release-records" / record["line_id"] / (record["version"] + ".json")
            if path.exists() and read(path) != record:
                raise RuntimeError("Existing release identity differs from the publication record")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded(record))
    outputs = generated(ROOT)
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    staged_paths = {str(path.relative_to(ROOT)) for path in outputs}
    staged_paths.update(path for path in ("images", "release-records") if (ROOT / path).exists())
    run("git", "add", "--", *sorted(staged_paths))
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    if not changed and output("git", "rev-list", "--count", "origin/master..HEAD").strip() == "0":
        print("Already current; no writeback needed.")
        return
    title = "Refresh development image inputs" if refresh else "Catalog verified public releases"
    if changed:
        run("git", "commit", "-m", title)
    # An unchanged recovered branch may still need its missing PR created.
    run("git", "push", "origin", branch)
    if refresh:
        body = "Updates changed upstream inputs and allocates fresh patch revisions only for their consumers and descendants. Debian package-index changes trigger apt refreshes. Image behavior is validated by PR CI before publication."
    else:
        views = []
        for name, key in (("catalog.json", "images"), ("catalog-v2.json", "resources")):
            previous = subprocess.run(["git", "show", f"origin/master:{name}"], cwd=ROOT, capture_output=True, text=True)
            views.append(json.loads(previous.stdout)[key] if previous.returncode == 0 else [])
        repository = os.environ["GITHUB_REPOSITORY"]
        proposed = proposed_records(ROOT)
        body = catalog_body(proposed, *views, repository, source_prs(proposed, repository))
    body += "\n\nMerge through the repository's permitted merge method. Writeback does not enable automatic merge. If this PR was created with GITHUB_TOKEN, select Approve workflows to run in the PR's merge box. LIBRARY_BOT_TOKEN lets PR validation start automatically."
    upsert_pr(branch, title, body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    main(refresh=parser.parse_args().refresh)
