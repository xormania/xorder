"""Prove installed image tools offline without consumer imports or model calls."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


NAMES = ("codex", "claude", "grok")
DISTRIBUTIONS = {"codex": "npm-package-lock", "claude": "signed-native-release",
                 "grok": "signed-npm-platform-package"}


def command(*argv):
    result = subprocess.run(argv, check=True, capture_output=True, text=True,
                            stdin=subprocess.DEVNULL, timeout=90)
    return result.stdout


def validate_status(status, pins):
    for name in NAMES:
        receipt = status["harnesses"][name]
        if (receipt.get("status") != "installed" or receipt.get("integrity") != "passed"
                or receipt.get("version") != pins["harnesses"][name]["version"]):
            raise RuntimeError("Selected harness is incomplete or changed: " + name)
        if (receipt.get("provenance", {}).get("distribution") != DISTRIBUTIONS[name]
                or not receipt["provenance"].get("source")
                or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("sha256", ""))):
            raise RuntimeError("Selected harness lacks release provenance: " + name)


def cli_check(name, expected):
    output = command(name, "--version").strip()
    if not re.search(r"(?<![0-9.])" + re.escape(expected) + r"(?![0-9A-Za-z._-])", output):
        raise RuntimeError("Harness launcher did not execute selected version: " + name)
    if name == "codex":
        # Generate and parse an actual CLI artifact; project protocol extensions
        # and adapter-specific schema fields belong to the consuming project.
        with tempfile.TemporaryDirectory(prefix="xorder-schema-") as directory:
            command(name, "app-server", "generate-json-schema", "--out", directory)
            documents = [json.loads(path.read_text()) for path in Path(directory).rglob("*.json")]
            if not documents or not all(isinstance(value, dict) for value in documents):
                raise RuntimeError("Codex did not generate JSON schema documents")
        facts = {"operation": "app-server generate-json-schema", "schema_files": len(documents)}
    else:
        argv = (name, "agent", "stdio", "--help") if name == "grok" else (name, "--help")
        help_text = command(*argv)
        if not help_text.strip():
            raise RuntimeError("Harness help operation returned no output: " + name)
        facts = {"operation": " ".join(argv[1:]), "help_output": True}
    return {"version_output": output, **facts, "live_round_trip": "unverified"}


def main():
    if os.environ["HOME"] != "/home/dev":
        raise RuntimeError("Harness HOME must persist for root and non-root users")
    credentials = (".codex/auth.json", ".claude/.credentials.json", ".grok/auth.json")
    if any((Path.home() / name).exists() for name in credentials):
        raise RuntimeError("Image acceptance HOME contains vendor account credentials")
    pins = json.loads(Path("/usr/local/share/xorder/harness-pins.json").read_text())
    before = json.loads(command("harnesses", "status"))
    validate_status(before, pins)
    # A replacement disconnected container must reuse every installed selection.
    command("harnesses", "ensure")
    after = json.loads(command("harnesses", "status"))
    if before != after:
        raise RuntimeError("Readiness changed selected versions or installation receipts")
    validate_status(after, pins)
    observations = {name: cli_check(name, after["harnesses"][name]["version"]) for name in NAMES}
    native = json.loads(command(sys.executable, "-I", "/runtime/check.py"))
    return {"schema_version": 2, "fixture": "xorder-harness-image-capabilities", "uid": os.getuid(),
            "installed": after, "harnesses": observations, "native_runtime": native,
            "network": "none", "authenticated": False, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
