#!/usr/bin/env python3
"""Fetch a pinned consumer, then verify its matrix in a networkless container."""
import json
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
    consumer = json.loads((FIXTURE / "consumer.json").read_text())
    output = ROOT / "out/python-matrix"
    output.mkdir(parents=True, exist_ok=True)
    # This fetch is preparation on the Docker host. The acceptance workload
    # itself has no network, inherited credentials, vendor CLI, or model calls.
    with tempfile.TemporaryDirectory(prefix="xorder-python-matrix-") as directory:
        checkout = Path(directory) / "consumer"
        cache = "xorder-python-matrix-" + Path(directory).name
        git_env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        if os.environ.get("CA_CERTIFICATE"):
            git_env.setdefault("GIT_SSL_CAINFO", os.environ["CA_CERTIFICATE"])
        run("git", "-c", "core.hooksPath=/dev/null", "init", "-q", str(checkout), env=git_env)
        run("git", "-C", str(checkout), "fetch", "--depth=1", consumer["repository"],
            consumer["commit"], env=git_env)
        run("git", "-C", str(checkout), "-c", "core.hooksPath=/dev/null", "checkout",
            "--detach", "FETCH_HEAD", env=git_env)
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                         text=True).strip()
        if actual != consumer["commit"]:
            raise RuntimeError("Consumer checkout does not match its committed pin")
        try:
            run("docker", "run", "--rm", "--init", "--network=none",
                "-e", "PUID=" + str(os.getuid()), "-e", "PGID=" + str(os.getgid()),
                "--mount", f"type=bind,src={checkout},dst=/workspace",
                "--mount", f"type=bind,src={FIXTURE},dst=/proof,readonly",
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
