"""Exercise Chrome component reuse and final assembly without browser downloads."""
import os
import json
import importlib.util
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


class ChromeComponentTests(unittest.TestCase):
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
                recipe = recipe.replace("/opt/xorder/chrome-toolchain.lock.json", shlex.quote(str(folder / "chrome-lock.json")))
                result = subprocess.run(["bash", "-euc", recipe], capture_output=True, text=True, timeout=5,
                                        env={**os.environ, "PATH": str(folder) + ":" + os.environ["PATH"],
                                             "COMMAND_LOG": str(log), "APT_REFRESH": "observed-package-index"})
                if result.returncode:
                    break
            return result, log.read_text() if log.exists() else ""


    def test_chrome_runtime_composes_payloads_without_fetching_browser_or_npm_packages(self):
        result, commands = self.exercise("php-chrome-dev")
        self.assertEqual(result.returncode, 0, result.stderr + commands)
        self.assertIn("python /opt/xorder/serena/identity.py\n", commands)
        self.assertNotIn("npm ci", commands)
        self.assertNotIn("curl ", commands)


    def test_chrome_browser_identity_is_independent_of_mcp_and_php_refreshes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("images", "schemas", "scripts"):
                shutil.copytree(ROOT / name, root / name)
            shutil.copyfile(ROOT / ".dockerignore", root / ".dockerignore")
            browser, mcp, node = "chrome-for-testing-157", "chrome-devtools-mcp-1-12", "node-chrome-22"
            before = {name: components.build_key(name, root) for name in (browser, mcp, node)}
            package_path = root / "images/php-chrome-dev/package.json"
            package = json.loads(package_path.read_text())
            package["dependencies"]["chrome-devtools-mcp"] = "1.12.1"
            package_path.write_text(json.dumps(package))
            php_path = root / "images/php-dev/definition.json"
            php = json.loads(php_path.read_text())
            php["lines"]["8.4-trixie"]["base"]["digest"] = "sha256:" + "a" * 64
            php_path.write_text(json.dumps(php))
            self.assertEqual(components.build_key(browser, root), before[browser])
            self.assertEqual(components.build_key(node, root), before[node])
            self.assertNotEqual(components.build_key(mcp, root), before[mcp])
            browser_lock = root / "images/components/chrome-for-testing-157/toolchain.lock.json"
            lock = json.loads(browser_lock.read_text())
            lock["browser"]["archive_sha256"] = "b" * 64
            browser_lock.write_text(json.dumps(lock))
            self.assertNotEqual(components.build_key(browser, root), before[browser])


    def test_runtime_chrome_lock_expands_browser_and_mcp_owned_pins(self):
        spec = importlib.util.spec_from_file_location("compose_chrome_component_lock", ROOT / "images/php-chrome-dev/compose-lock.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "components").mkdir()
            (root / "chrome-devtools").mkdir()
            shutil.copyfile(ROOT / "images/php-chrome-dev/toolchain.lock.json", root / "chrome-composition.lock.json")
            shutil.copyfile(ROOT / "images/components/chrome-for-testing-157/toolchain.lock.json", root / "components/chrome-for-testing-157.lock.json")
            package_path = root / "chrome-devtools/package.json"
            shutil.copyfile(ROOT / "images/php-chrome-dev/package.json", package_path)
            value = module.compose(root)
            self.assertEqual(value["browser"], json.loads((root / "components/chrome-for-testing-157.lock.json").read_text())["browser"])
            self.assertEqual(value["mcp"]["chrome_devtools_mcp"], "1.12.0")
            package = json.loads(package_path.read_text())
            package["dependencies"]["chrome-devtools-mcp"] = "^1.12.0"
            package_path.write_text(json.dumps(package))
            with self.assertRaisesRegex(ValueError, "exact npm version"):
                module.compose(root)


if __name__ == "__main__":
    unittest.main()
