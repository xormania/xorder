#!/usr/bin/env python3
"""Install and select versioned harnesses without changing active sessions."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import shlex
import stat
import subprocess
import sys
import tempfile

VERSION = "1.0.0"
HELPERS = Path(__file__).resolve().parent
if not (HELPERS / "root_trust.py").is_file():
    HELPERS = Path("/usr/local/share/xorder")


def helper(name):
    spec = importlib.util.spec_from_file_location("xorder_harness_" + name, HELPERS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT_TRUST = helper("root_trust")
CURL = "/usr/bin/curl"
NPM = "/usr/local/bin/npm"
NAMES = ("codex", "claude", "grok")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9._-]+)?\Z")
LATEST = {"claude": "https://downloads.claude.ai/claude-code-releases/latest",
          "grok": "https://x.ai/cli/stable"}


def version(value):
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise ValueError("Expected an exact X.Y.Z version (optional prerelease suffix)")
    return value


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_hashes(directory):
    """Bind dependencies, executable/traversal permissions and link destinations."""
    hashes = {".": {"type": "directory", "mode": stat.S_IMODE(directory.stat().st_mode)}}
    for path in sorted(directory.rglob("*")):
        if path.name == "receipt.json" and path.parent == directory:
            continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Installed symlink escapes version directory")
            hashes[str(path.relative_to(directory))] = {"symlink": os.readlink(path)}
        elif path.is_file():
            hashes[str(path.relative_to(directory))] = {"sha256": sha256(path),
                                                       "mode": stat.S_IMODE(path.stat().st_mode)}
        elif path.is_dir():
            hashes[str(path.relative_to(directory))] = {"type": "directory",
                                                       "mode": stat.S_IMODE(path.stat().st_mode)}
        else:
            raise ValueError("Unsupported installed file type: " + str(path))
    return hashes


def run(command, *, env, timeout=600, input_text=None, check=True):
    """Bound installers and their children; leave no downloader after timeout."""
    process = subprocess.Popen(command, env=env, text=True, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise ValueError("Command timed out: " + command[0]) from None
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check and result.returncode:
        # Installer output may include environment-specific details; do not persist it.
        raise ValueError(f"Command failed ({result.returncode}): {command[0]}\n{stderr[-4000:]}")
    return result


def isolated_environment(home):
    """Only transport/runtime settings cross into installation and probes."""
    keys = ("PATH", "LANG", "LC_ALL", "TERM", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    env.update(HOME=str(home), XDG_CACHE_HOME=str(home / ".cache"),
               XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
               DISABLE_AUTOUPDATER="1", GROK_DISABLE_AUTOUPDATER="1",
               npm_config_update_notifier="false", npm_config_audit="false",
               npm_config_fund="false", npm_config_userconfig=str(home / ".npmrc"),
               npm_config_globalconfig=str(home / "npm-globalrc"), npm_config_cache=str(home / ".npm"))
    return env


def runtime_environment():
    env = dict(os.environ)
    env.update(DISABLE_AUTOUPDATER="1", DISABLE_UPDATES="1", GROK_DISABLE_AUTOUPDATER="1")
    return env


def fetch(url, destination, env):
    run([CURL, "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
         "--proto-redir", "=https", "--connect-timeout", "15", "--max-time", "180",
         "--retry", "2", "--output", str(destination), url], env=env, timeout=570)


def command_for(name, executable, args):
    prefix = [str(executable)]
    if name == "codex":
        prefix += ["-c", "check_for_update_on_startup=false"]
    elif name == "grok" and "--no-auto-update" not in args:
        prefix += ["--no-auto-update"]
    return prefix + args


def probe(name, executable, expected, env):
    output = run(command_for(name, executable, ["--version"]), env=env, timeout=30).stdout.strip()
    if not re.search(r"(?<![0-9.])" + re.escape(expected) + r"(?![0-9A-Za-z._-])", output):
        raise ValueError(f"{name} version mismatch: expected {expected}, got {output!r}")
    if name == "codex":
        with tempfile.TemporaryDirectory(prefix="harness-schema-") as directory:
            run(command_for(name, executable, ["app-server", "generate-json-schema", "--experimental", "--out", directory]),
                env=env, timeout=30)
            schemas = [json.loads(path.read_text()) for path in Path(directory).rglob("*.json")]
            definitions = {}
            for schema in schemas:
                definitions.update(schema.get("definitions", {}))
                definitions.update(schema.get("$defs", {}))
                if schema.get("title"):
                    definitions[schema["title"]] = schema
            for model, fields in {"TurnStartParams": {"input", "threadId", "toolOutput"},
                                  "ThreadStartParams": {"dynamicTools"}}.items():
                if not fields <= set(definitions.get(model, {}).get("properties", {})):
                    raise ValueError("Codex schema lacks required fields: " + model)
    elif name == "claude":
        help_text = run([str(executable), "--help"], env=env, timeout=30).stdout
        if not all(flag in help_text for flag in ("--session-id", "--mcp-config", "--debug-file")):
            raise ValueError("Claude help lacks required launcher flags")
        result = run([str(executable), "--dangerously-load-development-channels", "server:xordination", "--print"],
                     env=env, timeout=30, input_text="", check=False)
        message = result.stdout + result.stderr
        if result.returncode == 0 or "Input must be provided" not in message or "unknown option" in message:
            raise ValueError("Claude development-channel probe did not reject empty input as expected")
    else:
        run(command_for(name, executable, ["agent", "stdio", "--help"]), env=env, timeout=30)
    return output


class Manager:
    def __init__(self, root, pins):
        self.root = Path(root).expanduser().absolute()
        self.pins_path = Path(pins)
        ROOT_TRUST.validate_root_store(self.root)

    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        ROOT_TRUST.validate_root_store(self.root)
        with (self.root / ".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def state(self):
        if not self.root.exists() and not self.root.is_symlink():
            return {"schema_version": 1, "harnesses": {}}
        ROOT_TRUST.validate_root_store(self.root, require_exists=True)
        return read_json(self.root / "selected.json", {"schema_version": 1, "harnesses": {}})

    def installation(self, name, selected_version):
        if name not in NAMES:
            raise ValueError("Unknown harness: " + name)
        return self.root / "versions" / name / version(selected_version)

    def receipt(self, name, selected_version):
        directory = self.installation(name, selected_version)
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Version directory escapes installation root")
        receipt = read_json(directory / "receipt.json")
        if receipt.get("name") != name or receipt.get("version") != selected_version:
            raise ValueError("Installed receipt identity mismatch")
        executable = (directory / receipt["executable"]).resolve()
        if not executable.is_relative_to(directory.resolve()) or not executable.is_file():
            raise ValueError("Installed executable escapes its immutable version directory")
        return receipt, executable

    def status(self, names):
        result = {"schema_version": 1, "root": str(self.root), "harnesses": {}}
        try:
            state = self.state()
        except (ValueError, OSError) as error:
            result["harnesses"] = {name: {"status": "invalid", "integrity": "failed", "detail": str(error)}
                                   for name in names}
            return result
        for name in names:
            selected = state["harnesses"].get(name)
            if selected is None:
                result["harnesses"][name] = {"status": "not_installed"}
            else:
                try:
                    receipt, executable = self.receipt(name, selected["version"])
                except (ValueError, OSError) as error:
                    result["harnesses"][name] = {"status": "invalid", "version": selected["version"],
                                                "integrity": "failed", "detail": str(error)}
                    continue
                result["harnesses"][name] = {**{key: value for key, value in receipt.items() if key != "files"}, "executable": str(executable),
                    "status": "installed", "previous": selected.get("previous"),
                    "integrity": "passed" if self.integrity(name, selected["version"], receipt) else "failed"}
        return result

    def integrity(self, name, selected_version, receipt):
        try:
            return file_hashes(self.installation(name, selected_version)) == receipt["files"]
        except (ValueError, OSError):
            return False

    def wrappers(self):
        directory = self.root / "bin"
        directory.mkdir(exist_ok=True)
        for name in NAMES:
            path = directory / name
            content = '#!/bin/sh\nexec /usr/local/bin/harnesses --root ' + shlex.quote(str(self.root)) + ' exec ' + name + ' -- "$@"\n'
            if not path.exists() or path.read_text() != content:
                fd, temporary = tempfile.mkstemp(prefix=".launcher-", dir=directory)
                with os.fdopen(fd, "w") as stream:
                    stream.write(content)
                Path(temporary).chmod(0o755)
                os.replace(temporary, path)

    def activate(self, name, selected_version):
        receipt, executable = self.receipt(name, selected_version)
        if not self.integrity(name, selected_version, receipt) or not os.access(executable, os.X_OK):
            raise ValueError("Installed harness bytes or executable permissions changed")
        state = self.state()
        current = state["harnesses"].get(name, {})
        previous = current.get("version")
        if previous != selected_version:
            state["harnesses"][name] = {"version": selected_version, "previous": previous}
            atomic_json(self.root / "selected.json", state)
        self.wrappers()

    def install(self, name, selected_version):
        selected_version = version(selected_version)
        final = self.installation(name, selected_version)
        if final.exists():
            receipt, executable = self.receipt(name, selected_version)
            if not self.integrity(name, selected_version, receipt):
                raise ValueError("Installed binary checksum changed; preserve evidence and choose another version")
        else:
            final.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".install-", dir=final.parent) as temporary:
                stage = Path(temporary)
                home = stage / "installer-home"
                home.mkdir(mode=0o700)
                env = isolated_environment(home)
                (stage / "bin").mkdir()
                if name == "codex":
                    run([NPM, "install", "--prefix", str(stage / "npm"), "--save-exact", "--ignore-scripts",
                         "--include=optional", "--no-audit", "--no-fund", "--registry=https://registry.npmjs.org",
                         "@openai/codex@" + selected_version], env=env)
                    executable = stage / "npm/node_modules/.bin/codex"
                    provenance = {"distribution": "npm-package-lock",
                                  "source": "https://registry.npmjs.org/@openai/codex/" + selected_version}
                else:
                    executable, provenance = helper("provenance").install_native(
                        name, selected_version, stage, env, fetch, run)
                output = probe(name, executable, selected_version, env)
                # Never retain installer-generated config or home/account state.
                shutil.rmtree(home)
                receipt = {"schema_version": 1, "name": name, "version": selected_version,
                           "executable": str(executable.relative_to(stage)), "version_output": output,
                           "sha256": sha256(executable.resolve()), "provenance": provenance,
                           "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           "files": file_hashes(stage)}
                lock = stage / "npm/package-lock.json"
                if lock.is_file():
                    receipt["package_lock_sha256"] = sha256(lock)
                atomic_json(stage / "receipt.json", receipt)
                stage.rename(final)
            try:
                # Native/npm paths must also work after moving the staged installation.
                with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.root) as verification_home:
                    probe(name, self.receipt(name, selected_version)[1], selected_version,
                          isolated_environment(Path(verification_home)))
            except BaseException:
                shutil.rmtree(final)
                raise
        self.activate(name, selected_version)

    def ensure(self, names):
        pins = read_json(self.pins_path)["harnesses"]
        for name in names:
            selected = self.state()["harnesses"].get(name)
            if selected:
                receipt, executable = self.receipt(name, selected["version"])
                if not self.integrity(name, selected["version"], receipt):
                    raise ValueError("Selected harness installation changed: " + name)
            else:
                self.install(name, pins[name]["version"])
        self.wrappers()

    def latest(self, name):
        with tempfile.TemporaryDirectory(prefix="harness-update-") as directory:
            home = Path(directory)
            env = isolated_environment(home)
            if name == "codex":
                output = run([NPM, "view", "@openai/codex", "version", "--registry=https://registry.npmjs.org"],
                             env=env, timeout=60).stdout.strip()
            else:
                target = home / "latest"
                fetch(LATEST[name], target, env)
                output = target.read_text().strip()
            return version(output)

    def rollback(self, name, target=None):
        current = self.state()["harnesses"].get(name, {})
        target = target or current.get("previous")
        if target is None:
            raise ValueError("No previous selected version for " + name)
        receipt, executable = self.receipt(name, version(target))
        if not self.integrity(name, target, receipt):
            raise ValueError("Rollback installation checksum changed")
        self.activate(name, target)

    def execute(self, name, args):
        selected = self.state()["harnesses"].get(name)
        if selected is None:
            raise ValueError(name + " is not installed; run harnesses ensure")
        receipt, executable = self.receipt(name, selected["version"])
        if not self.integrity(name, selected["version"], receipt) or not os.access(executable, os.X_OK):
            raise ValueError("Installed harness bytes or executable permissions changed")
        # Resolve npm launcher symlinks now; later selection changes cannot redirect this process.
        command = command_for(name, executable, args)
        os.execve(str(executable), command, runtime_environment())


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version="harnesses " + VERSION)
    result.add_argument("--root", default=os.environ.get("HARNESS_ROOT", "/home/dev/.local/share/xorder/harnesses"))
    result.add_argument("--pins", default=os.environ.get("HARNESS_PINS", "/usr/local/share/xorder/harness-pins.json"))
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("ensure", "status", "check-updates"):
        command = commands.add_parser(name)
        command.add_argument("names", nargs="*", choices=NAMES)
    install = commands.add_parser("install")
    install.add_argument("name", choices=NAMES)
    install.add_argument("version")
    update = commands.add_parser("update")
    update.add_argument("name", choices=NAMES)
    update.add_argument("--version", dest="selected_version")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("name", choices=NAMES)
    rollback.add_argument("version", nargs="?")
    execute = commands.add_parser("exec")
    execute.add_argument("name", choices=NAMES)
    execute.add_argument("args", nargs=argparse.REMAINDER)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    manager = Manager(args.root, args.pins)
    names = getattr(args, "names", None) or NAMES
    if args.command == "status":
        result = manager.status(names)
    elif args.command == "check-updates":
        state = manager.state()["harnesses"]
        result = {"schema_version": 1, "harnesses": {name: {"installed": state.get(name, {}).get("version"),
                  "latest": manager.latest(name)} for name in names}}
    elif args.command == "exec":
        manager.execute(args.name, args.args[1:] if args.args[:1] == ["--"] else args.args)
        return
    else:
        with manager.locked():
            if args.command == "ensure":
                manager.ensure(names)
            elif args.command == "install":
                manager.install(args.name, args.version)
            elif args.command == "update":
                manager.install(args.name, args.selected_version or manager.latest(args.name))
            elif args.command == "rollback":
                manager.rollback(args.name, args.version)
        result = manager.status(names if args.command == "ensure" else [args.name])
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print("harnesses: " + str(error), file=sys.stderr)
        raise SystemExit(1)
