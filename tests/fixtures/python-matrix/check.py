#!/usr/bin/env python3
"""Verify an image-owned Python subject with normal mounts and no network."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def main():
    image = sys.argv[1]
    output = ROOT / "out/python-matrix"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xorder-python-matrix-") as directory:
        workspace = Path(directory) / "workspace"
        workspace.mkdir()
        cache = "xorder-python-matrix-" + Path(directory).name
        try:
            run("docker", "run", "--rm", "--init", "--network=none",
                "-e", "PUID=" + str(os.getuid()), "-e", "PGID=" + str(os.getgid()),
                "--mount", f"type=bind,src={workspace},dst=/workspace",
                "--mount", f"type=bind,src={FIXTURE},dst=/proof,readonly",
                "--mount", f"type=bind,src={ROOT / 'tests/fixtures/native-runtime'},dst=/runtime,readonly",
                "--mount", f"type=bind,src={ROOT / 'tests/fixtures/native-check.c'},dst=/native-check.c,readonly",
                "--mount", f"type=bind,src={output},dst=/evidence",
                "--mount", f"type=volume,src={cache},dst=/home/dev",
                image, "python3.14", "/proof/run.py")
        finally:
            subprocess.run(["docker", "volume", "rm", cache], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Offline Python matrix, SQLite WAL/read-only and real tmux acceptance passed")


if __name__ == "__main__":
    main()
