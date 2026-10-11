#!/usr/bin/env python3
"""Plan GHCR build-cache imports; only branch-push Actions jobs may export."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid


def cache_image(repository):
    """Keep ordinary GitHub names, with a distinct safe name for unusual ones."""
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be a GitHub owner/name, without URLs or extra paths")
    owner, name = repository.lower().split("/")
    if not re.fullmatch(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*", name):
        digest = hashlib.sha256(name.encode()).hexdigest()[:16]
        name = (re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "repository")[:80] + "-" + digest
    if not re.fullmatch(r"[a-z0-9]+(?:-+[a-z0-9]+)*", owner):
        raise ValueError("repository owner is not a valid GHCR namespace")
    return f"ghcr.io/{owner}/{name}-cache"


def branch_tag(branch, scope=""):
    if not branch:
        raise ValueError("a nonempty branch is required")
    if scope and not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,23}", scope):
        raise ValueError("scope must be at most 24 lowercase letters, digits, dots, underscores or hyphens")
    if branch in ("main", "dev", "master"):
        tag = branch
    else:
        # Hash every other branch, including already-safe names: a/b and a-b,
        # differently cased branches, and truncated names must not share a tag.
        slug = re.sub(r"[^a-z0-9_.-]+", "-", branch.lower()).strip("._-") or "branch"
        tag = slug[:82] + "-" + hashlib.sha256(branch.encode()).hexdigest()[:16]
    return (scope + "-" if scope else "") + tag


def plan(repository, branch=None, default_branch="main", base_branch=None, scope="", write=False,
         protected=False, trusted_branches=()):
    image = cache_image(repository)
    # Validate scope even when there is no current branch (forks/detached HEAD).
    branch_tag(default_branch or "main", scope)
    trusted_branches = list(dict.fromkeys(trusted_branches))
    branches = list(dict.fromkeys(item for item in (branch, base_branch, "dev", "main", default_branch,
                                                   *trusted_branches) if item))
    if protected:
        branches = [item for item in branches if item in trusted_branches]
    imports = [f"type=registry,ref={image}:{branch_tag(item, scope)}" for item in branches]
    tag = branch_tag(branch, scope) if branch else ""
    exporter = (f"type=registry,ref={image}:{tag},mode=max,image-manifest=true,oci-mediatypes=true"
                if write and branch else "")
    # Clear inherited exports first, so a read-only Bake run cannot retain a
    # cache-to from the consumer's Compose/Bake definition.
    bake = ["*.cache-from=", "*.cache-to="]
    bake += ["*.cache-from+=" + item for item in imports]
    if exporter:
        bake.append("*.cache-to+=" + exporter)
    return {"image": image, "branch-tag": tag, "import-policy": "protected-only" if protected else "branch-reuse", "cache-from": imports,
            "cache-to": exporter, "write-enabled": bool(exporter), "bake-set": bake}


def github_plan(env):
    """Derive trust from the trigger, never from a caller-provided branch name."""
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text())
    repository = env["GITHUB_REPOSITORY"]
    event_repository = event.get("repository", {})
    default = event_repository.get("default_branch") or "main"
    trigger, ref = env.get("GITHUB_EVENT_NAME", ""), env.get("GITHUB_REF", "")
    ref_branch = ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else None
    branch = ref_branch
    base = None
    if trigger in ("pull_request", "pull_request_target"):
        pr = event.get("pull_request", {})
        head, base_info = pr.get("head", {}), pr.get("base", {})
        branch = head.get("ref") if (head.get("repo") or {}).get("full_name", "").lower() == repository.lower() else None
        base = base_info.get("ref")
    requested = env.get("XORDER_CACHE_WRITE", "true")
    if requested not in ("true", "false"):
        raise ValueError("write must be true or false")
    trusted = (env.get("GITHUB_ACTIONS") == "true" and trigger == "push"
               and ref.startswith("refs/heads/") and not event.get("deleted", False)
               and event_repository.get("full_name", "").lower() == repository.lower())
    # A cache is executable build input. Branch pushes may write their own cache,
    # but a protected job must not consume a mutable lower-trust branch cache.
    # GitHub supplies protection for the current ref; other branches require an
    # explicit owner-maintained list with equal protection. Missing facts fail
    # closed, and pull_request_target never imports the PR head's cache.
    protection = env.get("GITHUB_REF_PROTECTED", "")
    protected = protection != "false" or trigger == "pull_request_target"
    trusted_branches = [name.strip() for name in env.get("XORDER_CACHE_TRUSTED_BRANCHES", "").splitlines() if name.strip()]
    if protection == "true" and ref_branch:
        trusted_branches.append(ref_branch)
    return plan(repository, branch, default, base, env.get("XORDER_CACHE_SCOPE", ""),
                write=requested == "true" and trusted, protected=protected,
                trusted_branches=trusted_branches)


def current_branch(directory):
    result = subprocess.run(["git", "-C", str(directory), "symbolic-ref", "--quiet", "--short", "HEAD"],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def github_outputs(result, destination):
    with Path(destination).open("a") as output:
        for key, value in result.items():
            if isinstance(value, list):
                value = "\n".join(value)
            elif isinstance(value, bool):
                value = str(value).lower()
            delimiter = "XORDER_CACHE_" + uuid.uuid4().hex
            output.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def compose_overlay(result, service):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", service):
        raise ValueError("service must be a Compose service name")
    # Plain [] would append nothing and retain inherited exports. Compose's
    # explicit reset/override tags enforce the local read-only cache policy.
    lines = ["services:", f"  {json.dumps(service)}:", "    build:",
             "      cache_to: !reset []", "      cache_from: !override" + ("" if result["cache-from"] else " []")]
    lines += ["        - " + json.dumps(item) for item in result["cache-from"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", help="GitHub owner/name whose CI owns the cache")
    parser.add_argument("--branch", help="Current branch; defaults to this checkout's branch")
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--scope", default="", help="Optional separate build/target scope, matching CI")
    parser.add_argument("--protected", action="store_true", help="Import only explicitly trusted branch caches")
    parser.add_argument("--trusted-branch", action="append", default=[], help="Equally protected cache branch; repeat for multiple branches")
    parser.add_argument("--format", choices=("json", "buildx", "bake", "compose"), default="json")
    parser.add_argument("--service", default="php", help="Compose service for the generated import overlay")
    parser.add_argument("--github-output", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.github_output:
            result = github_plan(os.environ)
            github_outputs(result, args.github_output)
        else:
            if not args.repository:
                raise ValueError("local imports require --repository owner/name")
            result = plan(args.repository, args.branch or current_branch(Path.cwd()), args.default_branch,
                          scope=args.scope, protected=args.protected, trusted_branches=args.trusted_branch)
            if args.format == "json":
                print(json.dumps(result, indent=2))
            elif args.format == "buildx":
                print("\n".join("--cache-from=" + item for item in result["cache-from"]))
            elif args.format == "bake":
                print("\n".join(result["bake-set"]))
            else:
                print(compose_overlay(result, args.service), end="")
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
