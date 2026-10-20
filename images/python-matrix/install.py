#!/usr/bin/env python3
"""Preinstall exact compatibility interpreters outside persisted user storage."""
import json
import os
from pathlib import Path
import shutil
import subprocess

pins = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
env = {**os.environ, "UV_PYTHON_INSTALL_DIR": "/opt/xorder/python",
       "UV_CACHE_DIR": "/tmp/python-matrix-install-cache"}
# Install all selected patches independently of the parent's default Python.
# Keep /usr/local/bin/python* and its pip environment intact across refreshes.
subprocess.run(["uv", "python", "install", "--no-bin", *pins.values()], env=env, check=True)
bin_directory = Path("/opt/xorder/python-bin")
bin_directory.mkdir(parents=True)
for minor, expected in pins.items():
    installed = subprocess.check_output(
        ["uv", "python", "find", "--managed-python", "--no-project", expected],
        env={**env, "UV_PYTHON_DOWNLOADS": "never"}, text=True).strip()
    executable = bin_directory / f"python{minor}"
    executable.symlink_to(installed)
    actual = subprocess.check_output(
        [str(executable), "-c", "import platform, sqlite3; print(platform.python_version())"],
        text=True).strip()
    if actual != expected:
        raise SystemExit(f"Python {minor}: expected {expected}, observed {actual}")
shutil.rmtree(env["UV_CACHE_DIR"], ignore_errors=True)
