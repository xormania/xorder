"""Auditable Playwright invocations; the caller owns the heavy-run lease."""
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile

from runtime import resources, state_root


LIMIT = 65536
PROBE = "console.log(JSON.stringify({demo_url:process.env.DEMO_URL||null,extension_reporter:process.env.PW_TEST_REPORTER||null,cwd:process.cwd(),environment_sha256:require('node:crypto').createHash('sha256').update(JSON.stringify(Object.entries(process.env).sort())).digest('hex')}))"


class UnsafeTestCancellation(subprocess.CalledProcessError):
    plant_cleanup_safe = False

    def __init__(self):
        super().__init__(130, "Playwright test", stderr="Container test cancellation could not be confirmed. Keep the plant recovery journal and stop the test payload before restoring source.\n")


def parse_test_options(arguments, env):
    """Remove only xorder's options; retain the consumer's Playwright arguments."""
    remaining = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            remaining.extend(arguments[index:])
            break
        if argument == "--measure":
            env["XORDER_TEST_MEASURE"] = "1"
        elif argument == "--attest-server":
            env["XORDER_TEST_ATTEST_SERVER"] = "1"
        elif argument == "--wait" or argument.startswith("--wait="):
            wait = argument.partition("=")[2] if "=" in argument else "600"
            if argument == "--wait" and index + 1 < len(arguments):
                try:
                    float(arguments[index + 1])
                except ValueError:
                    pass
                else:
                    index += 1
                    wait = arguments[index]
            try:
                number = float(wait)
            except ValueError as error:
                raise ValueError("--wait must be a finite nonnegative number of seconds") from error
            if not math.isfinite(number) or number < 0:
                raise ValueError("--wait must be a finite nonnegative number of seconds")
            env["XORDER_TEST_WAIT_SECONDS"] = wait
        else:
            remaining.append(argument)
        index += 1
    return remaining


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def project_sources(workspace, env):
    """Include current TS specs/config and all other tracked/nonignored bytes."""
    if (workspace / ".git").exists():
        names = subprocess.check_output(["git", "-C", str(workspace), "ls-files", "-z",
                                         "--cached", "--others", "--exclude-standard"], env=env).decode().split("\0")
        files = [workspace / name for name in sorted(set(names)) if name]
    else:
        files = []
        for directory, subdirectories, filenames in os.walk(workspace):
            subdirectories[:] = sorted(name for name in subdirectories
                                      if name not in (".git", "node_modules", "vendor", "var", ".cache", "__pycache__"))
            files.extend(Path(directory) / name for name in sorted(filenames))
    result = hashlib.sha256()
    for path in files:
        name = path.relative_to(workspace).as_posix()
        result.update(name.encode() + b"\0")
        if path.is_symlink():
            result.update(b"symlink\0" + os.readlink(path).encode())
        elif path.is_file():
            with path.open("rb") as source:
                while block := source.read(1024 * 1024):
                    result.update(block)
        else:
            result.update(b"missing")
        result.update(b"\0")
    return result.hexdigest()


def exec_command(compose, env, *arguments, overrides=None):
    forwarded = [item for key, value in (overrides or {}).items() for item in ("-e", key + "=" + value)]
    return [*compose, "exec", "-T", "--user", f'{env["PUID"]}:{env["PGID"]}',
            "-w", "/app", *forwarded, "php", *arguments]


def observe(command, env):
    result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False, timeout=30)
    if result.returncode:
        raise ValueError("observation command failed")
    return result.stdout


def stack_snapshot(compose, env, project):
    configuration = observe([*compose, "config", "--format", "json"], env)
    ids = observe(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project], env).split()
    containers = json.loads(observe(["docker", "inspect", *ids], env)) if ids else []
    identities = [{"id": item.get("Id"), "image_id": item.get("Image"),
                   "image_reference": item.get("Config", {}).get("Image"),
                   "service": item.get("Config", {}).get("Labels", {}).get("com.docker.compose.service")}
                  for item in containers]
    # The effective Compose document may contain proxy credentials. Retain its
    # hash, not its raw environment or reporter options.
    return {"configuration_sha256": hashlib.sha256(configuration.encode()).hexdigest(),
            "containers": sorted(identities, key=lambda item: item["id"] or "")}


def parse_events(text):
    events = []
    for line in text.splitlines():
        if line.strip():
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise ValueError("Invalid reporter event")
            events.append(event)
    return events


