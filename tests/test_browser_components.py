"""Execute runtime assembly recipes without allowing browser payload downloads."""
import os
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import components


def runtime_runs(family):
    source = (ROOT / "images" / family / "Dockerfile").read_text().replace("\\\n", " ")
    commands = []
    for line in source.splitlines():
        if line.startswith("RUN "):
            command = line.removeprefix("RUN ")
            while command.startswith("--mount="):
                command = command.split(None, 1)[1]
            commands.append(command)
    return commands


class BrowserAssemblyTests(unittest.TestCase):
    def exercise(self, family):
        with tempfile.TemporaryDirectory(prefix="browser assembly ") as directory:
            folder = Path(directory)
            log = folder / "commands"
            recorder = folder / "record-command"
            recorder.write_text("#!/bin/sh\nname=${0##*/}\nprintf '%s' \"$name\" >> \"$COMMAND_LOG\"\n"
                                "printf ' %s' \"$@\" >> \"$COMMAND_LOG\"\nprintf '\\n' >> \"$COMMAND_LOG\"\n"
                                "case \"$name:$1\" in curl:*|unzip:*|npm:ci|playwright:install) exit 97;; esac\n")
            recorder.chmod(0o755)
            for name in ("npm", "curl", "unzip", "playwright", "mv", "ln", "apt-get", "rm",
                         "useradd", "mkdir", "chmod", "python", "python3"):
                (folder / name).symlink_to(recorder)
            for recipe in runtime_runs(family):
                recipe = recipe.replace("/opt/playwright/node_modules/.bin/playwright", shlex.quote(str(folder / "playwright")))
                recipe = recipe.replace("/opt/xorder/image-identity.json", shlex.quote(str(folder / "identity.json")))
                result = subprocess.run(["bash", "-euc", recipe], capture_output=True, text=True, timeout=5,
                                        env={**os.environ, "PATH": str(folder) + ":" + os.environ["PATH"],
                                             "COMMAND_LOG": str(log), "APT_REFRESH": "observed-package-index"})
                if result.returncode:
                    break
            return result, log.read_text() if log.exists() else ""

    def test_playwright_runtime_assembles_retained_payload_with_all_engine_dependencies(self):
        result, commands = self.exercise("playwright-browser")
        self.assertEqual(result.returncode, 0, result.stderr + commands)
        self.assertIn("playwright install-deps chromium firefox webkit\n", commands)
        self.assertIn("10-sub-pixel-rgb.conf", commands)
        self.assertIn("10-sub-pixel-none.conf.disabled", commands)

    def test_playwright_payload_identity_survives_runtime_and_apt_refresh_but_tracks_its_npm_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "images", root / "images")
            shutil.copytree(ROOT / "schemas", root / "schemas")
            shutil.copyfile(ROOT / ".dockerignore", root / ".dockerignore")
            payload = "playwright-1-58-payload"
            original = components.build_key(payload, root)
            tools_path = root / "images/tools.json"
            tools = json.loads(tools_path.read_text())
            tools["apt_indexes"] = {key: "f" * 64 for key in tools["apt_indexes"]}
            tools_path.write_text(json.dumps(tools))
            runtime_path = root / "images/playwright-browser/definition.json"
            runtime = json.loads(runtime_path.read_text())
            runtime["lines"]["1.58-trixie"]["base"]["digest"] = "sha256:" + "e" * 64
            runtime_path.write_text(json.dumps(runtime))
            self.assertEqual(components.build_key(payload, root), original)
            npm_lock = root / "images/playwright-browser/lines/1.58-trixie/package-lock.json"
            npm_lock.write_bytes(npm_lock.read_bytes() + b"\n")
            self.assertNotEqual(components.build_key(payload, root), original)


if __name__ == "__main__":
    unittest.main()
