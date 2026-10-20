#!/usr/bin/env python3
"""Reject promotion of mutable non-root HOME or harness state into root execution."""
import argparse
import os
from pathlib import Path
import stat


def _owned(path, *, sticky_parent=False):
    info = path.lstat()
    if info.st_uid != 0:
        raise ValueError(f"Root harness state must be root-owned before startup: {path}")
    if stat.S_ISLNK(info.st_mode):
        raise ValueError(f"Root harness state path must not be a symlink: {path}")
    if info.st_mode & 0o022:
        if not (sticky_parent and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX):
            raise ValueError(f"Root harness state must not be group/other-writable: {path}")
    return info


def validate_root_tree(path, *, missing=False, sticky_ancestors=False):
    """Check ownership before chown can erase the prior trust boundary.

    Sticky root-owned temporary ancestors may protect a private custom store;
    HOME itself and its ancestors always require ordinary protected permissions.
    Internal links are allowed (npm uses them), while external links cannot
    import less-trusted files into the protected tree.
    """
    path = Path(os.path.abspath(path))
    for parent in reversed(path.parents):
        if missing and not parent.exists() and not parent.is_symlink():
            continue
        _owned(parent, sticky_parent=sticky_ancestors)
    if not path.exists() and not path.is_symlink():
        if missing:
            return
        raise ValueError(f"Root harness HOME does not exist: {path}")
    root = _owned(path)
    if not stat.S_ISDIR(root.st_mode):
        raise ValueError(f"Root harness state must be a directory: {path}")
    def inaccessible(error):
        raise error
    for directory, directories, files in os.walk(path, followlinks=False, onerror=inaccessible):
        for name in directories + files:
            entry = Path(directory) / name
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode):
                lexical = Path(os.path.abspath(entry.parent / os.readlink(entry)))
                if (info.st_uid != 0 or not lexical.is_relative_to(path)
                        or not entry.resolve().is_relative_to(path)):
                    raise ValueError(f"Root harness state contains an untrusted symlink: {entry}")
            else:
                _owned(entry)


def validate_root_store(path, *, require_exists=False):
    if os.geteuid() == 0:
        validate_root_tree(path, missing=not require_exists, sticky_ancestors=True)


def startup(home=Path("/home/dev"), selected_uid=None):
    uid = int(os.environ.get("PUID", "1000") if selected_uid is None else selected_uid)
    if uid < 0:
        raise ValueError("PUID must be nonnegative")
    if os.geteuid() == 0 and uid == 0:
        try:
            validate_root_tree(home)
            store = os.environ.get("HARNESS_ROOT")
            if store:
                validate_root_store(store)
        except (ValueError, OSError) as error:
            raise ValueError(str(error) + "; use a dedicated root-owned HOME volume for root sessions") from error


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path("/home/dev"))
    args = parser.parse_args()
    try:
        startup(args.home)
    except (ValueError, OSError) as error:
        parser.exit(64, f"harness startup: {error}\n")
