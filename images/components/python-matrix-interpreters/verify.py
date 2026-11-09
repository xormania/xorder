"""Exercise every pinned managed interpreter without permitting a download."""
import json
import os
from pathlib import Path
import subprocess


def main():
    pins = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
    bootstrap = json.loads(Path("/opt/xorder/python-matrix/pip-bootstrap.json").read_text())
    environment = dict(os.environ, UV_PYTHON_DOWNLOADS="never")
    for minor, expected in pins.items():
        executable = "/opt/xorder/python-bin/python" + minor
        observed = subprocess.check_output(
            [executable, "-I", "-c", "import ensurepip,platform,sqlite3,pip; import pip._vendor.certifi as certifi; "
             "print(platform.python_version()); print(sqlite3.sqlite_version); "
             "print(pip.__version__); print(ensurepip.version()); print(certifi.__version__)"],
            text=True, env=environment).splitlines()
        if len(observed) != 5 or observed[0] != expected or not observed[1]:
            raise RuntimeError(f"Managed Python {minor} differs from its pinned SQLite-enabled interpreter")
        def version(value):
            return tuple(map(int, value.split(".")))
        if (any(version(value) < version(bootstrap["version"]) for value in observed[2:4])
                or version(observed[4]) < version(bootstrap["certifi_min_version"])):
            raise RuntimeError(f"Managed Python {minor} has a vulnerable pip/bootstrap dependency")


if __name__ == "__main__":
    main()
