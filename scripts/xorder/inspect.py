"""Bounded read-only facts for discovery; application readiness remains separate."""
import platform
import shutil
import subprocess
from pathlib import Path

from . import model


COMMANDS = ("docker", "php", "nix", "devenv", "bash", "git", "python3")
LOCKFILES = ("composer.lock", "package-lock.json", "uv.lock", "Cargo.lock", "devenv.lock",
             "demo/composer.lock", "demo/package-lock.json")


def _probe(argv, timeout):
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timed_out"}
    except OSError:
        return {"status": "unavailable"}
    if result.returncode:
        return {"status": "failed", "exit_code": result.returncode}
    return {"status": "passed", "value": result.stdout.strip()[:200]}


def inspect_target(workspace, resource=None, timeout=3):
    """Probe fixed commands only; do not invoke project hooks, pull or start services."""
    if not 0 < timeout <= 10:
        raise ValueError("Inspection timeout must be greater than zero and at most 10 seconds")
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("Inspection workspace must be an existing directory")
    command_names = set(COMMANDS)
    if resource:
        command_names.update(resource["prerequisites"]["commands"])
    commands = {name: bool(shutil.which(name)) for name in sorted(command_names)}
    machine = platform.machine().lower()
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(machine, machine)
    host_platform = platform.system().lower() + "/" + architecture
    facts = {"platform": host_platform,
             "commands": [name for name, present in commands.items() if present]}
    gaps = []
    prerequisites = resource["prerequisites"]["commands"] if resource else []
    for command in prerequisites:
        if not commands[command]:
            gaps.append({"code": "missing_command", "command": command,
                         "action": f"Provide {command} in this execution environment, then repeat doctor."})
    probes = {}
    if commands["docker"]:
        probes["docker_engine"] = _probe(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"], timeout)
        probes["docker_compose"] = _probe(["docker", "compose", "version", "--short"], timeout)
        if resource and resource["kind"] == "image" and probes["docker_engine"]["status"] != "passed":
            gaps.append({"code": "docker_engine_" + probes["docker_engine"]["status"],
                         "action": "Restore the host's Docker engine or connection, then repeat doctor; a client alone is insufficient."})
    if resource and resource["kind"] == "image":
        # A remote Linux engine may be used by a different host OS. Never
        # substitute host architecture for unknown engine target facts.
        facts.pop("platform")
        engine = probes.get("docker_engine", {})
        if engine.get("status") == "passed":
            engine_platform = engine["value"].split("/")
            if len(engine_platform) == 2 and all(engine_platform):
                os_name, arch = engine_platform
                facts["platform"] = os_name.lower() + "/" + {"x86_64": "amd64", "aarch64": "arm64"}.get(arch, arch)
    if resource and "platform" in facts and "any" not in resource["targets"] and facts["platform"] not in resource["targets"]:
        gaps.append({"code": "untested_target_platform", "observed": facts["platform"],
                     "action": "Read the resource targets and use a verified execution surface."})
    disk = shutil.disk_usage(workspace)
    result = {"schema_version": 1, "status": "prerequisites_missing" if gaps else "facts_observed",
              "target": facts, "command_presence": commands, "probes": probes,
              "host_platform": host_platform,
              "workspace": {"path": str(workspace), "free_bytes": disk.free,
                            "total_bytes": disk.total,
                            "lockfiles": [name for name in LOCKFILES if (workspace / name).is_file()]},
              "gaps": gaps, "network": "not_probed", "application_readiness": "not_probed"}
    if resource:
        result["resource"] = {"id": resource["id"], "version": resource["version"],
                              "identity": resource["identity"], "usage": resource["documentation"]}
        result["declared_requirements"] = resource["prerequisites"].get("requirements", [])
    return result
