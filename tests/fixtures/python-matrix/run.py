#!/usr/bin/env python3
"""Exercise every preinstalled interpreter and the pinned consumer's real tmux."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile


def sqlite_check(expected_line):
    actual = ".".join(map(str, sys.version_info[:2]))
    if actual != expected_line:
        raise RuntimeError(f"Expected Python {expected_line}, executed {actual}")
    with tempfile.TemporaryDirectory(prefix="xorder-sqlite-") as directory:
        database = Path(directory) / "wal.sqlite"
        writer = sqlite3.connect(database)
        try:
            mode = writer.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode != "wal":
                raise RuntimeError(f"SQLite did not enter WAL mode: {mode}")
            writer.execute("CREATE TABLE proof (value INTEGER NOT NULL)")
            writer.execute("INSERT INTO proof VALUES (42)")
            writer.commit()
            # Keep the writer open so the URI reader must observe a real WAL.
            if not Path(str(database) + "-wal").is_file():
                raise RuntimeError("SQLite did not create a WAL file")
            reader = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            try:
                if reader.execute("SELECT value FROM proof").fetchone() != (42,):
                    raise RuntimeError("URI read-only connection could not read WAL data")
                try:
                    reader.execute("INSERT INTO proof VALUES (99)")
                except sqlite3.OperationalError as error:
                    if "readonly" not in str(error).lower():
                        raise
                else:
                    raise RuntimeError("URI read-only connection accepted a write")
            finally:
                reader.close()
        finally:
            writer.close()
    return {"python": platform.python_version(), "executable": sys.executable,
            "sqlite": sqlite3.sqlite_version,
            "checks": ["interpreter-line", "wal", "uri-read-only-wal", "writes-rejected"]}


def command(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-only", metavar="PYTHON_LINE")
    args = parser.parse_args()
    if args.sqlite_only:
        print(json.dumps(sqlite_check(args.sqlite_only), sort_keys=True))
        return
    fixture = Path(__file__).resolve().parent
    consumer = json.loads((fixture / "consumer.json").read_text())
    versions = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
    output = Path("/evidence")
    evidence = {"consumer": consumer, "network": "none", "interpreters": {}}
    for line in consumer["python_lines"]:
        executable = shutil.which("python" + line)
        if not executable:
            raise RuntimeError("Missing preinstalled interpreter python" + line)
        facts = json.loads(subprocess.check_output(
            [executable, str(Path(__file__).resolve()), "--sqlite-only", line], text=True))
        if facts["python"] != versions[line]:
            raise RuntimeError(f"Python {line} does not match its build pin: {facts}")
        if Path(executable).resolve().is_relative_to(Path("/home/dev")):
            raise RuntimeError("Interpreter was installed in the persistent home volume")
        with tempfile.TemporaryDirectory(prefix="xorder-venv-" + line + "-") as directory:
            venv = Path(directory) / "venv"
            command(executable, "-m", "venv", str(venv))
            command(str(venv / "bin/python"), "-m", "pip", "--version")
        facts["checks"].append("offline-venv-with-pip")
        # Temporary selection/report paths cannot accidentally reuse a preceding
        # interpreter's run. sys.executable propagates into consumer subprocesses.
        with tempfile.TemporaryDirectory(prefix="xorder-contracts-" + line + "-") as directory:
            selection = Path(directory) / "selection.json"
            report = output / ("contracts-" + line + ".json")
            command(executable, "scripts/ci/select_checks.py", "--event", "workflow_dispatch",
                    "--selection-file", str(selection))
            command(executable, "scripts/ci/run_contracts.py", "--selection", str(selection),
                    "--report", str(report), env=dict(os.environ, PYTHONPATH="src"))
            census = json.loads(report.read_text())
            expected = consumer["contract_count"]
            if (not census["full"] or not census["required_exercised"]
                    or any(census[key] for key in ("skipped", "not_run", "failures", "errors",
                                                   "expected_failures", "unexpected_successes"))
                    or any(census[key] != expected for key in ("collected", "started", "executed"))):
                raise RuntimeError(f"Incomplete contract acceptance for Python {line}: {census}")
            facts["contracts"] = {key: census[key] for key in
                                  ("collected", "started", "executed", "duration_seconds")}
        evidence["interpreters"][line] = facts
    with tempfile.TemporaryDirectory(prefix="xorder-native-") as directory:
        executable = Path(directory) / "native-proof"
        command("cc", "/native-check.c", "-o", str(executable))
        command(str(executable))
    evidence["checks"] = ["native-compiler"]
    tmux = subprocess.check_output(["tmux", "-V"], text=True).strip()
    if not tmux.startswith("tmux 3."):
        raise RuntimeError("Expected tmux 3.x, observed " + tmux)
    checks = json.loads(subprocess.check_output(
        ["python3.14", "scripts/testing/live_tmux.py", "self-check"], text=True))
    if not checks or not all(value is True for value in checks.values()):
        raise RuntimeError(f"Real tmux self-check did not pass every check: {checks}")
    evidence["tmux"] = {"version": tmux, "self_check": checks}
    (output / "acceptance.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
