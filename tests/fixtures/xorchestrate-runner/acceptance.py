#!/usr/bin/env python3
"""Real native consumer preparation, including a fresh network-isolated replay."""

import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "examples/xorchestrate/runner.py"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def source(args):
    actual = subprocess.check_output(["git", "-C", str(args.consumer), "rev-parse", "HEAD"], text=True).strip()
    if actual != args.revision:
        raise ValueError("Consumer checkout differs from the selected exact revision")
    return actual


def baseline(args):
    source(args)
    specification = importlib.util.spec_from_file_location("xor_runner", RUNNER)
    runner = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(runner)
    pins = runner.baseline(args.consumer)
    workflow = json.loads((args.consumer / ".github/workflows/ci.yml").read_text())
    checksums = set()

    def visit(value):
        if isinstance(value, dict):
            if value.get("uses", "").startswith("astral-sh/setup-uv@"):
                checksums.add(value.get("with", {}).get("checksum"))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(workflow)
    if len(checksums) != 1 or not isinstance(next(iter(checksums)), str) or len(next(iter(checksums))) != 64:
        raise ValueError("Consumer CI must declare one exact uv checksum")
    return {**pins, "uv_checksum": next(iter(checksums))}


def environment(args):
    # Public dependencies only; do not forward Actions tokens or ambient credentials.
    return {"HOME": str(args.runtime / "home"), "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
            "UV_CACHE_DIR": str(args.runtime / "uv-cache"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}


def bounded_command(argv, env, evidence, *, timeout=480):
    """Let the runner unwind owned child sessions before a bounded kill fallback."""
    started = time.monotonic()
    evidence.update(command=argv, status="failed", cleanup="not_needed")
    process = subprocess.Popen(argv, env=env, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    stdout, stderr = "", ""
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException as error:
            evidence["failure"] = type(error).__name__
            evidence["cleanup"] = "attempted"
            # A second cancellation must not bypass the cleanup already underway.
            previous = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate(timeout=1)
                evidence["cleanup"] = "passed"
            except BaseException:
                evidence["cleanup"] = "failed"
                raise
            finally:
                signal.signal(signal.SIGTERM, previous)
            raise
        evidence["status"] = "passed" if process.returncode == 0 else "failed"
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        evidence.update(returncode=process.poll(), seconds=round(time.monotonic() - started, 3),
                        stdout_tail=stdout[-12000:], stderr_tail=stderr[-12000:])
        process.stdout.close()
        process.stderr.close()


def run(args, phase, command, *, offline=False):
    argv = [args.python, str(RUNNER), command, "--workspace", str(args.consumer),
            "--state-dir", str(args.runtime / ("offline-state" if offline else "online-state")),
            "--python", args.python, "--uv", args.uv, "--tmux", args.tmux,
            "--timeout", "120", "--check-timeout", "60"]
    if offline:
        argv.append("--offline")
    execution = {}
    try:
        completed = bounded_command(argv, environment(args), execution)
    except BaseException:
        write(args.output / (phase + ".json"), execution)
        raise
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        write(args.output / (phase + ".json"), {"returncode": completed.returncode,
              "stdout_tail": completed.stdout[-12000:], "stderr_tail": completed.stderr[-12000:]})
        raise ValueError("Runner did not return a JSON result for " + phase) from error
    write(args.output / (phase + ".json"), result)
    if completed.returncode or result.get("status") != "passed":
        raise ValueError("Native consumer acceptance failed at " + phase)
    return result


def network_evidence(parent):
    namespace = os.readlink("/proc/self/ns/net")
    interfaces = sorted(line.split(":", 1)[0].strip()
                        for line in Path("/proc/net/dev").read_text().splitlines() if ":" in line)
    routes = [line.split() for line in Path("/proc/net/route").read_text().splitlines()[1:]]
    if namespace == parent or interfaces != ["lo"]:
        raise ValueError("Offline replay is not inside its own empty network namespace")
    if any(len(route) > 1 and route[1] == "00000000" for route in routes):
        raise ValueError("Offline namespace still has a default network route")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        error = connection.connect_ex(("1.1.1.1", 443))
    if error not in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
        raise ValueError("Offline namespace did not reject outbound IP communication")
    return {"namespace": namespace, "parent_namespace": parent, "interfaces": interfaces,
            "routes": routes, "outbound_connect_errno": error, "uid": os.geteuid(), "gid": os.getegid()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "run", "offline"))
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--tmux", default="tmux")
    parser.add_argument("--parent-network")
    parser.add_argument("--uid", type=int)
    parser.add_argument("--gid", type=int)
    args = parser.parse_args()
    pins = baseline(args)
    if args.mode == "baseline":
        for key, value in pins.items():
            print(key + "=" + value)
        return
    if args.runtime is None or args.output is None:
        raise ValueError("Acceptance requires explicit external runtime and output directories")
    args.consumer, args.runtime, args.output = (path.resolve() for path in (args.consumer, args.runtime, args.output))
    args.python, args.uv, args.tmux = (shutil.which(value) for value in (args.python, args.uv, args.tmux))
    if not all((args.python, args.uv, args.tmux)):
        raise ValueError("Python, uv and real tmux must be installed")
    args.runtime.mkdir(parents=True, exist_ok=True)
    (args.runtime / "home").mkdir(exist_ok=True)
    manifest = {"schema_version": 1, "consumer_revision": source(args), "baseline": pins,
                "uid": os.geteuid(), "gid": os.getegid(),
                "dependency_sha256": {name: hashlib.sha256((args.consumer / name).read_bytes()).hexdigest()
                    for name in ("pyproject.toml", "uv.lock", ".github/requirements-ci.txt")}}
    if args.mode == "offline":
        if (os.geteuid(), os.getegid()) != (args.uid, args.gid):
            raise ValueError("Offline replay did not drop back to the original user and group")
        write(args.output / "offline-network.json", network_evidence(args.parent_network))
        run(args, "offline-fresh-prepare", "prepare", offline=True)
        run(args, "offline-static-check", "check", offline=True)
        write(args.output / "offline-manifest.json", {**manifest, "status": "passed"})
        return
    run(args, "online-fresh-prepare", "prepare")
    reused = run(args, "online-unchanged-reuse", "prepare")
    if reused.get("preparation") != "reused" or any(
            record.get("name") in {"locked dependency installation", "editable project installation"}
            for record in reused.get("evidence", [])):
        raise ValueError("Unchanged preparation unnecessarily installed dependencies")
    # This is the sole privileged operation: create an empty network namespace,
    # then immediately drop to the original user before executing consumer code.
    uid, gid = os.geteuid(), os.getegid()
    argv = ["sudo", "-n", "unshare", "--net", "--setgid", str(gid), "--setuid", str(uid), "--",
            "/usr/bin/env", "-i", *(key + "=" + value for key, value in environment(args).items()),
            args.python, str(Path(__file__).resolve()), "offline", "--consumer", str(args.consumer),
            "--revision", args.revision, "--runtime", str(args.runtime), "--output", str(args.output),
            "--python", args.python, "--uv", args.uv, "--tmux", args.tmux,
            "--parent-network", os.readlink("/proc/self/ns/net"), "--uid", str(uid), "--gid", str(gid)]
    execution = {}
    try:
        completed = bounded_command(argv, environment(args), execution)
        if completed.returncode:
            raise ValueError("Network-isolated consumer replay failed; see offline launch evidence")
    finally:
        write(args.output / "offline-launch.json", execution)
    manifest.update(status="passed", offline="fresh_cached_environment_network_namespace")
    write(args.output / "manifest.json", manifest)
    print(json.dumps(manifest))


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("Native acceptance interrupted; stopping owned child processes")

    signal.signal(signal.SIGTERM, interrupted)
    main()
