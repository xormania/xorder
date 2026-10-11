#!/usr/bin/env python3
"""Run an xorder project profile against an explicit checkout."""
import os
from pathlib import Path
import sys

if len(sys.argv) < 3:
    raise SystemExit("Usage: xr.py WORKSPACE up|seed|status|sync|plant|test|cache|gc|phpunit|php-tests|exec|logs|down [arguments]")
os.environ["WORKSPACE"] = str(Path(sys.argv[1]).resolve(strict=True))
runner = Path(__file__).resolve().parents[1] / "examples/uxor/run.sh"
os.execvp("bash", ["bash", str(runner), *sys.argv[2:]])
