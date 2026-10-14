#!/usr/bin/env python3
"""Local Compose orchestration; dependencies and application hooks stay project-owned."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

PROFILE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROFILE))
sys.path.insert(0, str(PROFILE.parent / "shared"))
sys.path.insert(0, str(PROFILE.parents[1] / "scripts"))
from xorder.downstream import runner_check as support_check, requires_check as support_required, runner_precheck as support_precheck  # noqa: E402
from network import container_environment, local_engine, owner_label, stop, loopback_proxy, PROXIES  # noqa: E402
from proxy_relay import directory as relay_directory, running as relay_running  # noqa: E402
from runtime import ensure_daemon, print_resources, print_activity, stack_activity, heavy_run, gc, state_root, observation_timeout, print_reclaimable  # noqa: E402
from pull_budget import preflight  # noqa: E402
from seed import seed, shared_paths, forget_sharing, inside as seed_path  # noqa: E402
from testing_contract import load_contract, run_plant, sync_contract  # noqa: E402
from test_receipts import parse_test_options, run_test as receipt_test  # noqa: E402
from cache import register_workspace_cache, orphan_cache_usage  # noqa: E402
from container_memory import memory_observations, print_service_memory, failure_diagnostics  # noqa: E402

PHP_TEST_ENVIRONMENT = (
    "PHPUNIT_PROJECT", "PHPUNIT_CONFIGURATION",
    "PHPSTAN_PROJECT", "PHPSTAN_WORKSPACE", "PHPSTAN_CONFIGURATION",
    "PHPSTAN_AUTOLOAD_FILE", "PHPSTAN_PATHS",
    "COVERAGE_DRIVER", "COVERAGE_SOURCE", "COVERAGE_CLOVER",
)


def call(arguments, env, capture=False, check=True, observational=None):
    try:
        return subprocess.run(arguments, env=env, check=check, text=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None,
                              timeout=observation_timeout(env) if (capture if observational is None else observational) else None)
    except subprocess.TimeoutExpired as error:
        raise ValueError("Docker or workspace observation timed out; inspect the selected engine and its disk, "
                         "then retry status (XORDER_OBSERVE_TIMEOUT_SECONDS controls the deadline)") from error




def playwright(workspace):
    package = json.loads((workspace / "package.json").read_text())
    lock = json.loads((workspace / "package-lock.json").read_text())
    version = lock["packages"]["node_modules/@playwright/test"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or package.get("devDependencies", {}).get("@playwright/test") != version:
        raise ValueError("Pin @playwright/test to the same exact version in package.json and package-lock.json")
    return version


def php_exec(compose, env, *arguments, cwd="/app", capture=False, check=True, forwarded=(), observational=False):
    overrides = [argument for key in forwarded if key in env
                 for argument in ("-e", key + "=" + env[key])]
    return call([*compose, "exec", "-T", "--user", f'{env["PUID"]}:{env["PGID"]}', "-w", cwd,
                 *overrides, "php", *arguments], env, capture=capture, check=check, observational=observational)


def compose_command(workspace, project, env):
    command = ["docker", "compose", "--project-directory", str(workspace / "demo"), "-p", project]
    if env.get("XORDER_PARITY_FIXTURE") == "1":
        # Consumer configuration is executable infrastructure, not trusted input.
        # The controlled fixture mounts only this checkout and the trusted profile.
        for name in ("Caddyfile", "conf.d/10-app.ini", "conf.d/20-app.dev.ini"):
            path = (workspace / "demo/frankenphp" / name).resolve(strict=True)
            if not path.is_relative_to(workspace) or not path.is_file():
                raise ValueError("Parity configuration must stay inside the disposable consumer checkout")
        command += ["--env-file", os.devnull, "-f", str(PROFILE.parents[1] / "tests/fixtures/playwright/compose.yaml")]
    else:
        command += ["-f", str(workspace / "demo/compose.yaml"), "-f", str(workspace / "demo/compose.override.yaml")]
    return [*command, "-f", str(PROFILE / "compose.yaml")]


def identity(workspace, env, slot):
    key = hashlib.sha256(str(workspace).encode()).hexdigest()
    project = env.get("UXOR_PROJECT") or "uxor-" + re.sub(r"[^a-z0-9_-]", "-", workspace.name.lower())[:32] + "-" + key[:10]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("UXOR_PROJECT must start with a lowercase letter/digit and contain lowercase letters, digits, _ or -")
    selected = int(key[:8], 16) % 5000 if slot is None else slot
    if not 0 <= selected <= 14999:
        raise ValueError("--slot must be between 0 and 14999")
    http = env.get("HTTP_PORT") or str(20000 + 2 * selected)
    https = env.get("HTTPS_PORT") or str(20001 + 2 * selected)
    udp = env.get("HTTP3_PORT") or https
    for port in (http, https, udp):
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("HTTP_PORT, HTTPS_PORT and HTTP3_PORT must be integer ports from 1 to 65535")
    if http == https:
        raise ValueError("HTTP_PORT and HTTPS_PORT must differ")
    return project, http, https, udp, key


def containers(project, env):
    ids = call(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project], env, capture=True).stdout.split()
    return json.loads(call(["docker", "inspect", *ids], env, capture=True).stdout) if ids else []


def readiness(container, env):
    if not container or not container.get("State", {}).get("Running"):
        return False
    result = call(["docker", "exec", container["Id"], "curl", "--fail", "--silent", "--show-error", "--insecure", "--noproxy", "*", "--max-time", "5", "https://localhost" + env.get("APP_READY_PATH", "/")], env, capture=True, check=False)
    return result.returncode == 0


def status(project, env, reclaimable=False):
    print("project: " + project)
    print_resources(Path(env["WORKSPACE"]), env)
    print_activity(Path(env["WORKSPACE"]), project, env)
    try:
        daemon = call(["docker", "info", "--format", "{{json .ServerVersion}}"], env, capture=True, check=False)
    except ValueError as error:
        print("daemon: unavailable (" + str(error) + ")")
        return 1
    if daemon.returncode:
        print("daemon: unavailable (start Docker, then run up)")
        return 1
    print("daemon: reachable")
    if reclaimable:
        print_reclaimable(env)
    relay = True
    if env.get("PROXY_PASSTHROUGH", "auto") == "auto" and any(
            env.get(name) and loopback_proxy(env[name], name) for name in PROXIES):
        active = relay_running(relay_directory(f"uxor:{env['WORKSPACE']}:{project}"))
        relay = bool(active)
        expected = sorted({(proxy[1], proxy[2]) for name in PROXIES
                           if env.get(name) and (proxy := loopback_proxy(env[name], name))})
        if active and sorted(tuple(target) for target in active["config"]["targets"]) != expected:
            relay = False
        if active:
            for host, port in active["config"]["targets"]:
                try:
                    with socket.create_connection((host, port), timeout=2):
                        pass
                except OSError:
                    relay = False
        print("proxy relay: " + ("ready" if relay else "unavailable (run up to restore)"))
    else:
        print("proxy relay: not required")
    found = containers(project, env)
    memory = memory_observations(project, env, containers=found)
    for fact in memory["services"]:
        print_service_memory(fact, env)
    php = None
    services = {}
    for container in found:
        service = container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service")
        services[service] = container
        state = container.get("State", {})
        if service == "php":
            php = container
        health = state.get("Health", {}).get("Status", "unreported")
        print(f"{service}: {state.get('Status', 'unknown')}, health={health}")
    for service in ("php", "browser"):
        if service not in services:
            print(service + ": absent")
    ready = readiness(php, env)
    print("application: " + ("ready" if ready else "not ready"))
    return 0 if relay and ready and all(services.get(service, {}).get("State", {}).get("Running") and services[service]["State"].get("Health", {}).get("Status") == "healthy" for service in ("php", "browser")) else 1


def browser_image(version):
    resources = json.loads((PROFILE.parents[1] / "catalog-v2.json").read_text())["resources"]
    candidates = [entry for entry in resources if entry["id"].startswith("image/playwright-browser/")
                  and entry["lifecycle"] == "available" and entry["verification"]["status"] == "passed"
                  and json.loads((PROFILE.parents[1] / entry["release_record"]).read_text())["platforms"][0]["inventory"]["runtime_version"] == version]
    if candidates:
        return max(candidates, key=lambda item: tuple(map(int, item["version"].split("."))))["identity"]
    return f"mcr.microsoft.com/playwright:v{version}-noble"


def check_ports(project, env):
    owned = set()
    found = containers(project, env)
    php = next((container for container in found if container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service") == "php"), None)
    if found:
        label = (php or {}).get("Config", {}).get("Labels", {}).get("dev.xorder.workspace")
        mounts = (php or {}).get("Mounts", [])
        legacy_workspace = any(mount.get("Type") == "bind" and mount.get("Destination") == "/app" and Path(mount.get("Source", "")).resolve() == Path(env["WORKSPACE"]) for mount in mounts)
        if label != env["WORKSPACE"] and not (label is None and legacy_workspace):
            raise ValueError("UXOR_PROJECT is already owned by another workspace; choose a different name")
    if not local_engine(env):
        # Compose checks binds on the remote engine; client ports are unrelated.
        return
    for container in found:
        for port, bindings in (container.get("NetworkSettings", {}).get("Ports") or {}).items():
            for binding in bindings or []:
                owned.add((port.rsplit("/", 1)[1], int(binding["HostPort"])))
    for protocol, value in (("tcp", env["HTTP_PORT"]), ("tcp", env["HTTPS_PORT"]), ("udp", env["HTTP3_PORT"])):
        port = int(value)
        if (protocol, port) in owned:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                raise ValueError(f"Port {port}/{protocol} is occupied; choose another --slot or explicit HTTP_PORT/HTTPS_PORT/HTTP3_PORT") from error


def input_fingerprint(workspace, env):
    value = hashlib.sha256()
    extensions = {".php", ".twig", ".json", ".yaml", ".yml", ".js", ".mjs", ".cjs", ".ts", ".css", ".xml", ".ini", ".lock", ".sh", ".neon", ".py"}
    for base in (workspace, PROFILE):
        value.update(str(base).encode() + b"\0")
        if base == workspace and (workspace / ".git").exists():
            # Ignore generated recipes/assets exactly as the project does. Hash
            # current working bytes, including nonignored uncommitted source.
            names = call(["git", "-C", str(workspace), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], env, capture=True).stdout.split("\0")
            files = sorted(base / name for name in names if name)
        else:
            files = []
            for directory, subdirectories, filenames in os.walk(base):
                subdirectories[:] = sorted(name for name in subdirectories if name not in (".git", "node_modules", "vendor", "var", ".cache", "__pycache__"))
                files.extend(Path(directory) / name for name in sorted(filenames))
        for file in files:
            if not file.is_file() or file.is_symlink() or (file.suffix not in extensions and not file.name.startswith(".env")):
                continue
            value.update(str(file.relative_to(base)).encode() + b"\0" + file.read_bytes() + b"\0")
    if env.get("CA_CERTIFICATE"):
        value.update(Path(env["CA_CERTIFICATE"]).read_bytes())
    return value.hexdigest()


def service_fingerprint(workspace, env):
    """Restart only for mounted startup/server inputs; source belongs to setup evidence."""
    value = hashlib.sha256()
    paths = [(PROFILE, name) for name in (
        "startup.sh", "trust.py", "reuse.sh", "verify-composer.php", "composer-dist.php",
        "importmap-state.php", "cache.py", "compose.yaml")]
    configuration = workspace / "demo/frankenphp"
    if configuration.is_dir():
        paths.extend((workspace, str(path.relative_to(workspace)))
                     for path in sorted(configuration.rglob("*")) if path.is_file())
    for base, name in paths:
        path = base / name
        value.update(str(base).encode() + b"\0" + name.encode() + b"\0")
        value.update(path.read_bytes() if path.is_file() else b"missing")
    if env.get("CA_CERTIFICATE"):
        value.update(Path(env["CA_CERTIFICATE"]).read_bytes())
    return value.hexdigest()


def run_test(compose, env, workspace, project, arguments, workers=None):
    try:
        baseline = memory_observations(project, env)
    except Exception:
        baseline = {"services": [], "unavailable": "test memory baseline unavailable"}
    return receipt_test(compose, env, workspace, project, arguments, workers=workers,
                        input_fingerprint=input_fingerprint(workspace, env), memory_start=baseline)


def main(arguments):
    if not arguments:
        raise ValueError("Usage: run.sh [--slot N] up|seed|status|support|sync|plant|test|cache|gc|phpunit|php-tests|exec|logs|down [arguments]")
    slot = None
    if arguments[0] == "--slot":
        if len(arguments) < 3 or not arguments[1].isdigit():
            raise ValueError("Usage: run.sh --slot N action [arguments]")
        slot = int(arguments[1])
        arguments = arguments[2:]
    action, *extra = arguments
    if len(extra) >= 2 and extra[0] == "--slot":
        if not extra[1].isdigit():
            raise ValueError("--slot must be a nonnegative integer")
        slot = int(extra[1]); extra = extra[2:]
    if action not in ("up", "seed", "status", "support", "sync", "plant", "test", "cache", "gc", "phpunit", "php-tests", "exec", "logs", "down"):
        raise ValueError(f"Unknown action: {action}")
    env = dict(os.environ)
    if action == "test":
        extra = parse_test_options(extra, env)
    workspace = Path(env["WORKSPACE"]).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("WORKSPACE must be a directory")
    contract = None
    if action in ("plant", "sync"):
        contract = load_contract(workspace, PROFILE)
    if action == "plant":
        if extra == ["--list"]:
            return run_plant(workspace, env, contract, extra, None, None)
        if not extra:
            raise ValueError("Usage: xr plant NAME [--wait SECONDS] [--measure] [--attest-server] -- [Playwright arguments] | --list | --restore")
        if extra != ["--restore"]:
            extra = [extra[0], *parse_test_options(extra[1:], env)]
    if action == "sync" and extra not in ([], ["--check"]):
        raise ValueError("Usage: xr sync [--check]")
    if action == "seed":
        parser = argparse.ArgumentParser(prog="xr seed", description="Seed absent dependencies from an explicitly trusted checkout; never install or overwrite")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--from", dest="source", type=Path)
        mode.add_argument("--forget-sharing", action="store_true", help="Clear obsolete sharing guards only after all shared paths were removed and the stack is stopped")
        parser.add_argument("--hardlink", action="store_true", help="Require stopped donor/receiver and protect shared dependencies with durable read-only reuse guards")
        options = parser.parse_args(extra)
        if options.forget_sharing:
            if options.hardlink:
                raise ValueError("--hardlink requires --from")
            return forget_sharing(workspace, env)
        return seed(workspace, options.source, env, hardlink=options.hardlink)
    if action == "cache" and "--orphaned" in extra:
        parser = argparse.ArgumentParser(prog="xr cache", description="Inspect explicitly registered workspace caches; dry-run by default")
        parser.add_argument("operation", choices=("usage", "prune"))
        parser.add_argument("--orphaned", action="store_true", required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--dry-run", action="store_true")
        options = parser.parse_args(extra)
        if options.operation == "usage" and options.apply:
            raise ValueError("--apply requires cache prune --orphaned")
        root = Path(env.get("XORDER_SHARED_CACHE_DIR", str(state_root(env) / "dependencies"))).resolve()
        return orphan_cache_usage(root, env, apply=options.apply)
    shared = [] if action in ("down", "logs", "status", "gc") else shared_paths(workspace, env)
    if action not in ("down", "logs", "status", "gc"):
        for path in shared:
            seed_path(workspace, path)
    if action == "up":
        parser = argparse.ArgumentParser(prog="xr up")
        parser.add_argument("--reuse-only", action="store_true", help="Verify and adopt existing dependencies with read-only mounts; never install or run setup hooks")
        options = parser.parse_args(extra)
        reuse = env.get("XORDER_REUSE_ONLY") or "0"
        if reuse not in ("0", "1"):
            raise ValueError("XORDER_REUSE_ONLY must be 0 or 1")
        env["XORDER_REUSE_ONLY"] = "1" if options.reuse_only or shared else reuse
        if env["XORDER_REUSE_ONLY"] == "0" and (env.get("COMPOSER_INSTALL_PREFERENCE") or "dist") != "dist":
            raise ValueError("up installs from dist only. Remove COMPOSER_INSTALL_PREFERENCE=source; source clones can exhaust the sandbox disk. Use up --reuse-only with complete existing dependencies")
    reuse_only = action == "up" and env.get("XORDER_REUSE_ONLY") == "1"
    if shared:
        env["XORDER_REUSE_ONLY"] = "1"
    project, http, https, udp, key = identity(workspace, env, slot)
    env.update(WORKSPACE=str(workspace), UXOR_PROJECT=project, PUID=env.get("PUID") or str(os.getuid()),
               PGID=env.get("PGID") or str(os.getgid()), UXOR_PROFILE_DIR=str(PROFILE),
               HTTP_PORT=http, HTTPS_PORT=https, HTTP3_PORT=udp, CONTAINER_CA_FILE="")
    if action == "support":
        if extra:
            raise ValueError("Usage: xr support (read-only current policy and running image check)")
        report = support_check(workspace, env, containers=containers(project, env) if support_required(workspace, env) else [])
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if action == "status":
        if extra not in ([], ["--reclaimable"]):
            raise ValueError("Usage: xr status [--reclaimable] (read-only cleanup candidates)")
        return status(project, env, reclaimable=extra == ["--reclaimable"])
    if action == "gc":
        parser = argparse.ArgumentParser(prog="xr gc", description="List unused resources; dry-run by default")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--dry-run", action="store_true")
        parser.add_argument("--runner-copy", action="append", default=[], help="Explicit unpacked old runner copy to inspect and remove")
        parser.add_argument("--keep", action="append", default=[], help="Protect an idle local tool image and its base images; repeat for each image to retain")
        options = parser.parse_args(extra)
        env["XORDER_RUNNER_ROOT"] = str(PROFILE.parents[1])
        return gc(env, apply=options.apply, runner_copies=options.runner_copy, keep=options.keep)
    if not env.get("IMAGE"):
        raise ValueError("Select IMAGE from the verified uxor-dev catalog")
    ca = env.get("CA_CERTIFICATE")
    if ca:
        if not Path(ca).is_absolute() or not os.access(ca, os.R_OK):
            raise ValueError("CA_CERTIFICATE must be a readable absolute PEM path")
        env["CONTAINER_CA_FILE"] = "/run/library-proxy.pem"
    # Only starting a new browser requires the lock. Recovery inspection and
    # cleanup work after deleted/moved dependency files as well.
    needs_browser_lock = action in ("up", "test") or (action == "plant" and extra != ["--restore"])
    env["PLAYWRIGHT_VERSION"] = playwright(workspace) if needs_browser_lock else "0.0.0"
    env["BROWSER_IMAGE"] = env.get("BROWSER_IMAGE") or browser_image(env["PLAYWRIGHT_VERSION"])
    if action == "up":
        ensure_daemon(env)
    elif action not in ("down", "logs"):
        # Existing containers can keep using retired cached images. Check their
        # engine image IDs before invoking any project test or command.
        if action != "cache" and support_required(workspace, env):
            support_check(workspace, env, containers=containers(project, env))
    proxy_owner = f"uxor:{workspace}:{project}"
    env["XORDER_PROXY_OWNER"] = owner_label(proxy_owner)
    if action not in ("down", "logs"):
        if action == "up":
            check_ports(project, env)
        settings = container_environment(env, proxy_owner, reconfigure=action == "up", services=("php", "browser"))
        env.update({"XORDER_" + key: value for key, value in settings.items()})
    if action == "up":
        env["XORDER_INPUT_FINGERPRINT"] = input_fingerprint(workspace, env)
        env["XORDER_SERVICE_FINGERPRINT"] = service_fingerprint(workspace, env)
    compose = compose_command(workspace, project, env)
    overlay = {"services": {"php": {"volumes": []}}}
    if (reuse_only or shared) and action not in ("down", "logs"):
        # Protect the actual dependency files even when project code or a tool
        # attempts a write. Receipts, Symfony caches and compiled CSS stay local.
        paths = [Path("demo/vendor"), Path("node_modules")] if reuse_only else []
        paths.extend(Path(path) for path in shared)
        map_file = Path(env.get("IMPORTMAP_FILE") or "importmap.php")
        asset_vendor = Path(env.get("IMPORTMAP_VENDOR_DIR") or "assets/vendor")
        for path in (map_file, asset_vendor):
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Reuse-only importmap paths must be relative paths inside demo")
        if reuse_only and (workspace / "demo" / map_file).is_file():
            paths.append(Path("demo") / asset_vendor)
        missing = []
        for path in sorted(set(paths)):
            source = (workspace / path).resolve()
            if not source.is_relative_to(workspace):
                raise ValueError("Reuse-only dependencies must stay inside the mounted workspace")
            if not source.is_dir():
                if reuse_only:
                    missing.append(str(path))
                continue
            overlay["services"]["php"]["volumes"].append({"type": "bind", "source": str(source), "target": "/app/" + path.as_posix(), "read_only": True, "bind": {"create_host_path": False}})
        if missing:
            raise ValueError("Reuse-only dependency directories are missing: " + ", ".join(missing) + "; prepare a private complete installation before retrying")
    if action == "up" and not env["BROWSER_IMAGE"].startswith("mcr.microsoft.com/playwright:"):
        overlay["services"]["browser"] = {"command": ["playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]}
    if action in ("up", "cache") and not reuse_only and env.get("XORDER_SHARED_CACHE", "1") != "0":
        common = call(["git", "-C", str(workspace), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                      env, capture=True, check=False)
        repository = common.stdout.strip() if common.returncode == 0 else str(workspace)
        scope = hashlib.sha256(repository.encode()).hexdigest()
        # Repository grouping is organizational only. Each checkout gets its own
        # bind, so untrusted linked worktrees cannot replace another's executable
        # snapshots or Composer dist archives. Cross-worktree reuse is an explicit
        # bundle import authenticated against a caller-supplied trusted digest.
        cache_root = Path(env.get("XORDER_SHARED_CACHE_DIR", str(state_root(env) / "dependencies"))).resolve()
        shared = cache_root / scope / key
        if shared.resolve() != shared:
            raise ValueError("Dependency cache must not be redirected by symlinks")
        shared.mkdir(parents=True, exist_ok=True)
        register_workspace_cache(shared, workspace, repository, downloads=not bool(env.get("COMPOSER_CACHE_DIR")))
        overlay["services"]["php"]["volumes"].append({"type": "bind", "source": str(shared), "target": "/run/xorder-cache", "bind": {"create_host_path": False}})
        overlay["services"]["php"]["environment"] = {"XORDER_CACHE_IMAGE": env["IMAGE"]}
        if not env.get("COMPOSER_CACHE_DIR"):
            downloads = shared / "composer-downloads"
            if downloads.resolve() != downloads:
                raise ValueError("Composer downloads must not be redirected by symlinks")
            downloads.mkdir(exist_ok=True)
            overlay["services"]["php"]["volumes"].append({"type": "bind", "source": str(downloads), "target": "/run/composer-cache", "bind": {"create_host_path": False}})
            overlay["services"]["php"]["environment"]["COMPOSER_CACHE_DIR"] = "/run/composer-cache"
    cache = env.get("COMPOSER_CACHE_DIR")
    if cache and not reuse_only:
        host_cache = Path(cache)
        if not host_cache.is_absolute() or not host_cache.is_dir():
            raise ValueError("COMPOSER_CACHE_DIR must be an existing absolute host cache directory")
        # A project's writable dist archives must never become another project's
        # dependency inputs. Mount only this canonical workspace's cache.
        scoped_cache = host_cache / "xorder" / key
        if scoped_cache.resolve() != host_cache.resolve() / "xorder" / key:
            raise ValueError("COMPOSER_CACHE_DIR workspace cache must not be redirected by symlinks")
        scoped_cache.mkdir(parents=True, exist_ok=True)
        overlay["services"]["php"]["volumes"].append({"type": "bind", "source": str(scoped_cache), "target": "/run/composer-cache", "bind": {"create_host_path": False}})
        # Keep the bind outside HOME so the image cannot change host ownership.
        overlay["services"]["php"].setdefault("environment", {})["COMPOSER_CACHE_DIR"] = "/run/composer-cache"
    if env.get("WORKTREE_GIT", "0") == "1" and (workspace / ".git").is_file():
        common = call(["git", "-C", str(workspace), "rev-parse", "--path-format=absolute", "--git-common-dir"], env, capture=True).stdout.strip()
        private = call(["git", "-C", str(workspace), "rev-parse", "--absolute-git-dir"], env, capture=True).stdout.strip()
        key = hashlib.sha256(str(workspace).encode()).hexdigest()
        pointer = Path(env.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "xorder/worktrees" / key / "git-pointer"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        (pointer.parent / "workspace.json").write_text(json.dumps({"workspace": str(workspace)}))
        pointer.write_text(f"gitdir: {private}\n")
        pointer.chmod(0o644)
        overlay["services"]["php"].setdefault("environment", {})["GIT_OPTIONAL_LOCKS"] = "0"
        for source, target in ((common, common), (str(pointer), "/app/.git")):
            overlay["services"]["php"]["volumes"].append({"type": "bind", "source": source, "target": target, "read_only": True, "bind": {"create_host_path": False}})
    with failure_diagnostics(project, env), stack_activity(workspace, project, env, action), tempfile.TemporaryDirectory(prefix="xorder-compose-") as directory:
        if overlay["services"]["php"]["volumes"] or "browser" in overlay["services"]:
            filename = Path(directory) / "overlay.json"
            filename.write_text(json.dumps(overlay))
            compose += ["-f", str(filename)]
        if action == "up":
            configuration = call([*compose, "config", "--format", "json"], env, capture=True).stdout
            # Include all services supplied by the consuming Compose project.
            service_names = json.loads(configuration).get("services", {})
            for proxy_key in ("XORDER_NO_PROXY", "XORDER_no_proxy"):
                env[proxy_key] = ",".join(dict.fromkeys([*env[proxy_key].split(","), *service_names]))
            if service_names:
                configuration = call([*compose, "config", "--format", "json"], env, capture=True).stdout
            support = support_precheck(workspace, env, json.loads(configuration))
            preflight(workspace, json.loads(configuration), env, PROFILE.parents[1])
            if support:
                # Pull before application startup so the support gate can check
                # actual bytes. Already cached images and unrelated third-party
                # services retain normal behavior.
                if not support.get("source_validation"):
                    call([*compose, "pull", "--policy", "missing", "--", *support["services"]], env)
                support_check(workspace, env, configuration=json.loads(configuration), prepared=support)
            configuration_hash = hashlib.sha256(configuration.encode()).hexdigest()
            receipt = Path(env.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "xorder/uxor" / key / (project + ".json")
            try:
                previous = json.loads(receipt.read_text())
            except (OSError, ValueError):
                previous = {}
            if reuse_only:
                if shared:
                    # Copy receiver recipe sources into private demo destinations.
                    # Dependency binds already prevent this command from writing
                    # through to donor files. Use the same project-owned contract
                    # as explicit sync/check/plant operations.
                    sync = load_contract(workspace, PROFILE)["sync"]["command"]
                    call([*compose, "run", "--rm", "--no-deps", "--entrypoint", "bash", "php",
                          "/run/xorder/startup.sh", "--entrypoint", "--seed-sync", *sync], env)
                # Inspect before Compose can start/recreate application services.
                # Initialize only private home/var ownership and trust, then
                # inspect as PUID without application setup or server hooks.
                call([*compose, "run", "--rm", "--no-deps", "--entrypoint", "bash", "php",
                      "/run/xorder/startup.sh", "--entrypoint", "--check-reuse"], env)
            call([*compose, "up", "--wait", "--wait-timeout", "600", "--no-build"], env)
            if support_required(workspace, env):
                support_check(workspace, env, containers=containers(project, env), prepared=support)
            # Recheck lockfiles even when Compose retained an existing container.
            php_exec(compose, env, "bash", "/run/xorder/startup.sh", "--prepare", cwd="/app/demo")
            npm = php_exec(compose, env, "node", "/run/xorder/node-state.cjs", "inspect" if reuse_only else "verify", capture=True, check=False, observational=True)
            if npm.returncode:
                if reuse_only:
                    raise ValueError("Reuse-only npm dependencies changed or are incomplete: " + npm.stderr.strip())
                php_exec(compose, env, "npm", "ci")
                npm = php_exec(compose, env, "node", "/run/xorder/node-state.cjs", "record", capture=True)
            composer_state = (php_exec(compose, env, "php", "/run/xorder/verify-composer.php", "fingerprint", cwd="/app/demo", capture=True)
                              if reuse_only else php_exec(compose, env, "cat", "var/xorder/composer-ready", cwd="/app/demo", capture=True)).stdout.strip()
            current = {"configuration": configuration_hash, "inputs": env["XORDER_INPUT_FINGERPRINT"],
                       "containers": sorted(container["Id"] for container in containers(project, env)),
                       "composer": composer_state, "npm": npm.stdout.strip(), "reuse_only": reuse_only}
            if previous != current:
                # Only a previously successful exact setup can reuse its test cache.
                # Startup already compiles CSS in a new service. Refresh retained
                # services after source changes without compiling twice on cold up.
                if previous.get("containers") == current["containers"] and previous.get("inputs") != current["inputs"]:
                    php_exec(compose, env, "php", "bin/console", "tailwind:build", "--no-interaction", cwd="/app/demo")
                php_exec(compose, env, "php", "bin/console", "cache:warmup", "--env=test", cwd="/app/demo")
            php_exec(compose, env, "curl", "--fail", "--silent", "--show-error", "--insecure", "--noproxy", "*", "--max-time", "15", "https://localhost" + env.get("APP_READY_PATH", "/"))
            receipt.parent.mkdir(parents=True, exist_ok=True)
            (receipt.parent / "workspace.json").write_text(json.dumps({"workspace": str(workspace)}))
            temporary_receipt = receipt.with_suffix(".tmp")
            temporary_receipt.write_text(json.dumps(current))
            temporary_receipt.replace(receipt)
            print(f"Ready: {project} http://localhost:{http} https://localhost:{https}")
        elif action == "test":
            with heavy_run(workspace, env) as workers:
                print(f"Test budget acquired; automatic worker budget {workers}", flush=True)
                return run_test(compose, env, workspace, project, extra, workers=workers)
        elif action == "sync":
            sync_contract(contract, lambda command: php_exec(compose, env, *command, capture=True, check=False), check=extra == ["--check"])
        elif action == "plant":
            with heavy_run(workspace, env) as workers:
                return run_plant(workspace, env, contract, extra,
                                 lambda command: php_exec(compose, env, *command, capture=True, check=False),
                                 lambda arguments: run_test(compose, env, workspace, project, arguments, workers=workers))
        elif action == "cache":
            support_check(workspace, env, configuration=json.loads(call([*compose, "config", "--format", "json"], env, capture=True).stdout))
            if extra and extra[0] == "import":
                sync = load_contract(workspace, PROFILE)["sync"]["command"]
                call([*compose, "run", "--rm", "--no-deps", "--entrypoint", "bash", "php",
                      "/run/xorder/startup.sh", "--entrypoint", "--seed-sync", *sync], env)
            call([*compose, "run", "--rm", "--no-deps", "-T", "--workdir", "/app/demo",
                  "--entrypoint", "bash", "php", "/usr/local/bin/library-entrypoint",
                  "python3", "/run/xorder/cache.py", *extra], env)
        elif action == "phpunit":
            call([*compose, "exec", "-T", "--user", f'{env["PUID"]}:{env["PGID"]}', "-w", "/app/demo",
                  "-e", "XDEBUG_MODE=" + env.get("PHPUNIT_XDEBUG_MODE", "off"), "-e", "APP_ENV=test", "-e", "APP_DEBUG=1",
                  "-e", "CREATE_SNAPSHOTS=false", "php", "php", "bin/phpunit", *extra], env)
        elif action == "php-tests":
            php_exec(compose, env, "bash", "/run/xorder/php-tests.sh", *extra,
                     forwarded=PHP_TEST_ENVIRONMENT)
        elif action == "exec":
            php_exec(compose, env, *extra)
        else:
            call([*compose, action, *extra], env)
            if action == "down":
                stop(proxy_owner)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]) or 0)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"xorder uxor: {error}", file=sys.stderr)
        sys.exit(64)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end="")
        sys.exit(error.returncode)
