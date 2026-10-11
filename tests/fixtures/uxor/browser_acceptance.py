#!/usr/bin/env python3
"""Bounded three-engine behavior and isolated real child-OOM acceptance."""
from contextlib import redirect_stdout
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
CONFIG_NAME = "xorder.cross-browser.config.ts"
PROJECTS = ("acceptance-chromium", "acceptance-firefox", "acceptance-webkit")
DEFAULT_LIMIT = 4 * 1024**3
OOM_LIMIT = 512 * 1024**2

CONFIGURATION = """import { defineConfig } from '@playwright/test';
import upstream from './playwright.config';

const smoke = upstream.projects?.find(project => project.name === 'smoke');
if (!smoke) throw new Error('Reviewed consumer smoke project is missing');

export default defineConfig({
  ...upstream,
  projects: (['chromium', 'firefox', 'webkit'] as const).map(browserName => ({
    ...smoke,
    name: `acceptance-${browserName}`,
    use: { ...smoke.use, browserName },
  })),
});
"""

ALLOCATOR = """from pathlib import Path
import time
Path('/proc/self/oom_score_adj').write_text('1000')
blocks = []
for _ in range(128):
    block = bytearray(16 * 1024 * 1024)
    for offset in range(0, len(block), 4096):
        block[offset] = 1
    blocks.append(block)
    time.sleep(0.005)
raise RuntimeError('2 GiB allocation completed without the expected cgroup kill')
"""


def browser(snapshot):
    matches = [service for service in snapshot.get("services", []) if service.get("service") == "browser"]
    if len(matches) != 1:
        raise RuntimeError("Acceptance needs exactly one observed browser service: " + json.dumps(snapshot))
    return matches[0]


def write_config(workspace):
    path = Path(workspace) / CONFIG_NAME
    with path.open("x") as stream:
        stream.write(CONFIGURATION)
    return path


def verify_behavior(receipt):
    attempts = receipt["observed_test_attempts"]
    counts = {project: sum(attempt.get("project") == project for attempt in attempts) for project in PROJECTS}
    if (receipt.get("exit_code") != 0 or receipt.get("observer_status") != "complete"
            or receipt.get("selected_test_count") != 135 or len(attempts) != 135
            or any(count != 45 for count in counts.values())
            or any(attempt.get("status") != "passed" or attempt.get("retry") != 0 for attempt in attempts)):
        raise RuntimeError("Expected 45 passed cases per engine without retries: " + json.dumps({"counts": counts, "receipt": receipt}))
    print("Three-browser behavior acceptance: " + json.dumps(counts, sort_keys=True), flush=True)


def docker(arguments, env, timeout=30, check=True):
    return subprocess.run(["docker", *arguments], env=env, text=True, capture_output=True,
                          timeout=timeout, check=check)


def inspect(container, env):
    result = json.loads(docker(["inspect", container], env).stdout)
    if len(result) != 1:
        raise RuntimeError("Container inspection did not establish one identity")
    return result[0]


def baseline(project, env, destination, observe):
    snapshot = observe(project, env)
    fact = browser(snapshot)
    state = inspect(fact["container"], env)
    if state["HostConfig"]["Memory"] != DEFAULT_LIMIT or fact.get("cgroup_limit_bytes") != DEFAULT_LIMIT:
        raise RuntimeError("Normal browser acceptance requires the actual default 4 GiB limit: " + json.dumps(fact))
    if not state["State"]["Running"] or fact.get("current_bytes") is None or fact.get("peak_bytes") is None:
        raise RuntimeError("Running browser cgroup usage/peak is unavailable: " + json.dumps(fact))
    Path(destination).write_text(json.dumps({"snapshot": snapshot, "container": state}))
    print("Normal browser default limit observed: 4294967296 bytes", flush=True)


def normal_workload(project, env, baseline_file, observe):
    saved = json.loads(Path(baseline_file).read_text())
    snapshot = observe(project, env, before=saved["snapshot"])
    fact, prior = browser(snapshot), browser(saved["snapshot"])
    state = inspect(fact["container"], env)
    if (fact["container"] != prior["container"] or fact["started_at"] != prior["started_at"]
            or not state["State"]["Running"] or fact["docker_limit_bytes"] != DEFAULT_LIMIT
            or fact["cgroup_limit_bytes"] != DEFAULT_LIMIT or fact["oom_kill_delta"] != 0):
        raise RuntimeError("Normal three-browser workload changed identity/limits or OOM events: " + json.dumps(fact))
    print("Normal browser workload memory acceptance: " + json.dumps(fact, sort_keys=True), flush=True)
    return state["Config"]["Image"]


