#!/usr/bin/env python3
"""Prepare an owned native Xorchestrate validation environment from its own lock."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import tomllib


INPUTS = (
    "pyproject.toml", "uv.lock", ".github/requirements-ci.txt",
    "scripts/ci/dependencies.py", "scripts/proof.sh",
    "scripts/testkit/adapters/profiles.py", "scripts/testkit/adapters/static.py",
    "tests/hexagonal/test_workflow_security.py", "tests/hexagonal/support/static_checks.py",
    "xorchestrate/adapters/telemetry_collector/sqlite.py",
)
CONTROLS = (
    "tests/hexagonal/test_workflow_security.py::test_real_pinned_zizmor_accepts_a_clean_minimal_workflow_with_complete_inputs",
    "tests/hexagonal/test_workflow_security.py::test_real_pinned_zizmor_detects_a_deliberate_template_injection_without_republishing_it",
)
PYTHON_FACTS = """import hashlib,importlib.metadata,json,platform,sqlite3,sys
packages=sorted((d.metadata['Name'],d.version,d.read_text('direct_url.json') or '')
                for d in importlib.metadata.distributions())
print(json.dumps({'version':platform.python_version(),'executable':sys.executable,
 'prefix':sys.prefix,'base_prefix':sys.base_prefix,'cache_tag':sys.implementation.cache_tag,
 'sqlite_version':sqlite3.sqlite_version,
 'packages':hashlib.sha256(json.dumps(packages).encode()).hexdigest()}))
"""
SETUP = """import json,sys
from scripts.testkit.adapters.profiles import setup
state,root=sys.argv[1:]
from pathlib import Path
state=Path(state)
print(json.dumps(setup(state/'profile.json',root=root,install=False,overrides={
 'suite':'static','environment':str(state/'environment'),
 'interpreter':str(state/'environment/bin/python'),'output':str(state/'runs')})))
"""
SQLITE = """import json,sqlite3
from xorchestrate.adapters.telemetry_collector.sqlite import require_sqlite
require_sqlite()
print(json.dumps({'sqlite_version':sqlite3.sqlite_version,'project_gate':'passed'}))
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"Refusing redirected state file: {path}")
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def write_json(path, value):
    if path.is_symlink() or path.with_suffix(".tmp").is_symlink():
        raise ValueError(f"Refusing redirected state file: {path}")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def redact(value):
    value = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", value)
    value = re.sub(r"(?i)([?&](?:token|key|password|signature|secret)=)[^\s&]+", r"\1[redacted]", value)
    for name, secret in os.environ.items():
        if re.search("TOKEN|PASSWORD|SECRET|AUTHORIZATION", name.upper()) and len(secret) >= 8:
            value = value.replace(secret, "[redacted]")
    return value


