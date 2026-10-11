#!/usr/bin/env python3
"""Explicit trusted-worktree dependency seeding, without installs or overwrites."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from cache import sha, tree_manifest

SHARING_RECEIPT = ".xorder-shared-dependencies.json"


def relative_path(relative):
    path = Path(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("Seed paths must be relative paths inside the checkout")
    return path


def inside(workspace, relative):
    path = relative_path(relative)
    result = workspace / path
    if result.resolve() != result:
        raise ValueError("Seed paths cannot be redirected by symlinks: " + relative)
    return result


def shared_paths(workspace):
    """A sharing guard applies to donor and receiver on every runner invocation."""
    receipt = inside(workspace, SHARING_RECEIPT)
    if not receipt.exists():
        return []
    value = json.loads(receipt.read_text())
    if not isinstance(value, dict):
        raise ValueError("Invalid dependency sharing receipt: " + str(receipt))
    paths = value.get("paths")
    if value.get("schema") != 1 or not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
        raise ValueError("Invalid dependency sharing receipt: " + str(receipt))
    for path in paths:
        relative_path(path)
    return sorted(set(paths))


def matched_inputs(source, destination, env):
    map_file = env.get("IMPORTMAP_FILE") or "importmap.php"
    if Path(map_file).is_absolute() or ".." in Path(map_file).parts or "\\" in map_file:
        raise ValueError("Seed importmap file must be relative inside demo")
    required = ["package.json", "package-lock.json", "demo/composer.json", "demo/composer.lock"]
    optional = ["demo/symfony.lock", "demo/" + map_file]
    fingerprints = {}
    for name in required + optional:
        donor, receiver = inside(source, name), inside(destination, name)
        if name in optional and not donor.exists() and not receiver.exists():
            continue
        if not donor.is_file() or not receiver.is_file():
            raise ValueError("Seed inputs are missing or differ: " + name)
        fingerprint = sha(donor)
        if fingerprint != sha(receiver):
            raise ValueError("Seed inputs are missing or differ: " + name)
        fingerprints[name] = fingerprint
    return fingerprints


def dependency_paths(env, inputs):
    paths = ["demo/vendor", "node_modules"]
    if "demo/" + (env.get("IMPORTMAP_FILE") or "importmap.php") in inputs:
        vendor = (env.get("IMPORTMAP_VENDOR_DIR") or "assets/vendor").rstrip("/")
        if not Path(vendor).parts or Path(vendor).is_absolute() or ".." in Path(vendor).parts or "\\" in vendor:
            raise ValueError("Seed importmap vendor must be relative inside demo")
        paths.append("demo/" + vendor)
    ordered = sorted(set(paths))
    for index, path in enumerate(ordered):
        if any(Path(other).is_relative_to(Path(path)) for other in ordered[index + 1:]):
            raise ValueError("Seed dependency directories cannot overlap")
    return ordered


def snapshot(workspace, relative, destination):
    folder = inside(workspace, relative)
    if not folder.is_dir():
        raise ValueError("Seed source dependency directory is missing: " + relative)
    for directory, dirs, files in os.walk(folder, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                raise ValueError("Unsupported dependency file type: " + str(path))
            if path.is_symlink():
                target = os.readlink(path)
                receiver_link = destination / path.relative_to(workspace)
                if Path(target).is_absolute() or not path.resolve().is_relative_to(workspace) or not (receiver_link.parent / target).resolve().is_relative_to(destination):
                    raise ValueError("Dependency symlink leaves its checkout: " + str(path))
    manifest = tree_manifest(folder)
    if not manifest:
        raise ValueError("Seed source dependency directory is empty: " + relative)
    return manifest


def require_stopped(workspaces, env):
    """Include legacy unlabeled stacks by inspecting their actual bind mounts."""
    try:
        result = subprocess.run(["docker", "ps", "-q"], env=env, text=True, capture_output=True, check=True)
        ids = result.stdout.split()
        containers = json.loads(subprocess.run(["docker", "inspect", *ids], env=env, text=True, capture_output=True, check=True).stdout) if ids else []
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Hardlink seeding requires a reachable Docker engine to verify both worktrees are stopped; use the default private copy instead") from error
    for container in containers:
        labels = container.get("Config", {}).get("Labels") or {}
        for workspace in workspaces:
            mounted = any(mount.get("Type") == "bind" and mount.get("Source") and (
                Path(mount["Source"]).resolve().is_relative_to(workspace) or workspace.is_relative_to(Path(mount["Source"]).resolve()))
                for mount in container.get("Mounts", []))
            if mounted or labels.get("dev.xorder.workspace") == str(workspace):
                raise ValueError("Stop containers using " + str(workspace) + " before hardlink seeding: " + container.get("Name", container.get("Id", "unknown")))


def copy_tree(source, destination, hardlink):
    if hardlink:
        shutil.copytree(source, destination, symlinks=True, copy_function=os.link)
    elif shutil.which("cp"):
        # Reflinks have independent file contents; normal copies are the fallback.
        subprocess.run(["cp", "-a", "--reflink=auto", "--", str(source), str(destination)], check=True)
    else:
        shutil.copytree(source, destination, symlinks=True)


def promote(staged, destination):
    # GNU mv uses renameat2(RENAME_NOREPLACE) when supported. Checking the staged
    # path also detects its successful-but-skipped no-clobber return status.
    result = subprocess.run(["mv", "--no-clobber", "--no-target-directory", "--", str(staged), str(destination)], capture_output=True, text=True)
    if staged.exists() and (destination.exists() or destination.is_symlink()):
        raise ValueError("Seed destination appeared during staging; nothing was overwritten: " + str(destination))
    result.check_returncode()


def seed(destination, source, env=None, hardlink=False):
    env = dict(os.environ if env is None else env)
    destination, source = Path(destination).resolve(strict=True), Path(source).resolve(strict=True)
    if not destination.is_dir() or not source.is_dir() or destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Seed donor and receiver must be separate, non-nested checkout directories")
    inputs = matched_inputs(source, destination, env)
    paths = dependency_paths(env, inputs)
    if shared_paths(destination):
        raise ValueError("Receiver already has a dependency sharing receipt; remove its shared trees and receipt before reseeding")
    donor_guard = shared_paths(source)
    if hardlink and donor_guard and donor_guard != paths:
        raise ValueError("Donor sharing receipt covers different dependency directories")
    targets = [inside(destination, path) for path in paths]
    for target in targets:
        if target.exists() or target.is_symlink():
            raise ValueError("Seed destination already exists; nothing was overwritten: " + str(target))
    manifests = {path: snapshot(source, path, destination) for path in paths}
    if hardlink:
        require_stopped((source, destination), env)
    promoted, receipts = [], []
    with tempfile.TemporaryDirectory(prefix=".xorder-seed-", dir=destination) as temporary:
        staging = Path(temporary)
        for index, path in enumerate(paths):
            staged = staging / str(index)
            copy_tree(source / path, staged, hardlink)
            if not staged.is_dir() or staged.is_symlink() or staged.resolve() != staged:
                raise ValueError("Seed staged dependency root is redirected or incomplete: " + path)
            if tree_manifest(staged) != manifests[path]:
                raise ValueError("Seed source changed while copying: " + path)
        if matched_inputs(source, destination, env) != inputs:
            raise ValueError("Seed manifest or lock changed during staging")
        for index, path in enumerate(paths):
            # Validate the actual donor tree again: matching bytes alone must not
            # adopt a dependency root redirected to an outside checkout mid-copy.
            if snapshot(source, path, destination) != manifests[path]:
                raise ValueError("Seed source changed during staging: " + path)
            if hardlink:
                for name, entry in manifests[path].items():
                    if "link" in entry:
                        continue
                    donor = (source / path / name).stat(follow_symlinks=False)
                    retained = (staging / str(index) / name).stat(follow_symlinks=False)
                    if (donor.st_dev, donor.st_ino) != (retained.st_dev, retained.st_ino):
                        raise ValueError("Seed donor inode changed during hardlink staging: " + path + "/" + name)
        if hardlink:
            require_stopped((source, destination), env)
        try:
            if hardlink:
                value = json.dumps({"schema": 1, "paths": paths}, sort_keys=True) + "\n"
                for checkout in (source, destination):
                    receipt = inside(checkout, SHARING_RECEIPT)
                    if receipt.exists():
                        if shared_paths(checkout) != paths:
                            raise ValueError("Dependency sharing receipt changed while staging")
                        continue
                    with receipt.open("x") as output:
                        output.write(value)
                    receipts.append(receipt)
            for index, target in enumerate(targets):
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.resolve() != target:
                    raise ValueError("Seed destination was redirected while staging: " + str(target))
                promote(staging / str(index), target)
                promoted.append(target)
        except BaseException:
            for target in reversed(promoted):
                shutil.rmtree(target)
            for receipt in receipts:
                receipt.unlink()
            raise
    print("Seeded " + ", ".join(paths) + (" using protected hardlinks; both checkouts now require read-only reuse" if hardlink else " using private reflinks/copies"))
    print("No install or setup hooks ran; up still verifies Composer, npm and importmap readiness.")
    return 0