def child_oom(project, env, image, state_file, observe, diagnostics):
    fixture_project = project + "-oom-" + uuid.uuid4().hex[:10]
    isolated_env = {**env, "BROWSER_MEMORY": "512m"}
    container = None
    try:
        result = docker(["run", "--detach", "--init", "--network", "none", "--memory", "512m",
                         "--memory-swap", "512m", "--label", "com.docker.compose.project=" + fixture_project,
                         "--label", "com.docker.compose.service=browser", "--label", "dev.xorder.fixture=child-oom",
                         "--entrypoint", "node", image, "-e", "setInterval(() => {}, 1000)"], isolated_env)
        container = result.stdout.strip()
        Path(state_file).write_text(container)
        before = observe(fixture_project, isolated_env)
        prior = browser(before)
        if prior["cgroup_version"] != 2 or prior["cgroup_limit_bytes"] != OOM_LIMIT or "oom_kill" not in prior["events"]:
            raise RuntimeError("Hosted OOM acceptance requires an observed cgroup v2 counter and 512 MiB limit: " + json.dumps(prior))
        output = io.StringIO()
        try:
            with redirect_stdout(output), diagnostics(fixture_project, isolated_env):
                docker(["exec", "--user", "0", container, "python3", "-c", ALLOCATOR], isolated_env, timeout=45)
        except subprocess.CalledProcessError as failure:
            exit_code = failure.returncode
        else:
            raise RuntimeError("The allocator did not fail")
        print(output.getvalue(), end="", flush=True)
        after = observe(fixture_project, isolated_env, before=before)
        fact = browser(after)
        state = inspect(container, isolated_env)
        diagnostic = output.getvalue()
        if (exit_code != 137 or not state["State"]["Running"]
                or fact["container"] != prior["container"] or fact["started_at"] != prior["started_at"]
                or (fact.get("oom_kill_delta") or 0) < 1 or not fact["command_window_oom"]
                or fact["docker_limit_bytes"] != OOM_LIMIT or fact["cgroup_limit_bytes"] != OOM_LIMIT):
            raise RuntimeError("Child OOM identity, current-window counter, limit, or original exit was not established: " + json.dumps({"exit": exit_code, "memory": fact, "state": state["State"]}))
        if not all(fragment in diagnostic for fragment in ("service=browser", fact["container"], "Docker limit=0.50 GiB", "cgroup limit=0.50 GiB", "BROWSER_MEMORY=512m", "during the command window", "out of memory", "raise BROWSER_MEMORY")):
            raise RuntimeError("The failed-command observer did not report the browser identity, effective limit and recovery setting: " + diagnostic)
        print("Isolated browser-service child OOM acceptance (not a renderer benchmark): " + json.dumps({"original_exit_code": exit_code, "parent_running": True, "docker_oom_killed": state["State"]["OOMKilled"], "memory": fact}, sort_keys=True), flush=True)
    finally:
        if container:
            docker(["rm", "--force", container], isolated_env)
            Path(state_file).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("config")
    prepare.add_argument("workspace", type=Path)
    for action in ("baseline", "normal", "oom"):
        command = commands.add_parser(action)
        command.add_argument("project")
        command.add_argument("baseline_file", type=Path)
        if action == "oom":
            command.add_argument("state_file", type=Path)
    options = parser.parse_args()
    if options.action == "config":
        print(write_config(options.workspace))
        return
    sys.path.insert(0, str(ROOT / "examples/shared"))
    from container_memory import failure_diagnostics, memory_observations
    env = dict(os.environ)
    if options.action == "baseline":
        baseline(options.project, env, options.baseline_file, memory_observations)
    elif options.action == "normal":
        normal_workload(options.project, env, options.baseline_file, memory_observations)
    else:
        image = normal_workload(options.project, env, options.baseline_file, memory_observations)
        child_oom(options.project, env, image, options.state_file, memory_observations, failure_diagnostics)


if __name__ == "__main__":
    main()
