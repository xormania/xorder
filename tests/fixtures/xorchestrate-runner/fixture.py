"""Offline consumer contract fixture; real subprocesses and a real virtualenv."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib
import venv


def record(stage, **details):
    with Path(os.environ["XR_FIXTURE_LOG"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"stage": stage, **details}) + "\n")


def failure(stage):
    if os.environ.get("XR_FIXTURE_FAIL") == stage:
        print("fixture " + stage + " failed: package retrieval unavailable", file=sys.stderr)
        raise SystemExit(31)
    if os.environ.get("XR_FIXTURE_BLOCK") == stage:
        Path(os.environ["XR_FIXTURE_BLOCKED"]).write_text(stage, encoding="utf-8")
        time.sleep(30)


def expected_version(root):
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return next(value.split("==", 1)[1] for value in project["dependency-groups"]["validation"]
                if value.startswith("zizmor=="))


def scanner():
    version = sys.argv[2]
    if "--version" in sys.argv[3:]:
        print("zizmor " + version)
        return
    record("scanner", version=version, arguments=sys.argv[3:])
    failure("scanner")
    if any("deliberate-fault" in value for value in sys.argv[3:]):
        print("fixture finding: dangerous workflow")
        raise SystemExit(1)
    print("[]")


def uv():
    arguments = sys.argv[2:]
    if arguments == ["--version"]:
        print("uv 0.13.7")
        return
    if arguments[:2] == ["python", "find"]:
        print(sys.executable)
        return
    stage = "sync" if arguments[0] == "sync" else "install"
    environment = Path(os.environ["UV_PROJECT_ENVIRONMENT"])
    record(stage, arguments=arguments, environment=str(environment), workspace=str(Path.cwd()))
    failure(stage)
    if not (environment / "bin/python").exists():
        venv.EnvBuilder(with_pip=False).create(environment)
    if stage != "sync":
        return
    version = expected_version(Path.cwd())
    installed = environment / ".fixture-zizmor-installed"
    # A resolver can consider an installed distribution satisfied even when its
    # executable is missing or corrupt. Repair must explicitly reinstall it.
    if installed.exists() and installed.read_text(encoding="utf-8") == version and "--reinstall-package" not in arguments:
        return
    installed.write_text(version, encoding="utf-8")
    executable = environment / "bin/zizmor"
    executable.write_text(
        "#!" + sys.executable + " -S\n"
        "import os,sys\n"
        "os.execv(sys.executable, [sys.executable, '-S', " + repr(str(Path(__file__).resolve()))
        + ", 'scanner', " + repr(version) + ", *sys.argv[1:]])\n", encoding="utf-8")
    executable.chmod(0o755)


def setup(profile_path, *, root, install=True, overrides=None, **unused):
    profile_path = Path(profile_path)
    record("setup", install=install, profile=str(profile_path))
    failure("setup")
    values = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    values.update(overrides or {})
    values.setdefault("schema_version", 1)
    values.setdefault("mode", "protocol-fixture")
    values.setdefault("suite", "static")
    values.setdefault("environment", str(profile_path.parent / "environment"))
    values.setdefault("interpreter", str(Path(values["environment"]) / "bin/python"))
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(values), encoding="utf-8")
    return {"status": "passed", "profile": str(profile_path), "interpreter": values["interpreter"]}


def proof():
    arguments = sys.argv[2:]
    action = arguments[0]
    profile_path = Path(arguments[arguments.index("--profile") + 1])
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    interpreter = Path(profile["interpreter"])
    record(action, profile=str(profile_path), arguments=arguments)
    failure(action)
    scanner_path = interpreter.with_name("zizmor")
    if not scanner_path.is_file() or not os.access(scanner_path, os.X_OK):
        print(json.dumps({"status": "failed", "reason": "selected scanner missing"}))
        raise SystemExit(1)
    result = subprocess.run([str(scanner_path), "--version"], capture_output=True, text=True, check=False)
    if result.returncode or result.stdout.strip() != "zizmor " + expected_version(Path.cwd()):
        print(json.dumps({"status": "failed", "reason": "selected scanner wrong version"}))
        raise SystemExit(1)
    if action == "run":
        failure("check")
        subprocess.run([str(scanner_path), "clean-workflow.yml"], check=True)
    print(json.dumps({"status": "passed"}))


def controls():
    record("controls", arguments=sys.argv[1:])
    failure("controls")
    if "--collect-only" in os.environ.get("PYTEST_ADDOPTS", ""):
        print("2 tests collected; no scanner execution")
        return
    executable = Path(sys.executable).with_name("zizmor")
    version = subprocess.run([str(executable), "--version"], capture_output=True, text=True, check=True)
    if version.stdout.strip() != "zizmor " + expected_version(Path.cwd()):
        raise SystemExit(1)
    clean = subprocess.run([str(executable), "clean-workflow.yml"], capture_output=True, check=False)
    fault = subprocess.run([str(executable), "deliberate-fault.yml"], capture_output=True, check=False)
    if clean.returncode != 0 or fault.returncode == 0:
        raise SystemExit(1)
    print("2 passed")


def tmux():
    """Version identity only; real terminal behavior has a separate acceptance test."""
    arguments = sys.argv[2:]
    if arguments == ["-V"]:
        print("tmux 3.6a")
        return
    raise ValueError("The tmux fixture supplies version identity only")


def native():
    """Orchestration fixture output, never evidence of real host capabilities."""
    record("native")
    failure("native")
    version = subprocess.run([sys.argv[1], "-V"], capture_output=True, text=True, check=True)
    print(json.dumps({"status": "passed", "fixture": True, "tmux_version": version.stdout.strip(),
                      "scope": "runner preparation behavior only"}))


def main(stage=None):
    stage = stage or sys.argv[1]
    if stage == "uv":
        uv()
    elif stage == "scanner":
        scanner()
    elif stage == "dependencies":
        record("consistency", arguments=sys.argv[1:])
        failure("consistency")
        if (Path.cwd() / ".inconsistent").exists():
            print("fixture dependency export is stale", file=sys.stderr)
            raise SystemExit(1)
    elif stage == "proof":
        proof()
    elif stage == "controls":
        controls()
    elif stage == "tmux":
        tmux()
    elif stage == "native":
        native()
    else:
        raise ValueError("unknown fixture stage " + stage)


if __name__ == "__main__":
    main()
