#!/usr/bin/env python3
"""Run prepared Serena over stdio MCP against one mounted checkout."""
import argparse
import json
import os
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def available_image():
    entries = [item for item in json.loads((ROOT / "catalog-v2.json").read_text())["resources"]
               if item["id"] == "image/php-serena/8.5-trixie" and item["lifecycle"] == "available"
               and item["verification"]["status"] == "passed" and "linux/amd64" in item["targets"]]
    if not entries:
        raise ValueError("No verified php-serena release is available. Build a candidate with scripts/build.py and pass --image explicitly.")
    return max(entries, key=lambda item: tuple(map(int, item["version"].split("."))))["identity"]


def command(args):
    workspace = args.workspace.resolve(strict=True)
    project = (workspace / args.project).resolve(strict=True)
    if not workspace.is_dir() or not project.is_dir() or not project.is_relative_to(workspace):
        raise ValueError("The project must be a directory inside the mounted checkout")
    if "," in str(workspace):
        raise ValueError("Docker --mount cannot represent a checkout path containing a comma")
    image = args.image or available_image()
    uid, gid = os.getuid(), os.getgid()
    mount = f"type=bind,src={workspace},dst=/workspace" + (",readonly" if args.read_only else "")
    flags = []
    if getattr(args, "cache_dir", None):
        cache = args.cache_dir.resolve()
        if "," in str(cache):
            raise ValueError("Cache path cannot contain a comma")
        namespace = hashlib.sha256((str(workspace) + str(project) + image).encode()).hexdigest()
        cache = cache / namespace
        cache.mkdir(parents=True, exist_ok=True)
        flags = ["--mount", f"type=bind,src={cache},dst=/run/serena-cache"]
    argv = ["docker", "run", "--rm", "--interactive", "--pull=never", "--platform", "linux/amd64",
            "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user", f"{uid}:{gid}", "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
            "--tmpfs", f"/home/dev:rw,nosuid,nodev,size=512m,uid={uid},gid={gid},mode=0700",
            *flags, "--mount", mount, "--workdir", "/workspace",
            "--entrypoint", "/usr/local/bin/library-serena", image,
            "--project", str(Path("/workspace") / project.relative_to(workspace)),
            "--read-only" if args.read_only else "--write"]
    if getattr(args, "request_timeout", None):
        argv += ["--request-timeout", str(args.request_timeout)]
    if flags:
        argv += ["--cache-dir", "/run/serena-cache"]
    if getattr(args, "languages", None):
        argv += ["--languages", args.languages]
    return argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--project", default=".", help="Project directory within the checkout; use . for uxor recipes and demo source")
    parser.add_argument("--image", help="An explicitly selected digest or locally built candidate; images are never pulled during MCP startup")
    parser.add_argument("--cache-dir", type=Path, help="Optional host directory for a per-worktree, per-image index")
    parser.add_argument("--request-timeout", type=float, help="Language-server request timeout in seconds (default 180)")
    parser.add_argument("--languages", help="Comma-separated php_phpactor,typescript; use both for PHP and JavaScript")
    access = parser.add_mutually_exclusive_group()
    access.add_argument("--read-only", dest="read_only", action="store_true", default=True,
                        help="Mount the checkout read-only (default)")
    access.add_argument("--write", dest="read_only", action="store_false",
                        help="Allow the REPL and PHP tooling to modify a trusted checkout")
    args = parser.parse_args()
    try:
        argv = command(args)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
