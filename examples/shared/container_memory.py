"""Bounded, read-only memory observations from the selected Docker engine."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import time

from runtime import observation_timeout

PROBE = Path(__file__).with_name("memory-probe.cjs").read_text() + "\nconsole.log(JSON.stringify(probe()));\n"
DEFAULT_MEMORY = {"php": ("PHP_MEMORY", "2g"), "browser": ("BROWSER_MEMORY", "4g")}


def _number(value):
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _counters(value):
    result = {}
    if isinstance(value, str):
        for line in value.splitlines():
            fields = line.split()
            if len(fields) == 2 and (number := _number(fields[1])) is not None:
                result[fields[0]] = number
    return result


def _docker(arguments, env, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        completed = subprocess.run(["docker", *arguments], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True, timeout=remaining, check=False)
        return completed.stdout if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def memory_observations(project, env, containers=None, before=None):
    """A lifetime OOM counter is evidence to inspect, not attribution to this run."""
    deadline = time.monotonic() + observation_timeout(env)
    if containers is None:
        ids = _docker(["ps", "-aq", "--filter", "label=com.docker.compose.project=" + project], env, deadline)
        if ids is None:
            return {"services": [], "unavailable": "selected Docker engine observation unavailable"}
        if not ids.split():
            return {"services": [], "unavailable": "no stack containers found"}
        try:
            containers = json.loads(_docker(["inspect", *ids.split()], env, deadline) or "null")
        except ValueError:
            containers = None
    if not isinstance(containers, list):
        return {"services": [], "unavailable": "stack container inspection unavailable"}
    facts = []
    for container in containers:
        if not isinstance(container, dict) or not container.get("Id"):
            continue
        state = container.get("State", {})
        fact = {"service": container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service", "unknown"),
                "container": container["Id"], "docker_limit_bytes": _number(container.get("HostConfig", {}).get("Memory")),
                "oom_killed": state.get("OOMKilled") if type(state.get("OOMKilled")) is bool else None,
                "started_at": state.get("StartedAt"), "finished_at": state.get("FinishedAt"),
                "cgroup_version": None, "cgroup_limit_bytes": None, "cgroup_unlimited": False,
                "current_bytes": None, "peak_bytes": None, "events": {}, "events_local": {}}
        probe = None
        if state.get("Running"):
            try:
                probe = json.loads(_docker(["exec", container["Id"], "node", "-e", PROBE], env, deadline) or "null")
            except ValueError:
                pass
        if not isinstance(probe, dict) or probe.get("version") not in (1, 2) or not isinstance(probe.get("files"), dict):
            fact["unavailable"] = ("cgroup observation unavailable" if state.get("Running")
                                   else "cgroup peak/events unavailable for stopped container")
        else:
            files = probe["files"]
            version = fact["cgroup_version"] = probe["version"]
            maximum = files.get("memory.max" if version == 2 else "memory.limit_in_bytes")
            fact["cgroup_limit_bytes"] = _number(maximum)
            fact["cgroup_unlimited"] = maximum == "max"
            fact["current_bytes"] = _number(files.get("memory.current" if version == 2 else "memory.usage_in_bytes"))
            fact["peak_bytes"] = _number(files.get("memory.peak" if version == 2 else "memory.max_usage_in_bytes"))
            fact["events"] = _counters(files.get("memory.events" if version == 2 else "memory.oom_control"))
            fact["events_local"] = _counters(files.get("memory.events.local"))
            if version == 1:
                fact["limit_hits"] = _number(files.get("memory.failcnt"))
        fact["oom_evidence"] = fact["oom_killed"] is True or fact["events"].get("oom_kill", 0) > 0
        previous = next((item for item in (before or {}).get("services", [])
                         if item.get("container") == fact["container"]), None)
        fact.update(oom_kill_delta=None, oom_killed_changed=None, command_window_oom=False)
        if previous:
            if previous.get("oom_killed") is not None and fact["oom_killed"] is not None:
                fact["oom_killed_changed"] = previous["oom_killed"] is False and fact["oom_killed"] is True
            old, new = previous.get("events", {}).get("oom_kill"), fact["events"].get("oom_kill")
            # Container restarts can reset the cgroup counter, even with the same ID.
            same_start = bool(fact["started_at"]) and previous.get("started_at") == fact["started_at"]
            if same_start and old is not None and new is not None and new >= old:
                fact["oom_kill_delta"] = new - old
            fact["command_window_oom"] = (fact["oom_kill_delta"] or 0) > 0 or fact["oom_killed_changed"] is True
        facts.append(fact)
    return {"services": facts}


def _size(value, unlimited=False):
    return "unlimited" if unlimited else "unavailable" if value is None else f"{value / 1024**3:.2f} GiB"


def print_service_memory(fact, env):
    docker_limit = fact["docker_limit_bytes"]
    cgroup_limit = _size(fact["cgroup_limit_bytes"], fact["cgroup_unlimited"])
    flag = "unavailable" if fact["oom_killed"] is None else str(fact["oom_killed"]).lower()
    kills = fact["events"].get("oom_kill", "unavailable")
    print(f"{fact['service']} memory: container={fact['container']}, Docker limit={_size(docker_limit, docker_limit == 0)}, "
          f"cgroup limit={cgroup_limit}, peak={_size(fact['peak_bytes'])}, current={_size(fact['current_bytes'])}, "
          f"OOMKilled={flag}, oom_kill={kills} (cumulative), "
          f"oom_kill delta={fact['oom_kill_delta'] if fact['oom_kill_delta'] is not None else 'unavailable'}", flush=True)
    if fact.get("unavailable"):
        print(f"{fact['service']} memory: {fact['unavailable']}", flush=True)
    if fact["command_window_oom"]:
        print(f"New out of memory (OOM) evidence observed during the command window for service={fact['service']} "
              f"container={fact['container']}; inspect it alongside the failed command", flush=True)
    elif fact["oom_evidence"]:
        print(f"OOM evidence observed for service={fact['service']} container={fact['container']}; "
              "the counter/flag alone does not date the kill to this command", flush=True)
    if fact["service"] in DEFAULT_MEMORY:
        key, default = DEFAULT_MEMORY[fact["service"]]
        print(f"{fact['service']} memory setting: {key}={env.get(key) or default} for the next up; "
              "the limits above describe the existing container", flush=True)
        if fact["oom_evidence"]:
            cgroup_known = fact["cgroup_limit_bytes"] is not None or fact["cgroup_unlimited"]
            label = "effective limit" if cgroup_known else "Docker configured limit"
            limit = cgroup_limit if cgroup_known else _size(docker_limit, docker_limit == 0)
            print(f"Memory recovery after out of memory evidence: service={fact['service']} "
                  f"container={fact['container']}, {label}={limit}; check host capacity and raise {key} "
                  "for this workload, then run up", flush=True)


def report_failure(project, env, before=None, result=None):
    """A missing engine, broken stdout, or diagnostic timeout cannot replace the exit."""
    try:
        print("Failed command memory observations (OOM counters cover container lifetime):", flush=True)
        if result is None:
            result = memory_observations(project, env, before=before)
        if result.get("unavailable"):
            print("Memory diagnostics unavailable: " + result["unavailable"], flush=True)
        for fact in result["services"]:
            print_service_memory(fact, env)
    except Exception:
        try:
            print("Memory diagnostics unavailable; original command failure retained", flush=True)
        except OSError:
            pass


@contextmanager
def failure_diagnostics(project, env):
    try:
        before = memory_observations(project, env)
    except Exception:
        before = {"services": [], "unavailable": "baseline memory observation unavailable"}
    try:
        yield
    except BaseException:
        report_failure(project, env, before=before)
        raise
