#!/usr/bin/env python3
"""Opt-in, vendor-neutral agent observations with independent task postchecks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 2 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_bytes(path):
    """Evidence is a bounded regular file inside the isolated run workspace."""
    if path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError("Missing, redirected or oversized evidence file")
    return path.read_bytes()


def read_json(path):
    return json.loads(file_bytes(path))


def command(argv, cwd, env, timeout, capture_limit=16384):
    """Drain output with bounded memory; terminate the entire process group."""
    streams = [{"bytes": 0, "hash": hashlib.sha256(), "prefix": bytearray()} for _ in range(2)]

    def drain(pipe, facts):
        try:
            while block := pipe.read(8192):
                facts["bytes"] += len(block)
                facts["hash"].update(block)
                facts["prefix"].extend(block[:max(0, capture_limit - len(facts["prefix"]))])
        finally:
            pipe.close()

    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    readers = [threading.Thread(target=drain, args=(pipe, facts), daemon=True)
               for pipe, facts in zip((process.stdout, process.stderr), streams)]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        # Also stop background descendants after a successful adapter return.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                break
            if sig == signal.SIGTERM and process.poll() is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
        process.wait(timeout=3)
        for reader in readers:
            reader.join(timeout=3)
    return {"exit_code": process.returncode, "timed_out": timed_out,
            "stdout": bytes(streams[0]["prefix"]), "stderr": bytes(streams[1]["prefix"]),
            "output": [{"bytes": item["bytes"], "sha256": item["hash"].hexdigest()} for item in streams]}


def safe_version(value, env):
    value = value.decode("utf-8", errors="replace").strip().splitlines()
    value = value[0][:256] if value else ""
    for key, secret in env.items():
        if re.search(r"TOKEN|SECRET|PASSWORD|API_KEY|COOKIE|AUTH", key, re.I) and len(secret) >= 4:
            value = value.replace(secret, "[redacted]")
    value = re.sub(r"(?i)(bearer\s+|(?:token|password|api[_-]?key)\s*[=:]\s*)\S+", r"\1[redacted]", value)
    return value or None


def adapter_config(path):
    value = read_json(path)
    if not isinstance(value, dict) or set(value) - {"name", "command", "version_command", "harness", "model"}:
        raise ValueError("Invalid adapter configuration")
    for key in ("name", "harness", "model"):
        if not isinstance(value.get(key), str) or not 0 < len(value[key]) <= 128:
            raise ValueError("Adapter must declare name, harness and configured model")
    for key in ("command", "version_command"):
        argv = value.get(key)
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in argv):
            raise ValueError("Adapter command and version_command must be nonempty argv arrays")
    return value


def source_snapshot(root, commit):
    revision = subprocess.check_output(["git", "rev-parse", "--verify", commit + "^{commit}"],
                                       cwd=root, text=True, timeout=10).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Invalid evaluated source revision")

    def blob(relative):
        return subprocess.check_output(["git", "show", revision + ":" + relative], cwd=root, timeout=10,
                                       stderr=subprocess.DEVNULL)

    catalog_bytes = blob("catalog-v2.json")
    return {"commit": revision, "url": "https://github.com/xormania/xorder/tree/" + revision,
            "catalog_sha256": digest(catalog_bytes), "catalog": json.loads(catalog_bytes), "blob": blob}


def resource_for(scenario, source):
    eligible = [entry for entry in source["catalog"]["resources"]
                if entry["id"] == scenario["resource_id"] and entry["lifecycle"] == "available"
                and entry["verification"]["status"] == "passed" and "linux/amd64" in entry["targets"]]
    if not eligible:
        raise ValueError("No accepted resource for this scenario")
    return max(eligible, key=lambda entry: tuple(map(int, entry["version"].split("."))))


def disk_observation(workspace):
    total = 0
    for folder, dirs, files in os.walk(workspace, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(folder) / name).is_symlink()]
        for name in files:
            path = Path(folder) / name
            if not path.is_symlink() and path.is_file():
                total += path.stat().st_size
    return {"workspace_file_bytes": total, "filesystem_free_bytes": shutil.disk_usage(workspace).free,
            "loadavg": list(os.getloadavg()) if hasattr(os, "getloadavg") else None}


def discovered(workspace, source, resource):
    expected = {"catalog-v2.json": source["blob"]("catalog-v2.json"),
                "README.md": source["blob"]("README.md"),
                "usage.md": source["blob"](resource["documentation"])}
    checks = []
    for name, content in expected.items():
        path = workspace / "evidence" / name
        checks.append({"name": "downloaded-" + name, "passed": file_bytes(path) == content})
    result = read_json(workspace / "result.json")
    checks.append({"name": "available-exact-selection", "passed": all(
        result.get(key) == resource[reference] for key, reference in (
            ("resource_id", "id"), ("identity", "identity"), ("version", "version"), ("documentation", "documentation")) )})
    checks.append({"name": "readiness-recipe", "passed": result.get("readiness_command") == [
        "bash", "scripts/verify-image.sh", resource["id"][len("image/"):], resource["identity"]]})
    return checks, result


def docker_json(arguments, workspace, env):
    result = command(["docker", *arguments], workspace, env, 20, capture_limit=MAX_FILE)
    if result["timed_out"] or result["exit_code"]:
        raise ValueError("Docker evidence inspection unavailable")
    return json.loads(result["stdout"])


def docker_operation(argv):
    """Resolve observed Docker operations; ambiguous CLI input is not evidence."""
    if not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv):
        return None
    valued = {"--context", "-c", "--host", "-H", "--config", "--log-level", "-l",
              "--tlscacert", "--tlscert", "--tlskey"}
    booleans = {"--debug", "-D", "--tls", "--tlsverify"}
    special = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        flag, equals, value = arg.partition("=")
        if arg == "--":
            index += 1
            break
        if not arg.startswith("-"):
            break
        if flag in valued:
            if equals:
                if not value:
                    return None
            else:
                index += 1
                if index >= len(argv) or not argv[index] or argv[index].startswith("-"):
                    return None
        elif flag in booleans:
            if equals and value not in {"true", "false"}:
                return None
        elif arg in {"--help", "-h", "--version", "-v"}:
            special = "help" if arg in {"--help", "-h"} else "version"
        else:
            return None
        index += 1
    if special:
        return special
    if index >= len(argv):
        return None
    operation = argv[index]
    trailing = argv[index + 1:]
    if operation == "info":
        index = 0
        while index < len(trailing):
            flag, equals, value = trailing[index].partition("=")
            if flag in {"--help", "-h"}:
                if not equals or value == "true":
                    return "help"
                if value != "false":
                    return None
            elif flag in {"--format", "-f"}:
                if equals:
                    if not value:
                        return None
                else:
                    index += 1
                    if index >= len(trailing) or not trailing[index]:
                        return None
            else:
                return None
            index += 1
        return "info"
    if operation in {"info", "version", "help", "ps", "inspect", "logs", "stats"}:
        return operation
    readonly = {"context": {"show", "ls", "list", "inspect"},
                "image": {"ls", "list", "inspect", "history"},
                "container": {"ls", "list", "inspect", "logs", "stats"},
                "system": {"df"}}
    if operation in readonly and trailing and trailing[0] in readonly[operation]:
        return operation + " " + trailing[0]
    return None


def postchecks(scenario, workspace, source, resource, context, env):
    checks, result = discovered(workspace, source, resource)
    if scenario["check"] == "missing-prerequisite":
        observed = [docker_operation(json.loads(line)) for line in file_bytes(workspace / "docker-trace.jsonl").decode().splitlines()]
        checks += [{"name": "engine-checked-before-pull", "passed": "info" in observed and None not in observed},
                   {"name": "precise-recovery-report", "passed": result.get("status") == "blocked" and
                    result.get("blocker") == "docker-engine" and result.get("next_command") == ["docker", "info"]}]
    elif scenario["check"] == "first-task":
        container = docker_json(["inspect", context["container_name"]], workspace, env)[0]
        config, state = container["Config"], container["State"]
        checks += [{"name": "exact-image-executed", "passed": config["Image"] == resource["identity"] and
                    config.get("Labels", {}).get("xorder.agent-eval") == context["run_id"] and
                    state["Status"] == "exited" and state["ExitCode"] == 0},
                   {"name": "supplied-fixture-unchanged", "passed": digest(file_bytes(workspace / "fixture/task.php")) == context["fixture_sha256"]}]
        image = docker_json(["image", "inspect", resource["identity"]], workspace, env)[0]
        checks.append({"name": "task-container-policy", "passed": config.get("Cmd") == ["php", "/evaluation/task.php"] and
                       config.get("User") == "1000:1000" and
                       config.get("Entrypoint") == image["Config"].get("Entrypoint") and
                       image.get("Architecture") == "amd64" and image.get("Os") == "linux" and
                       container["HostConfig"].get("NetworkMode") == "none" and
                       container["HostConfig"].get("ReadonlyRootfs") is True and any(
                           mount.get("Source") == str(workspace / "fixture") and mount.get("Destination") == "/evaluation" and
                           mount.get("RW") is False for mount in container.get("Mounts", []))})
        output = docker_json(["logs", context["container_name"]], workspace, env)
        checks.append({"name": "php-task-output", "passed": output == {"nonce": context["nonce"], "requirements_met": True}})
    elif scenario["check"] == "warm-reuse":
        for name in ("scripts/xr.py", context["seed_source_file"]):
            checks.append({"name": "source-helper-" + name, "passed":
                           file_bytes(workspace / "checkout" / name) == source["blob"](name)})
        for name, expected in context["seed_files"].items():
            source_file, receiving_file = workspace / "donor" / name, workspace / "receiver" / name
            try:
                matches = file_bytes(source_file) == expected.encode() and file_bytes(receiving_file) == expected.encode()
                donor, receiver = source_file.stat(), receiving_file.stat()
                private = (donor.st_dev, donor.st_ino) != (receiver.st_dev, receiver.st_ino)
            except (OSError, ValueError):
                matches = private = False
            checks.append({"name": "reused-" + name, "passed": matches})
            checks.append({"name": "private-copy-" + name, "passed": private})
        checks.append({"name": "checkout-state-preserved", "passed":
                       not (workspace / "receiver/demo/var").exists() and
                       file_bytes(workspace / "receiver/keep.txt") == b"receiver-owned\n"})
    return checks


def prepare(scenario, workspace, context, env):
    (workspace / "evidence").mkdir()
    (workspace / "tmp").mkdir()
    env.update(TMPDIR=str(workspace / "tmp"), XORDER_EVAL_WORKSPACE=str(workspace),
               XORDER_EVAL_RESULT=str(workspace / "result.json"), XORDER_EVAL_PROMPT=str(workspace / "prompt.txt"))
    if scenario["check"] == "missing-prerequisite":
        folder = workspace / "bin"
        folder.mkdir()
        shim = folder / "docker"
        shim.write_text("#!" + sys.executable + "\nimport json,os,re,sys\nfrom pathlib import Path\n"
                        "args=sys.argv[1:]\n"
                        "for index,arg in enumerate(args):\n"
                        "    for key,value in os.environ.items():\n"
                        "        if re.search(r'TOKEN|SECRET|PASSWORD|API_KEY|COOKIE|AUTH',key,re.I) and len(value)>=4:\n"
                        "            arg=arg.replace(value,'[redacted]')\n"
                        "    if index and args[index-1] in ('--password','-p'):\n"
                        "        arg='[redacted]'\n"
                        "    arg=re.sub(r'(?i)((?:token|secret|password|api[_-]?key|cookie|auth)[^=\\s]*=).*',r'\\1[redacted]',arg)\n"
                        "    args[index]=arg\n"
                        "with Path(os.environ['XORDER_EVAL_DOCKER_TRACE']).open('a') as trace:\n"
                        "    trace.write(json.dumps(args) + '\\n')\n"
                        "print('Controlled evaluation: Docker engine unavailable', file=sys.stderr)\nsys.exit(125)\n")
        shim.chmod(0o755)
        env.update(PATH=str(folder) + os.pathsep + env.get("PATH", ""),
                   XORDER_EVAL_DOCKER_TRACE=str(workspace / "docker-trace.jsonl"))
    if scenario["check"] == "first-task":
        (workspace / "fixture").mkdir()
        fixture = ("<?php\n$met = PHP_VERSION_ID >= 80500 && extension_loaded('intl') && "
                   "extension_loaded('curl') && extension_loaded('zip');\n"
                   "echo json_encode(['nonce' => '" + context["nonce"] + "', 'requirements_met' => $met]);\n"
                   "exit($met ? 0 : 2);\n")
        (workspace / "fixture/task.php").write_text(fixture)
        context["fixture_sha256"] = digest(fixture.encode())
    if scenario["check"] == "warm-reuse":
        inputs = {"package.json": '{"name":"xorder-evaluation","private":true}\n',
                  "package-lock.json": '{"lockfileVersion":3,"packages":{}}\n',
                  "demo/composer.json": '{"name":"xorder/evaluation","require":{}}\n',
                  "demo/composer.lock": '{"packages":[],"packages-dev":[]}\n'}
        dependencies = {"demo/vendor/prepared.txt": context["nonce"] + "-composer-fixture\n",
                        "node_modules/prepared.txt": context["nonce"] + "-npm-fixture\n"}
        for checkout in ("donor", "receiver"):
            for name, value in inputs.items():
                target = workspace / checkout / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value)
        for name, value in dependencies.items():
            target = workspace / "donor" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value)
        (workspace / "donor/demo/var").mkdir()
        (workspace / "donor/demo/var/must-not-transfer.txt").write_text("donor-runtime-state\n")
        (workspace / "receiver/keep.txt").write_text("receiver-owned\n")
        context["seed_files"] = inputs | dependencies


def clean_container(context, workspace, env):
    try:
        data = docker_json(["inspect", context["container_name"]], workspace, env)
        if data[0]["Config"].get("Labels", {}).get("xorder.agent-eval") == context["run_id"]:
            result = command(["docker", "rm", "-f", context["container_name"]], workspace, env, 20)
            return result["exit_code"] == 0 and not result["timed_out"]
    except (OSError, ValueError, KeyError, IndexError):
        return False
    return False


def validate_observation(value, root=ROOT):
    Draft202012Validator(read_json(root / "schemas/agent-observation.schema.json"),
                         format_checker=FormatChecker(formats=["date-time", "uri"])).validate(value)
    if value["outcome"] == "pass":
        if not value["checks"] or not all(item["passed"] for item in value["checks"]):
            raise ValueError("Pass requires successful independent postchecks")
        execution = value["execution"]
        if not execution or execution["exit_code"] != 0 or execution["timed_out"]:
            raise ValueError("Pass requires a completed successful adapter execution")
    if not value["source"]["url"].endswith("/tree/" + value["source"]["commit"]):
        raise ValueError("Source URL must bind the evaluated commit")
    return value


def run(scenario_path, adapter_path, output, source_commit="HEAD", timeout=None, human_interventions=None, root=ROOT):
    scenario = read_json(scenario_path)
    if scenario.get("check") not in {"discovery", "first-task", "missing-prerequisite", "warm-reuse"}:
        raise ValueError("Unknown scenario check")
    adapter = adapter_config(adapter_path)
    source = source_snapshot(root, source_commit)
    resource = resource_for(scenario, source)
    deadline = timeout if timeout is not None else scenario["timeout_seconds"]
    if not isinstance(deadline, (int, float)) or not 0 < deadline <= 3600:
        raise ValueError("Scenario deadline must be between 0 and 3600 seconds")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Observation output already exists; choose a new path")
    run_id = uuid.uuid4().hex
    workspace = output.parent / ("agent-eval-" + run_id)
    workspace.mkdir(mode=0o700)
    context = {"run_id": run_id, "nonce": uuid.uuid4().hex, "container_name": "xorder-eval-" + run_id,
               "workspace": str(workspace), "source_url": source["url"]}
    env = dict(os.environ)
    prepare(scenario, workspace, context, env)
    task = scenario["task"]
    for key, value in context.items():
        task = task.replace("{" + key + "}", str(value))
    (workspace / "prompt.txt").write_text(task + "\n", encoding="utf-8")
    observation = {"schema_version": 1, "kind": "real-agent-observation", "run_id": run_id,
                   "scenario": {"id": scenario["id"], "sha256": digest(file_bytes(scenario_path)), "check": scenario["check"]},
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "source": {key: source[key] for key in ("commit", "url", "catalog_sha256")},
                   "resource": {key: resource[key] for key in ("id", "version", "identity", "verification")},
                   "harness": {"adapter": adapter["name"], "name": adapter["harness"], "version": None,
                               "model_configured": adapter["model"], "model_observed": None},
                   "workspace": str(workspace), "outcome": "indeterminate", "reason": "harness-unavailable", "checks": [],
                   "metrics": {"human_interventions": human_interventions, "download_bytes": None,
                               "download_measurement": "not-measured", "before": disk_observation(workspace)},
                   "execution": None, "cleanup": {"process_group": "not-started", "container": "not-applicable"}}
    started = time.monotonic()
    adapter_started = False
    try:
        if scenario["check"] == "warm-reuse":
            try:
                source["blob"]("examples/uxor/seed.py")
                context["seed_source_file"] = "examples/uxor/seed.py"
            except subprocess.CalledProcessError:
                observation["reason"] = "source-seed-helper-unavailable"
                raise PrerequisiteUnavailable()
        version = command(adapter["version_command"], workspace, env, min(deadline, 15))
        if not version["timed_out"] and not version["exit_code"]:
            observation["harness"]["version"] = safe_version(version["stdout"], env)
        if scenario["check"] == "first-task":
            probe = command(["docker", "info"], workspace, env, 20)
            if probe["timed_out"] or probe["exit_code"]:
                observation["reason"] = "docker-engine-unavailable"
                raise PrerequisiteUnavailable()
        argv = [arg.replace("{prompt}", str(workspace / "prompt.txt")).replace("{workspace}", str(workspace))
                .replace("{result}", str(workspace / "result.json")) for arg in adapter["command"]]
        adapter_started = True
        execution = command(argv, workspace, env, deadline)
        observation["cleanup"]["process_group"] = "terminated"
        observation["execution"] = {key: execution[key] for key in ("exit_code", "timed_out", "output")}
        if execution["timed_out"]:
            observation["outcome"], observation["reason"] = "fail", "scenario-deadline-exceeded"
        elif execution["exit_code"]:
            observation["outcome"], observation["reason"] = "indeterminate", "adapter-exited-unsuccessfully"
        else:
            try:
                observation["checks"] = postchecks(scenario, workspace, source, resource, context, env)
                passed = all(item["passed"] for item in observation["checks"])
                observation["outcome"], observation["reason"] = ("pass", "postchecks-passed") if passed else ("fail", "postchecks-failed")
            except (OSError, ValueError, KeyError, IndexError):
                observation["outcome"], observation["reason"] = "fail", "missing-or-invalid-task-evidence"
    except PrerequisiteUnavailable:
        pass
    except KeyboardInterrupt:
        observation["outcome"], observation["reason"] = "indeterminate", "operator-interrupted"
        observation["cleanup"]["process_group"] = "terminated"
    except FileNotFoundError:
        observation["reason"] = "harness-or-prerequisite-command-unavailable"
    finally:
        if scenario["check"] == "first-task" and adapter_started:
            observation["cleanup"]["container"] = "removed" if clean_container(context, workspace, env) else "not-found-or-cleanup-unconfirmed"
    return finish(observation, output, workspace, started)


class PrerequisiteUnavailable(Exception):
    """The requested execution surface is unavailable; no agent failure is inferred."""


def finish(observation, output, workspace, started):
    observation["metrics"].update(elapsed_seconds=round(time.monotonic() - started, 4), after=disk_observation(workspace))
    observation["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    validate_observation(observation)
    with output.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(observation, indent=2, sort_keys=True) + "\n")
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    runner = sub.add_parser("run", help="Run an explicitly configured real harness in an isolated directory")
    runner.add_argument("scenario", type=Path)
    runner.add_argument("--adapter", required=True, type=Path)
    runner.add_argument("--output", required=True, type=Path)
    runner.add_argument("--source-commit", default="HEAD")
    runner.add_argument("--timeout", type=float)
    runner.add_argument("--human-interventions", type=int)
    validator = sub.add_parser("validate", help="Validate observation structure; this does not replay its evidence")
    validator.add_argument("observation", type=Path)
    args = parser.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    if args.action == "validate":
        validate_observation(read_json(args.observation))
        print("Observation structure valid; evidence has not been replayed.")
        return 0
    if args.human_interventions is not None and args.human_interventions < 0:
        parser.error("human interventions must be nonnegative")
    value = run(args.scenario.resolve(), args.adapter.resolve(), args.output, args.source_commit,
                args.timeout, args.human_interventions)
    print(value["outcome"] + ": " + value["reason"] + " (" + str(args.output.resolve()) + ")")
    return {"pass": 0, "fail": 1, "indeterminate": 2}[value["outcome"]]  # nosec B105 # outcome key, not a credential


if __name__ == "__main__":
    raise SystemExit(main())