def evidence(events):
    begins = [event for event in events if event.get("event") == "begin"]
    attempts = [event for event in events if event.get("event") == "test_end"]
    running = {(event.get("id"), event.get("retry")): event for event in events if event.get("event") == "test_begin"}
    for attempt in attempts:
        running.pop((attempt.get("id"), attempt.get("retry")), None)
    attempts.extend(dict(event, status="interrupted_or_unknown") for event in running.values())
    endings = [event for event in events if event.get("event") == "end"]
    return {"observer_status": "complete" if endings else "incomplete" if events else "unavailable",
            "resolved_projects": begins[-1].get("projects", []) if begins else [],
            "container_demo_url": begins[-1].get("demo_url") if begins else None,
            "observed_test_attempts": attempts,
            "selected_test_count": begins[-1].get("selected_test_count") if begins else None,
            "playwright_status": endings[-1].get("status") if endings else None,
            "resolved_playwright_config_sha256": begins[-1].get("configuration_sha256") if begins else None,
            "actual_navigation_urls": {"status": "unknown", "reason": "Reporter project baseURL proves resolved configuration; it does not observe page requests or test-level fixture overrides."}}


def tail(path):
    with path.open("rb") as source:
        source.seek(max(0, path.stat().st_size - LIMIT))
        return source.read().decode(errors="replace")


def trace_urls(content):
    """Read observed request/frame URLs, never requested page.goto parameters."""
    if len(content) > 64 * 1024**2:
        raise ValueError("Trace exceeds the receipt observation size limit")
    requests, frames = set(), set()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = [item for item in archive.infolist() if item.filename.endswith((".network", ".trace"))]
        if sum(item.file_size for item in entries) > 64 * 1024**2:
            raise ValueError("Trace event files exceed the receipt observation size limit")
        for entry in entries:
            for line in archive.read(entry).decode().splitlines():
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Invalid trace event")
                if event.get("type") == "resource-snapshot":
                    url = event.get("snapshot", {}).get("request", {}).get("url")
                    if isinstance(url, str):
                        requests.add(url)
                elif event.get("type") == "frame-snapshot":
                    url = event.get("snapshot", {}).get("frameUrl")
                    if isinstance(url, str):
                        frames.add(url)
    return {"request_urls": sorted(requests), "frame_urls": sorted(frames)}


def collect_trace_urls(compose, env, attempts, errors):
    observed = []
    for attempt in attempts:
        for attachment in attempt.get("trace_attachments", []):
            path = attachment.get("path")
            if not isinstance(path, str) or not path:
                continue
            try:
                size = observe(exec_command(compose, env, "node", "-e", "console.log(require('fs').statSync(process.argv[1]).size)", path), env)
                if int(size) > 64 * 1024**2:
                    raise ValueError("Trace too large")
                result = subprocess.run(exec_command(compose, env, "cat", path), env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
                if result.returncode:
                    raise ValueError("Trace unavailable")
                urls = trace_urls(result.stdout)
                observed.append({"test_id": attempt.get("id"), "retry": attempt.get("retry"),
                                 "trace_path": path, "trace_sha256": hashlib.sha256(result.stdout).hexdigest(), **urls})
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError):
                errors.append("A reported trace could not establish request URLs")
    if observed:
        return {"status": "observed" if any(item["request_urls"] or item["frame_urls"] for item in observed) else "unknown",
                "source": "Playwright trace request/frame snapshots", "attempts": observed,
                "coverage": "Only attempts and requests retained by the reported trace attachments; absence is not proof of no navigation."}
    return {"status": "unknown", "reason": "No readable trace attachment established actual request or frame URLs."}


def write_once(path, value):
    with path.open("x") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    path.chmod(0o400)


def capped_workers(arguments, budget, cpus):
    """Normalize every Playwright worker spelling before filters' -- separator."""
    if budget is None:
        return list(arguments)
    remaining, requested = [], []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            remaining.extend(arguments[index:])
            break
        value = None
        if argument in ("--workers", "-j"):
            index += 1
            if index >= len(arguments):
                raise ValueError(argument + " needs a positive worker count or percentage")
            value = arguments[index]
        elif argument.startswith("--workers="):
            value = argument.partition("=")[2]
        elif argument.startswith("-j") and len(argument) > 2:
            value = argument[2:].removeprefix("=")
        if value is None:
            remaining.append(argument)
        else:
            try:
                if value.endswith("%"):
                    percentage = float(value[:-1])
                    if not math.isfinite(percentage) or percentage <= 0:
                        raise ValueError()
                    count = max(1, math.floor(cpus * percentage / 100))
                else:
                    count = int(value)
                    if str(count) != value or count < 1:
                        raise ValueError()
            except (ValueError, OverflowError) as error:
                raise ValueError("Worker setting must be a positive integer or percentage") from error
            requested.append((value, count))
        index += 1
    desired = requested[-1][1] if requested else budget
    effective = min(desired, budget)
    if requested and desired > budget:
        print(f"Worker request {requested[-1][0]} capped to host worker budget {budget}", flush=True)
    return [f"--workers={effective}", *remaining]