class Commands:
    def __init__(self, workspace, env):
        self.workspace, self.env, self.evidence = workspace, env, []

    def run(self, name, argv, timeout, *, required=True):
        """Bound process lifetime, descendants and retained output; never use a shell."""
        started = time.monotonic()
        record = {"name": name, "command": [str(a) for a in argv], "status": "failed"}
        self.evidence.append(record)
        tail = bytearray()
        process = None
        try:
            process = subprocess.Popen(argv, cwd=self.workspace, env=self.env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError(f"{name} exceeded {timeout:g} seconds")
                    for key, _ in selector.select(min(remaining, 0.1)):
                        block = os.read(key.fd, 8192)
                        if not block:
                            selector.unregister(key.fileobj)
                        else:
                            tail.extend(block)
                            del tail[:-12000]
                process.wait(timeout=max(0.01, timeout - (time.monotonic() - started)))
            record["returncode"] = process.returncode
            record["status"] = "passed" if process.returncode == 0 else "failed"
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                process.stdout.close()
            record["seconds"] = round(time.monotonic() - started, 3)
            record["output_tail"] = redact(tail.decode(errors="replace"))
        if required and record["status"] != "passed":
            raise ValueError(f"{name} failed; see bounded command evidence")
        return record

    def json(self, name, argv, timeout=15):
        return json.loads(self.run(name, argv, timeout)["output_tail"])


def executable(value):
    found = shutil.which(value)
    if not found:
        raise ValueError(f"Required executable is unavailable: {value}")
    return str(Path(found).absolute())


def baseline(workspace):
    """Read the consumer's current JSON-formatted workflow; never duplicate its pins."""
    source = workspace / ".github/workflows/ci.yml"
    if not source.is_file() or source.is_symlink():
        raise ValueError("Project CI baseline is missing or redirected")
    pins = {"actions/setup-python": set(), "astral-sh/setup-uv": set()}

    def visit(value):
        if isinstance(value, dict):
            action = value.get("uses", "").split("@", 1)[0]
            if action in pins:
                field = "python-version" if action == "actions/setup-python" else "version"
                pins[action].add(value.get("with", {}).get(field))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(json.loads(source.read_text()))
    if any(len(values) != 1 or not isinstance(next(iter(values)), str)
           or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", next(iter(values))) for values in pins.values()):
        raise ValueError("Project CI must select one exact Python version and one exact uv version")
    return {"python": next(iter(pins["actions/setup-python"])),
            "uv": next(iter(pins["astral-sh/setup-uv"]))}


def identity(args, commands):
    sources = {}
    for relative in INPUTS:
        path = args.workspace / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Required project input is missing or redirected: {relative}")
        sources[relative] = sha(path)
    declaration = tomllib.loads((args.workspace / "pyproject.toml").read_text())
    pins = [item.split("==", 1)[1] for item in declaration["dependency-groups"]["validation"]
            if isinstance(item, str) and item.startswith("zizmor==")]
    if len(pins) != 1 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pins[0]):
        raise ValueError("The project must declare one exact Zizmor validation pin")
    python = commands.json("bootstrap interpreter", [args.python, "-I", "-B", "-c", PYTHON_FACTS])
    selected_baseline = baseline(args.workspace)
    if python["version"] != selected_baseline["python"]:
        raise ValueError("Select the project's CI Python " + selected_baseline["python"]
                         + "; observed " + python["version"])
    # Distribution state of the bootstrap is irrelevant to the owned environment.
    python.pop("packages")
    uv = commands.run("uv version", [args.uv, "--version"], 15)["output_tail"].strip()
    if re.fullmatch(r"uv " + re.escape(selected_baseline["uv"]) + r"(?: \([^\r\n]+\))?", uv) is None:
        raise ValueError("Select the project's CI uv " + selected_baseline["uv"] + "; observed " + uv)
    tmux = commands.run("tmux version", [args.tmux, "-V"], 15)["output_tail"].strip()
    return {"schema_version": 1, "workspace": str(args.workspace),
            "environment": str(args.state_dir / "environment"), "inputs": sources,
            "runner": sha(Path(__file__)), "python": python,
            "python_sha256": sha(Path(args.python).resolve()), "uv": uv,
            "uv_sha256": sha(Path(args.uv).resolve()), "uv_path": args.uv,
            "tmux": tmux, "tmux_path": args.tmux, "tmux_sha256": sha(Path(args.tmux).resolve()),
            "native_probe_sha256": sha(Path(__file__).with_name("native.py")),
            "target": {"system": platform.system(), "machine": platform.machine()}, "baseline": selected_baseline,
            "zizmor_version": pins[0]}


def environment_facts(args, commands, expected):
    interpreter = args.state_dir / "environment/bin/python"
    scanner = interpreter.with_name("zizmor")
    if not interpreter.is_file() or not scanner.is_file() or not os.access(scanner, os.X_OK):
        raise ValueError("Selected environment lacks Python or its sibling Zizmor executable")
    facts = commands.json("selected interpreter", [str(interpreter), "-I", "-B", "-c", PYTHON_FACTS])
    if facts["prefix"] == facts["base_prefix"] or Path(facts["prefix"]).resolve() != args.state_dir / "environment":
        raise ValueError("Selected interpreter must belong to the owned virtual environment")
    reported = commands.run("selected Zizmor version", [str(scanner), "--version"], 15)["output_tail"].strip()
    if reported != "zizmor " + expected["zizmor_version"]:
        raise ValueError("Selected Zizmor version differs from the project's exact validation pin")
    return {"python": facts, "zizmor_sha256": sha(scanner), "zizmor_version": reported}


def profile_identity(args, *, required=True):
    path = args.state_dir / "profile.json"
    profile = read_json(path)
    if not profile and not required:
        return None
    selected = {"environment": str(args.state_dir / "environment"),
                "interpreter": str(args.state_dir / "environment/bin/python"),
                "output": str(args.state_dir / "runs"), "mode": "protocol-fixture"}
    if any(profile.get(key) != value for key, value in selected.items()):
        raise ValueError("Profile no longer selects the owned environment, output and protocol-fixture mode; "
                         "restore its selections or choose a new empty state directory")
    return sha(path)


def check_paths(args):
    if platform.system() != "Linux":
        raise ValueError("This native runner supports Linux and WSL2")
    args.workspace = args.workspace.expanduser().resolve(strict=True)
    if args.state_dir.is_symlink():
        raise ValueError("State directory must not be a symlink")
    args.state_dir = args.state_dir.expanduser().resolve()
    if (args.state_dir == args.workspace or args.state_dir.is_relative_to(args.workspace)
            or args.workspace.is_relative_to(args.state_dir)):
        raise ValueError("Select a state directory outside the project checkout")
    for name in ("environment", "pycache", "runs", "controls", "native.json", "profile.json", "owner.json", "receipt.json", "attempt.json", ".lock"):
        if (args.state_dir / name).is_symlink():
            raise ValueError(f"Refusing redirected owned state: {name}")
    args.python, args.uv, args.tmux = executable(args.python), executable(args.uv), executable(args.tmux)


@contextmanager
def owned_state(args):
    state = args.state_dir
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / ".lock").open("a+b") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another operation owns this selected state; wait for it to finish") from error
        owner = read_json(state / "owner.json")
        if owner:
            if owner != {"workspace": str(args.workspace)}:
                raise ValueError("State belongs to another workspace; select its own state directory")
        else:
            if set(p.name for p in state.iterdir()) != {".lock"}:
                raise ValueError("State directory is not empty and has no Xorder ownership record")
            state.chmod(0o700)
            write_json(state / "owner.json", {"workspace": str(args.workspace)})
        yield


