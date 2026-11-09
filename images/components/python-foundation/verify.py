"""Check the shared Python foundation without invoking project or vendor setup."""
import os
from pathlib import Path
import shutil
import subprocess


def main():
    for executable in ("python3", "gcc", "make", "psql", "gosu", "git", "gh", "rg"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"Python foundation omitted {executable}")
    subprocess.run(["python3", "-c", "import sys; assert sys.version_info[:2] == (3, 14)"], check=True)
    subprocess.run(["id", "dev"], check=True)
    if not Path("/usr/local/bin/library-entrypoint").is_file() or not Path("/workspace").is_dir():
        raise RuntimeError("Python foundation omitted the workspace entrypoint contract")
    if os.environ.get("HOME") != "/home/dev":
        raise RuntimeError("Python foundation HOME differs from the image contract")


if __name__ == "__main__":
    main()