def run_test(compose, env, workspace, project, arguments, workers=None, input_fingerprint=None):
    arguments = list(arguments)
    requested = list(arguments)
    attest = env.get("XORDER_TEST_ATTEST_SERVER", "0")
    if attest not in ("0", "1"):
        raise ValueError("XORDER_TEST_ATTEST_SERVER must be 0 or 1")
    if attest == "1":
        explicit_trace = None
        for index, argument in enumerate(arguments):
            if argument == "--trace":
                explicit_trace = arguments[index + 1] if index + 1 < len(arguments) else ""
            elif argument.startswith("--trace="):
                explicit_trace = argument.partition("=")[2]
        if explicit_trace is not None and explicit_trace != "on":
            raise ValueError("--attest-server requires --trace=on; remove the conflicting explicit trace mode")
        if explicit_trace is None:
            arguments.insert(0, "--trace=on")
    arguments = capped_workers(arguments, workers, resources(workspace)["cpus"])
    run_id = uuid.uuid4().hex
    folder = state_root(env) / "test-attempts" / run_id
    folder.mkdir(parents=True, mode=0o700)
    errors = []
    facts = {"schema_version": 1, "run_id": run_id, "workspace": str(workspace), "project": project,
             "requested_arguments": requested, "effective_arguments": arguments,
             "image_reference": env.get("IMAGE"), "browser_reference": env.get("BROWSER_IMAGE"),
             "automatic_worker_budget": workers,
             "plant_name": env.get("XORDER_PLANT_NAME"),
             "server_attestation_requested": attest == "1",
             "measurement_requested": env.get("XORDER_TEST_MEASURE", "0") == "1"}
    try:
        facts["stack"] = stack_snapshot(compose, env, project)
    except (OSError, ValueError, subprocess.SubprocessError):
        errors.append("Effective stack observation unavailable")
    try:
        facts["source_sha256"] = project_sources(workspace, env)
    except (OSError, subprocess.SubprocessError):
        errors.append("Project source fingerprint unavailable")
    facts["workspace_profile_sha256"] = input_fingerprint
    probe = {}
    try:
        probe = json.loads(observe(exec_command(compose, env, "node", "-e", PROBE), env))
        if not isinstance(probe, dict):
            raise ValueError("Invalid container environment observation")
    except (OSError, ValueError, subprocess.SubprocessError):
        probe = {}
        errors.append("Container test environment observation unavailable")
    facts["container_environment"] = {"demo_url": probe.get("demo_url"), "cwd": probe.get("cwd"),
                                       "sha256": probe.get("environment_sha256")}
    control = f"/app/demo/var/xorder/test-attempts/{run_id}"
    overrides = {"XORDER_TEST_CONTROL_DIR": control, "npm_config_update_notifier": "false"}
    observer_enabled = "extension_reporter" in probe and not probe.get("extension_reporter")
    if not observer_enabled:
        errors.append("Existing PW_TEST_REPORTER preserved; companion observer unavailable")
    else:
        overrides.update(PW_TEST_REPORTER="/run/xorder/receipt-reporter.cjs",
                         XORDER_TEST_EVENT_FILE=control + "/events.jsonl")
    command = exec_command(compose, env, "node", "/run/xorder/receipt-launcher.cjs", *arguments, overrides=overrides)
    fingerprint_inputs = {"arguments": arguments, "project": project,
                                     "stack": facts.get("stack"), "sources": facts.get("source_sha256"),
                                     "profile": input_fingerprint, "environment": facts["container_environment"],
                                     "image": facts["image_reference"], "browser": facts["browser_reference"],
                          "host_environment": digest(dict(env)),
                          "measurement": facts["measurement_requested"]}
    facts["started_at"] = utc()
    facts["host_start"] = resources(workspace)
    started = time.monotonic()
    process = None
    exit_code = 64
    cancellation_safe = True
    try:
        with (folder / "test-output.log").open("wb") as output:
            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while block := process.stdout.read1(65536):
                output.write(block)
                stream = getattr(sys.stdout, "buffer", None)
                if stream is None:
                    sys.stdout.write(block.decode(errors="replace"))
                else:
                    stream.write(block)
                sys.stdout.flush()
            exit_code = process.wait()
    except KeyboardInterrupt:
        try:
            # Stop the in-container process group before allowing a plant's
            # finally block to restore files. Killing only Docker's client can
            # leave the payload (and its global setup) running.
            observe(exec_command(compose, env, "node", "/run/xorder/receipt-launcher.cjs", "--stop", control), env)
        except (OSError, ValueError, subprocess.SubprocessError):
            cancellation_safe = False
            errors.append("Container test cancellation could not be confirmed; plant restoration is unsafe")
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        exit_code = 130
        errors.append("Test invocation interrupted")
    except OSError:
        errors.append("Test process could not start or output capture failed")
        if process is not None and process.poll() is None:
            try:
                observe(exec_command(compose, env, "node", "/run/xorder/receipt-launcher.cjs", "--stop", control), env)
            except (OSError, ValueError, subprocess.SubprocessError):
                cancellation_safe = False
                errors.append("Container test cancellation could not be confirmed; plant restoration is unsafe")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()
    try:
        finalize_attempt(compose, env, workspace, folder, facts, started, exit_code, errors,
                         observer_enabled, overrides, fingerprint_inputs)
    except Exception:
        # Reporting failures (including a full disk) must not replace a test's
        # exit status or prevent cancellation safety from reaching the caller.
        try:
            print("Run receipt unavailable: finalization failed; original test exit retained", flush=True)
        except OSError:
            pass
    if not cancellation_safe:
        raise UnsafeTestCancellation()
    return exit_code


