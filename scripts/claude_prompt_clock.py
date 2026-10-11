#!/usr/bin/env python3
"""Add an observed UTC clock to each Claude Code prompt, with opt-in setup."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import sys
import subprocess
import tempfile


def context():
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": "Current UTC time: " + timestamp}}


def exclude_local_settings(project, settings):
    """Local hook settings contain machine paths and must not become commit candidates."""
    try:
        root = subprocess.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    except FileNotFoundError:
        return False
    if root.returncode != 0:
        return False
    repository = Path(root.stdout.strip()).resolve()
    relative = settings.relative_to(repository).as_posix()
    tracked = subprocess.run(["git", "-C", str(project), "ls-files", "--error-unmatch", "--", str(settings)], text=True, capture_output=True)
    if tracked.returncode == 0:
        raise ValueError("settings.local.json is tracked; make the machine-local settings untracked before installing the clock")
    result = subprocess.run(["git", "-C", str(project), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"], text=True, capture_output=True, check=True)
    path = Path(result.stdout.strip())
    if path.is_symlink():
        raise ValueError("Git local exclude file is a symlink; exclude local clock settings manually")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as output:
        output.seek(0)
        existing = output.read()
        pattern = "/" + relative
        if pattern not in existing.splitlines():
            output.seek(0, os.SEEK_END)
            output.write(("\n" if existing and not existing.endswith("\n") else "") + pattern + "\n")
    return True


def install(project):
    project = Path(project).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project must be an existing directory")
    settings = project / ".claude/settings.local.json"
    if settings.is_symlink():
        raise ValueError("settings.local.json is a symlink; add the clock hook to its target manually")
    data = json.loads(settings.read_text()) if settings.exists() else {}
    if not isinstance(data, dict):
        raise ValueError("Claude settings must be a JSON object")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Claude settings hooks must be an object")
    groups = hooks.setdefault("UserPromptSubmit", [])
    if not isinstance(groups, list) or any(not isinstance(group, dict) or
            not isinstance(group.get("hooks"), list) or
            any(not isinstance(handler, dict) for handler in group["hooks"]) for group in groups):
        raise ValueError("UserPromptSubmit must contain hook groups with handler lists")
    excluded = exclude_local_settings(project, settings)
    handler = {"type": "command", "command": "python3",
               "args": [str(Path(__file__).resolve())], "timeout": 5}
    if any(existing.get("type") == handler["type"] and existing.get("command") == handler["command"]
           and existing.get("args") == handler["args"] for group in groups for existing in group["hooks"]):
        return {"status": "already-installed", "settings": str(settings), "local_git_excluded": excluded}
    groups.append({"hooks": [handler]})
    settings.parent.mkdir(parents=True, exist_ok=True)
    mode = settings.stat().st_mode & 0o777 if settings.exists() else 0o600
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=settings.parent, prefix=".clock-", delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, indent=2)
            output.write("\n")
        temporary.chmod(mode)
        os.replace(temporary, settings)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"status": "installed", "settings": str(settings), "local_git_excluded": excluded}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action")
    setup = commands.add_parser("install", help="Append the clock to local project settings")
    setup.add_argument("--project", required=True, help="Existing Claude Code project directory")
    options = parser.parse_args(arguments)
    result = install(options.project) if options.action == "install" else context()
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print("xorder clock: " + str(error), file=sys.stderr)
        sys.exit(1)
