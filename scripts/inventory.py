#!/usr/bin/env python3
"""Run inside the tested container; collect facts, not declared capabilities."""
import json
import hashlib
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path


def run(*command):
    output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output).strip()


family = sys.argv[1]
tools = {}
commands = {"bash": ["bash", "--version"], "git": ["git", "--version"], "gh": ["gh", "--version"],
            "curl": ["curl", "--version"], "jq": ["jq", "--version"], "rg": ["rg", "--version"],
            "psql": ["psql", "--version"]}
extensions = {}
if family == "harness-live":
    runtime = run("python3", "-c", "import platform; print(platform.python_version())")
    commands.update({"python": ["python3", "--version"], "node": ["node", "--version"],
                     "npm": ["npm", "--version"], "tmux": ["tmux", "-V"],
                     "harnesses": ["harnesses", "--version"]})
elif family.startswith("php") or family == "uxor-dev":
    runtime = run("php", "-r", "echo PHP_VERSION;")
    extensions = json.loads(run("php", "-r", '$out=[]; foreach(get_loaded_extensions() as $e) {$out[strtolower($e)]=phpversion($e) ?: "bundled";} echo json_encode($out);'))
    commands.update({"php": ["php", "--version"], "composer": ["composer", "--version"], "symfony": ["symfony", "version"]})
    commands.update({"library-php-coverage": ["library-php-coverage", "--version"],
                     "library-php-tests": ["library-php-tests", "--version"],
                     "phpstan-isolated": ["php", "/opt/xorder/php-tools/vendor/bin/phpstan", "--version"]})
    commands["infection"] = ["infection", "--version"]
    if family == "php-serena":
        commands.update({"library-serena": ["library-serena", "--version"],
                         "phpactor": ["php", "/opt/xorder/serena/phpactor.phar", "--version"],
                         "uv": ["uv", "--version"]})
    if family == "php-browser":
        commands.update({"chromium": ["chromium", "--version"], "chromedriver": ["chromedriver", "--version"]})
    if family in ("php-frankenphp", "uxor-dev"):
        commands["frankenphp"] = ["frankenphp", "version"]
    if family == "uxor-dev":
        commands.update({"node": ["node", "--version"], "npm": ["npm", "--version"],
                         "tailwindcss": ["tailwindcss", "--help"]})
elif family == "python-dev":
    runtime = run("python", "-c", "import platform; print(platform.python_version())")
    commands.update({"python": ["python", "--version"], "uv": ["uv", "--version"], "pip": ["python", "-m", "pip", "--version"]})
elif family == "rust-dev":
    runtime = run("rustc", "--version").split()[1]
    commands.update({"rustc": ["rustc", "--version"], "cargo": ["cargo", "--version"], "rustfmt": ["rustfmt", "--version"], "clippy": ["cargo", "clippy", "--version"], "rustup": ["rustup", "--version"]})
elif family == "playwright-browser":
    runtime = run("node", "-p", "require('/opt/playwright/node_modules/playwright/package.json').version")
    commands = {"node": ["node", "--version"], "playwright": ["playwright", "--version"]}
else:
    raise SystemExit("Unknown family")
for tool, command in commands.items():
    tools[tool] = run(*command).splitlines()[0]
os_release = {}
for line in Path("/etc/os-release").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os_release[k] = shlex.split(v)[0]
result = {"platform": "linux/" + {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()],
          "runtime_version": runtime, "tools": tools, "extensions": extensions,
          "os": os_release, "packages": run("dpkg-query", "-W", "-f=${Package}=${Version}\\n").splitlines()}
if family == "rust-dev":
    result["rust_targets"] = run("rustup", "target", "list", "--installed").splitlines()
if family == "php-serena":
    tools["node"] = run("node", "--version")
    tools["typescript-language-server"] = run("/opt/xorder/serena/javascript/node_modules/.bin/typescript-language-server", "--version")
    upstream_lock = Path("/opt/xorder/serena/upstream-uv.lock")
    if not upstream_lock.exists():
        upstream_lock = Path("/opt/serena-source/uv.lock")
    result["serena"] = {
        "source_revision": run("git", "-c", "safe.directory=/opt/serena-source", "-C", "/opt/serena-source", "rev-parse", "HEAD"),
        "upstream_lock_sha256": hashlib.sha256(upstream_lock.read_bytes()).hexdigest(),
        "effective_lock_sha256": hashlib.sha256(Path("/opt/serena-source/uv.lock").read_bytes()).hexdigest(),
        "phpactor_sha256": hashlib.sha256(Path("/opt/xorder/serena/phpactor.phar").read_bytes()).hexdigest(),
        "python_version": run("/opt/serena-env/bin/python", "--version"),
    }
if family == "php-toolkit":
    result["prepared_projects"] = {}
    for name in ("validator", "symfony-7.4"):
        project = Path("/opt/xorder/php-toolkit") / name
        installed = json.loads((project / "vendor/composer/installed.json").read_text())
        result["prepared_projects"][name] = {
            "composer_lock_sha256": hashlib.sha256((project / "composer.lock").read_bytes()).hexdigest(),
            "packages": {package["name"]: package["version"] for package in installed["packages"]},
        }
print(json.dumps(result, indent=2, sort_keys=True))