def finalize_attempt(compose, env, workspace, folder, facts, started, exit_code, errors, observer_enabled, overrides, fingerprint_inputs):
    facts.update(ended_at=utc(), host_end=resources(workspace), elapsed_seconds=time.monotonic() - started,
                 exit_code=exit_code)
    events = []
    if observer_enabled:
        try:
            content = observe(exec_command(compose, env, "cat", overrides["XORDER_TEST_EVENT_FILE"]), env)
            (folder / "events.jsonl").write_text(content)
            events = parse_events(content)
        except (OSError, ValueError, subprocess.SubprocessError):
            errors.append("Companion reporter events unavailable or invalid")
    facts.update(evidence(events))
    facts["actual_navigation_urls"] = collect_trace_urls(compose, env, facts["observed_test_attempts"], errors)
    fingerprint_inputs["playwright_configuration"] = facts["resolved_playwright_config_sha256"]
    facts["input_sha256"] = digest(fingerprint_inputs)
    log_path = folder / "server.log"
    try:
        logs = observe([*compose, "logs", "--no-color", "--timestamps", "--since", facts["started_at"],
                        "--until", facts["ended_at"], "php", "browser"], env)
        log_path.write_text(logs)
    except (OSError, ValueError, subprocess.SubprocessError):
        errors.append("Server logs for the test time window unavailable or could not be saved")
    output_path = folder / "test-output.log"
    facts["diagnostic_context"] = {}
    for name, path in (("test_output", output_path), ("server_logs", log_path)):
        try:
            facts["diagnostic_context"][name] = tail(path)
        except OSError:
            facts["diagnostic_context"][name] = ""
            errors.append(name + " diagnostic context unavailable")
    facts["artifacts"] = {"test_output": str(output_path), "server_logs": str(log_path),
                          "events": str(folder / "events.jsonl") if events else None}
    facts["observation_errors"] = errors
    receipt_path = folder / "receipt.json"
    try:
        write_once(receipt_path, facts)
    except OSError:
        print("Run receipt unavailable: could not save the completed attempt; original test exit retained", flush=True)
        return None
    print(f"Run receipt: {receipt_path}", flush=True)
    print(f"Full test output: {output_path}", flush=True)
    if facts["observer_status"] != "complete":
        print("Run receipt observer: " + facts["observer_status"] + "; executed tests and resolved server URLs may be unknown", flush=True)
    if exit_code and env.get("XORDER_TEST_FAILURE_HOOK"):
        try:
            from failure_hooks import run_failure_hook
            advice = run_failure_hook(receipt_path, env)
        except Exception:
            advice = {"status": "unavailable", "reason": "Failure hook unavailable"}
        try:
            write_once(folder / "advisory.json", advice)
        except OSError:
            pass
        print("Failure hook advisory: " + str(advice.get("status", "unknown")), flush=True)
    return receipt_path
