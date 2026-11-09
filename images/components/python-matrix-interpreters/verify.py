"""Exercise every pinned managed interpreter without permitting a download."""
import json
import os
from pathlib import Path
import subprocess


def main():
    pins = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
    environment = dict(os.environ, UV_PYTHON_DOWNLOADS="never")
    for minor, expected in pins.items():
        executable = "/opt/xorder/python-bin/python" + minor
        observed = subprocess.check_output(
            [executable, "-c", "import platform, sqlite3; print(platform.python_version()); print(sqlite3.sqlite_version)"],
            text=True, env=environment).splitlines()
        if len(observed) != 2 or observed[0] != expected or not observed[1]:
            raise RuntimeError(f"Managed Python {minor} differs from its pinned SQLite-enabled interpreter")


if __name__ == "__main__":
    main()
