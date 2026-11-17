#!/usr/bin/env python3
"""Exercise image-owned subjects with every preinstalled interpreter offline."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile


PYTHON_LINES = ("3.10", "3.12", "3.14")


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
    return subprocess.run(args, check=True, timeout=90, **kwargs)


def wheel_fixture(destination):
    """Build a tiny deterministic wheel without a build backend or downloads."""
    files = {"xorder_image_probe.py": "VALUE = 42\n",
             "xorder_image_probe-1.0.0.dist-info/METADATA":
                 "Metadata-Version: 2.1\nName: xorder-image-probe\nVersion: 1.0.0\n",
             "xorder_image_probe-1.0.0.dist-info/WHEEL":
                 "Wheel-Version: 1.0\nGenerator: xorder\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    record = "xorder_image_probe-1.0.0.dist-info/RECORD"
    files[record] = "".join(path + ",,\n" for path in (*files, record))
    with zipfile.ZipFile(destination, "w") as archive:
        for path, contents in files.items():
            archive.writestr(zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0)), contents)


def pip_check(executable, pin):
    """Measure the pip that this interpreter or newly created venv executes."""
    facts = json.loads(subprocess.check_output([
        str(executable), "-I", "-c",
        "import ensurepip,json,pip,ssl; import pip._vendor.certifi as certifi; "
        "context=ssl.create_default_context(cafile=certifi.where()); "
        "print(json.dumps(dict(pip=pip.__version__, ensurepip=ensurepip.version(), "
        "certifi=certifi.__version__, ca_count=context.cert_store_stats()['x509_ca'])))"], text=True, timeout=30))
    def version(value):
        return tuple(map(int, value.split(".")))
    if (version(facts["pip"]) < version(pin["version"])
            or version(facts["ensurepip"]) < version(pin["version"])
            or version(facts["certifi"]) < version(pin["certifi_min_version"])
            or facts["ca_count"] <= 0):
        raise RuntimeError(f"Python pip/bootstrap security floor failed: {facts}")
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-only", metavar="PYTHON_LINE")
    args = parser.parse_args()
    if args.sqlite_only:
        print(json.dumps(sqlite_check(args.sqlite_only), sort_keys=True))
        return
    versions = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
    bootstrap = json.loads(Path("/opt/xorder/python-matrix/pip-bootstrap.json").read_text())
    output = Path("/evidence")
    if set(versions) != set(PYTHON_LINES):
        raise RuntimeError("Installed matrix pins do not match the advertised interpreter lines")
    evidence = {"schema_version": 2, "fixture": "xorder-python-image-capabilities",
                "network": "none", "interpreters": {}}
    for line in PYTHON_LINES:
        executable = shutil.which("python" + line)
        if not executable:
            raise RuntimeError("Missing preinstalled interpreter python" + line)
        facts = json.loads(subprocess.check_output(
            [executable, str(Path(__file__).resolve()), "--sqlite-only", line], text=True, timeout=30))
        if facts["python"] != versions[line]:
            raise RuntimeError(f"Python {line} does not match its build pin: {facts}")
        if any(Path(executable).resolve().is_relative_to(Path(path))
               for path in ("/home/dev", "/workspace")):
            raise RuntimeError("Interpreter was installed under a runtime mount")
        facts["installed_pip"] = pip_check(executable, bootstrap)
        with tempfile.TemporaryDirectory(prefix="xorder-venv-" + line + "-") as directory:
            venv = Path(directory) / "venv"
            command(executable, "-m", "venv", str(venv))
            command(str(venv / "bin/python"), "-m", "pip", "--version")
            facts["fresh_venv_pip"] = pip_check(venv / "bin/python", bootstrap)
            wheel = Path(directory) / "xorder_image_probe-1.0.0-py3-none-any.whl"
            wheel_fixture(wheel)
            command(str(venv / "bin/python"), "-m", "pip", "--isolated", "install",
                    "--no-index", "--no-deps", "--disable-pip-version-check", str(wheel))
            command(str(venv / "bin/python"), "-I", "-c",
                    "import xorder_image_probe; assert xorder_image_probe.VALUE == 42")
        facts["checks"].append("offline-venv-with-pip")
        facts["checks"].extend(["installed-pip-vendored-certifi", "offline-venv-security-floor"])
        facts["checks"].append("offline-wheel-install-and-import")
        facts["native_runtime"] = json.loads(subprocess.check_output(
            [executable, "-I", "/runtime/check.py"], text=True, timeout=90))
        evidence["interpreters"][line] = facts
    with tempfile.TemporaryDirectory(prefix="xorder-native-") as directory:
        executable = Path(directory) / "native-proof"
        command("cc", "/native-check.c", "-o", str(executable))
        command(str(executable))
    evidence["checks"] = ["native-compiler"]
    (output / "acceptance.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
