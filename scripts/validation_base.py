#!/usr/bin/env python3
"""Reuse successful validation for an ancestral head of the same PR and base."""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SHA = re.compile(r"[0-9a-f]{40}")
ARTIFACT_FILE = "validation-context.json"
MAX_CANDIDATES = 10
MAX_ARCHIVE = 64 * 1024
MAX_CONTEXT = 8 * 1024


def commit_tree(commit):
    result = subprocess.run(["git", "rev-parse", "--verify", f"{commit}^{{tree}}"],
                            capture_output=True, text=True)
    value = result.stdout.strip()
    return value if result.returncode == 0 and SHA.fullmatch(value) else None


def positive_integer(value):
    return type(value) is int and value > 0


def observed_checkout(source_head):
    """Prove the actual PR merge inputs instead of trusting a stale event base."""
    try:
        checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        parents = subprocess.check_output(["git", "show", "-s", "--format=%P", "HEAD"], text=True).split()
        tree = commit_tree("HEAD")
    except (OSError, subprocess.CalledProcessError):
        return {"checkout_sha": None, "checkout_tree": None, "checkout_parents": [], "base_sha": None}
    proven = (isinstance(source_head, str) and SHA.fullmatch(source_head)
              and len(parents) == 2 and parents[1] == source_head
              and SHA.fullmatch(checkout) and tree
              and all(SHA.fullmatch(parent) for parent in parents))
    return {"checkout_sha": checkout, "checkout_tree": tree, "checkout_parents": parents,
            "base_sha": parents[0] if proven else None}


def api_bytes(url, token, limit):
    origin = urlsplit(url)
    if (origin.scheme != "https" or origin.hostname != "api.github.com" or origin.port not in (None, 443)
            or origin.username or origin.password):
        raise ValueError("Validation evidence requires the GitHub API origin")
    request = Request(url, headers={"Accept": "application/vnd.github+json",
                                    "X-GitHub-Api-Version": "2022-11-28"})
    # Redirected artifact downloads must not carry the API credential.
    request.add_unredirected_header("Authorization", "Bearer " + token)
    # The exact HTTPS GitHub API origin is enforced before constructing the request.
    with urlopen(request, timeout=20) as response:  # nosec B310
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Validation evidence response exceeds its limit")
    return content


def artifact_context(run, repository, token):
    run_id, attempt = run.get("id"), run.get("run_attempt")
    if not positive_integer(run_id) or not positive_integer(attempt):
        return None
    prefix = f"https://api.github.com/repos/{repository}/actions"
    listing = json.loads(api_bytes(f"{prefix}/runs/{run_id}/artifacts?per_page=100", token, 128 * 1024))
    expected = f"validation-context-{attempt}"
    if (not isinstance(listing, dict) or not isinstance(listing.get("artifacts"), list)
            or not all(isinstance(item, dict) for item in listing["artifacts"])):
        return None
    artifacts = [item for item in listing["artifacts"] if item.get("name") == expected]
    if len(artifacts) != 1:
        return None
    artifact = artifacts[0]
    size = artifact.get("size_in_bytes")
    if (artifact.get("expired") is not False or not positive_integer(artifact.get("id"))
            or not positive_integer(size) or size > MAX_ARCHIVE):
        return None
    content = api_bytes(f"{prefix}/artifacts/{artifact['id']}/zip", token, MAX_ARCHIVE)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != ARTIFACT_FILE:
            return None
        member = members[0]
        if (member.is_dir() or member.file_size <= 0 or member.file_size > MAX_CONTEXT
                or member.flag_bits & 1 or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
            return None
        with archive.open(member) as stream:
            payload = stream.read(MAX_CONTEXT + 1)
        if len(payload) > MAX_CONTEXT:
            return None
    return json.loads(payload)


def valid_context(context, run, number, head, base, repository):
    return (isinstance(context, dict) and type(context.get("schema_version")) is int and context["schema_version"] == 1
            and context.get("repository") == repository
            and positive_integer(context.get("run_id")) and context["run_id"] == run.get("id")
            and positive_integer(context.get("run_attempt")) and context["run_attempt"] == run.get("run_attempt")
            and positive_integer(context.get("number")) and context["number"] == number
            and context.get("event") == "pull_request"
            and context.get("head_sha") == head and context.get("base_sha") == base
            and context.get("checkout_parents") == [base, head]
            and isinstance(context.get("checkout_sha"), str) and SHA.fullmatch(context["checkout_sha"])
            and isinstance(context.get("checkout_tree"), str) and SHA.fullmatch(context["checkout_tree"]))


def ancestor(commit, head):
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, head],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def select_context(runs, number, head, base, is_ancestor=ancestor, *, evidence=None,
                   repository=None, checkout_tree=None, get_tree=commit_tree):
    """Keep successful source-head comparisons separate from merge checkouts."""
    fallback = {"sha": base, "head": "HEAD", "reused": False, "same_head": False}
    if evidence is None or not repository or not checkout_tree:
        return fallback
    attempted = 0
    for run in runs:
        if (run.get("event") != "pull_request" or run.get("status") != "completed"
                or run.get("conclusion") != "success"):
            continue
        commit = run.get("head_sha", "")
        if not isinstance(commit, str) or not SHA.fullmatch(commit):
            continue
        if not is_ancestor(commit, head) or (commit != head and not is_ancestor(base, commit)):
            continue
        # An unchanged source head has the same tested merge inputs. For new
        # source heads, the old source must already contain the target base:
        # otherwise merging that base can change the tree without a source diff.
        if attempted >= MAX_CANDIDATES:
            break
        attempted += 1
        context = evidence(run)
        if not valid_context(context, run, number, commit, base, repository):
            continue
        expected_tree = checkout_tree if commit == head else get_tree(commit)
        if expected_tree and context["checkout_tree"] == expected_tree:
            return {"sha": commit, "head": head, "reused": True, "same_head": commit == head}
    return fallback