def doctor(args, commands, *, required=True):
    return commands.run("project doctor", ["bash", str(args.workspace / "scripts/proof.sh"),
                        "doctor", "--profile", str(args.state_dir / "profile.json"), "--suite", "static"],
                        args.check_timeout, required=required)


def inspect(args, commands, current):
    if read_json(args.state_dir / "owner.json") != {"workspace": str(args.workspace)}:
        raise ValueError("No preparation is owned here for this workspace")
    receipt = read_json(args.state_dir / "receipt.json")
    attempt = read_json(args.state_dir / "attempt.json")
    if attempt.get("status") != "passed" or receipt.get("identity") != current:
        raise ValueError("Preparation is absent, interrupted, failed or stale")
    if profile_identity(args) != receipt.get("profile_sha256"):
        raise ValueError("Managed profile changed after verification; rerun prepare")
    if environment_facts(args, commands, current) != receipt.get("environment"):
        raise ValueError("Selected environment changed after verification")
    return receipt


def perform(args, commands, result):
    current = identity(args, commands)
    if args.command == "status":
        receipt = inspect(args, commands, current)
        result.update(status="passed", preparation="reused", readiness="previously_passed",
                      check="not_executed", receipt=str(args.state_dir / "receipt.json"),
                      verified_at=receipt["verified_at"])
        return
    with owned_state(args):
        profile_identity(args, required=False)
        reusable = False
        try:
            inspect(args, commands, current)
            reusable = True
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            pass
        # Written before any project hook: SIGKILL cannot leave old success usable.
        write_json(args.state_dir / "attempt.json", {"status": "running", "action": args.command})
        try:
            commands.run("project dependency consistency", [args.python, "-m", "scripts.ci.dependencies", "check", "--uv", args.uv,
                         *(("--offline",) if args.offline else ())], args.timeout)
            if args.command == "prepare":
                if reusable:
                    reusable = doctor(args, commands, required=False)["status"] == "passed"
                if not reusable:
                    result["preparation"] = "attempted"
                    for options in (("--only-group", "validation"),
                                    ("--no-default-groups", "--group", "validation", "--extra", "test")):
                        repair = ["--reinstall-package", "zizmor"] if options[0] == "--only-group" else []
                        commands.run("locked dependency installation", [args.uv, "sync", "--locked", *options,
                                     *repair, "--no-install-project", "--no-python-downloads", "--python", args.python], args.timeout)
                    commands.run("editable project installation", [args.uv, "pip", "install", "--python",
                                 str(args.state_dir / "environment/bin/python"), "--no-deps", "--no-build-isolation",
                                 "-e", str(args.workspace)], args.timeout)
                    commands.run("project profile setup", [str(args.state_dir / "environment/bin/python"), "-c", SETUP,
                                 str(args.state_dir), str(args.workspace)], args.timeout)
                result["preparation"] = "reused" if reusable else "succeeded"
            else:
                if not reusable:
                    raise ValueError("Preparation is not current; run prepare for this selected state first")
                result["preparation"] = "reused"
            result["readiness"] = "attempted"
            doctor(args, commands)
            selected = environment_facts(args, commands, current)
            commands.run("project SQLite WAL version gate", [str(args.state_dir / "environment/bin/python"), "-c", SQLITE], 15)
            commands.run("native terminal operations", [str(args.state_dir / "environment/bin/python"),
                         str(Path(__file__).with_name("native.py")), args.tmux], min(args.check_timeout, 30))
            result["readiness"] = "passed"
            result["check"] = "attempted"
            if args.command == "prepare":
                commands.run("real scanner clean and fault controls", [str(args.state_dir / "environment/bin/python"),
                             "-m", "pytest", "-p", "no:cacheprovider", "--basetemp", str(args.state_dir / "controls"),
                             "-q", *CONTROLS], args.check_timeout)
            else:
                commands.run("project static checks", ["bash", str(args.workspace / "scripts/proof.sh"), "run",
                             "--profile", str(args.state_dir / "profile.json"), "--suite", "static",
                             "--check-timeout", str(args.check_timeout)], args.timeout)
            result["check"] = "passed"
            # Reject a dependency edit or executable replacement during preparation.
            if identity(args, commands) != current or environment_facts(args, commands, current) != selected:
                raise ValueError("Inputs or selected environment changed during verification; rerun prepare")
            receipt = {"identity": current, "environment": selected, "verified_at": time.time(),
                       "profile_sha256": profile_identity(args),
                       "readiness": "passed", "check": "passed", "evidence": commands.evidence}
            write_json(args.state_dir / "receipt.json", receipt)
            write_json(args.state_dir / "attempt.json", {"status": "passed", "action": args.command})
            result.update(status="passed", receipt=str(args.state_dir / "receipt.json"))
        except BaseException:
            write_json(args.state_dir / "attempt.json", {"status": "failed", "action": args.command,
                       "evidence": commands.evidence})
            raise


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "status", "check"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True, help="exclusive owned directory outside the checkout")
    parser.add_argument("--python", default=sys.executable, help="installed Python >=3.12 executable; no runtime download")
    parser.add_argument("--uv", default="uv", help="installed uv executable; the project owns tool selection")
    parser.add_argument("--tmux", default="tmux", help="installed real tmux for private native readiness checks")
    parser.add_argument("--offline", action="store_true", help="forbid uv downloads; requires already cached locked packages and Git source")
    parser.add_argument("--timeout", type=float, default=600, help="seconds per preparation/static-run command")
    parser.add_argument("--check-timeout", type=float, default=60, help="seconds for doctor/scanner controls and individual static checks")
    args = parser.parse_args(argv)
    result = {"status": "not_ready" if args.command == "status" else "failed",
              "preparation": "not_attempted", "readiness": "not_executed", "check": "not_executed"}
    commands = None
    try:
        if not (0 < args.timeout <= 1800 and 0 < args.check_timeout <= 600):
            raise ValueError("Timeouts must be positive; maximum preparation 1800s and check 600s")
        check_paths(args)
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(args.state_dir / "environment"),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(args.state_dir / "pycache"),
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                   PROOF_PYTHON=str(args.state_dir / "environment/bin/python"))
        if args.offline:
            env["UV_OFFLINE"] = "true"
        # Ignore ambient project/venv selection; explicit workspace/environment own this run.
        for name in ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT", "UV_WORKING_DIRECTORY",
                     "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "BASH_ENV", "ENV", "TMUX", "TMUX_TMPDIR"):
            env.pop(name, None)
        commands = Commands(args.workspace, env)
        perform(args, commands, result)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, InterruptedError, KeyboardInterrupt) as error:
        result["reason"] = redact(str(error))
        if result["preparation"] == "attempted":
            result["preparation"] = "failed"
        if result["readiness"] == "attempted":
            result["readiness"] = "failed"
        if result["check"] == "attempted":
            result["check"] = "failed"
        result["recovery"] = "Correct the reported prerequisite/input failure, then rerun prepare with the same workspace and state directory."
    result["evidence"] = commands.evidence if commands else []
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("Preparation interrupted; selected state requires verification")

    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
