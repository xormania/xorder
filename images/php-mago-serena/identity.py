"""Capture installed tool identity; the browser child regenerates the same record."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path("/opt/xorder/serena")


def version(*args):
    return subprocess.check_output(args, text=True, timeout=30).splitlines()[0].strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect():
    lock = json.loads((ROOT / "toolchain.lock.json").read_text())
    record = {
        "lock": lock,
        "php": version("php", "-v"),
        "composer": version("composer", "--version"),
        "node": None,
        "chrome_for_testing": None,
        "chromium_base": version("/usr/bin/chromium", "--version"),
        "symfony_cli": version("symfony", "version", "--no-ansi"),
        "mago": version("mago", "--version"),
        "mago_native": version("mago-native", "--version"),
        "mago_native_binary_sha256": sha("/usr/local/bin/mago-native"),
        "mago_binary_sha256": sha("/usr/local/bin/mago"),
        "mago_baseline": version("mago-baseline", "--version"),
        "mago_baseline_binary_sha256": sha("/usr/local/bin/mago-baseline"),
        "mago_source_sha": (ROOT / "mago-source.sha").read_text().strip(),
        "mago_patch_sha256": (ROOT / "mago-patch.sha256").read_text().split()[0],
        "mago_cargo_lock_sha256": (ROOT / "mago-cargo-lock.sha256").read_text().split()[0],
        "mago_rust_version": (ROOT / "mago-rust-version.txt").read_text().strip(),
        "python": version("/usr/local/bin/python3", "--version"),
        "uv": version("uv", "--version"),
        "serena": json.loads((ROOT / "serena-patch.json").read_text()),
        "serena_facade_sha256": sha("/opt/venv/lib/python3.12/site-packages/serena/repl/api/lsp_api.py"),
        "serena_uv_lock_sha256": sha(ROOT / "uv.lock"),
        "serena_dependency_patch_sha256": sha(ROOT / "security.patch"),
        "serena_manifest_sha256": (ROOT / "serena-manifest.sha256").read_text().split()[0],
        "chrome_binary_sha256": None,
        "chrome_devtools_mcp": None,
    }
    if record["mago_native"] != "mago " + lock["native_mago"]["version"]:
        raise RuntimeError("Native Mago executable differs from the selected release")
    if record["mago_source_sha"] != lock["mago"]["sdk"]["source_rev"]:
        raise RuntimeError("Experimental Mago backend and PHP SDK source revisions differ")
    if record["serena"]["source"] != lock["serena"]["source_rev"]:
        raise RuntimeError("Installed Serena source differs from the selected revision")
    if record["serena_uv_lock_sha256"] != lock["serena"]["effective_uv_lock_sha256"]:
        raise RuntimeError("Installed Serena dependency lock differs from the selected inputs")
    if (record["serena_dependency_patch_sha256"] != lock["serena"]["dependency_patch_sha256"]
            or record["serena_manifest_sha256"] != lock["serena"]["effective_manifest_sha256"]):
        raise RuntimeError("Installed Serena dependency patch differs from the selected inputs")
    # These tools are absent on the slow line; null keeps one explicit schema.
    chrome_lock = Path("/opt/xorder/chrome-toolchain.lock.json")
    if chrome_lock.is_file():
        browser = json.loads(chrome_lock.read_text())
        record["chrome_lock"] = browser
        expected = browser["browser"]["chrome_for_testing"]
        installed = Path("/opt/chrome-version").read_text().strip()
        if installed != expected:
            raise RuntimeError("Installed Chrome version differs from the locked input")
        chrome_version = version("/opt/chrome-linux64/chrome", "--version")
        if chrome_version.rsplit(" ", 1)[-1] != expected:
            raise RuntimeError("Chrome executable version differs from the locked input")
        record.update(
            node=version("node", "--version"),
            chrome_for_testing=chrome_version,
            chrome_binary_sha256=sha("/opt/chrome-linux64/chrome"),
            chrome_devtools_mcp=json.loads(Path("/usr/local/lib/node_modules/chrome-devtools-mcp/package.json").read_text())["version"],
        )
        if record["chrome_devtools_mcp"] != browser["mcp"]["chrome_devtools_mcp"]:
            raise RuntimeError("Installed Chrome DevTools MCP differs from the locked input")
    return record


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