def select(runs, number, head, base, is_ancestor=ancestor, **evidence):
    """Retain the original base-only helper interface."""
    return select_context(runs, number, head, base, is_ancestor, **evidence)["sha"]


def record_context(path, checkout):
    """Record original event inputs before checks, independently of reused scope."""
    context = {"schema_version": 1, "repository": os.environ["GITHUB_REPOSITORY"],
               "run_id": int(os.environ["GITHUB_RUN_ID"]),
               "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
               "number": int(os.environ["PR_NUMBER"]) if os.environ.get("PR_NUMBER") else None,
               "event": os.environ["GITHUB_EVENT_NAME"],
               "head_sha": os.environ.get("HEAD_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "event_base_sha": os.environ.get("BASE_SHA") or None,
               **checkout}
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(context, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", action="store_true", help="Emit baseline, comparison head and reuse flags")
    parser.add_argument("--record-context", help="Write the original run context before checks")
    args = parser.parse_args()
    base = os.environ.get("BASE_SHA", "")
    number = os.environ.get("PR_NUMBER", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    checkout = observed_checkout(os.environ.get("HEAD_SHA", ""))
    if args.record_context:
        record_context(args.record_context, checkout)
    if number:
        # Unproved PR checkouts cannot establish a safe runtime delta.
        base = checkout["base_sha"] or ""
    context = {"sha": base, "head": "HEAD", "reused": False, "same_head": False}
    if base and number and token:
        repository = os.environ["GITHUB_REPOSITORY"]
        try:
            runs = json.loads(api_bytes(f"https://api.github.com/repos/{repository}/actions/workflows/validate.yml/runs?event=pull_request&status=success&per_page=100",
                                        token, 2 * 1024 * 1024))["workflow_runs"]
            if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
                raise ValueError("Invalid workflow run listing")
            context = select_context(runs, int(number), os.environ["HEAD_SHA"], base,
                                     evidence=lambda run: artifact_context(run, repository, token),
                                     repository=repository, checkout_tree=checkout["checkout_tree"])
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError, OSError,
                zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as error:
            print(f"Previous validation unavailable ({type(error).__name__}); checking the full PR", file=sys.stderr)
    if args.github_output:
        for key, value in context.items():
            print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    else:
        print(context["sha"])


if __name__ == "__main__":
    main()
