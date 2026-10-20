"""Exercise initialization and invocation without installing vendor tools."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HarnessSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.jsonl"
        manager = self.bin / "harnesses"
        manager.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                           'with open(os.environ["CALLS"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
        manager.chmod(0o755)
        self.env = {**os.environ, "HOME": "/root", "HARNESS_ROOT": str(self.root / "installs"),
                    "PATH": str(self.bin) + os.pathsep + os.environ["PATH"], "CALLS": str(self.calls)}
        self.env.pop("HARNESS_AUTO_INSTALL", None)
        self.env.pop("HARNESS_NAMES", None)

    def invoke(self, *command, **environment):
        return subprocess.run(["bash", str(ROOT / "images/harness-live/session.sh"), *command],
                              env={**self.env, **environment}, capture_output=True, text=True)

    def records(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_startup_initializes_then_preserves_private_home_and_disables_updaters(self):
        result = self.invoke("python3", "-c", 'import json,os; print(json.dumps(dict(os.environ)))')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [["ensure", "codex", "claude", "grok"]])
        env = json.loads(result.stdout)
        self.assertEqual(env["HOME"], "/home/dev")
        self.assertEqual(env["DISABLE_AUTOUPDATER"], "1")
        self.assertEqual(env["DISABLE_UPDATES"], "1")
        self.assertEqual(env["GROK_DISABLE_AUTOUPDATER"], "1")
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(self.root / "installs/bin"))

    def test_management_and_explicit_offline_workloads_do_not_initialize(self):
        result = self.invoke("harnesses", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [["status"]])
        result = self.invoke("true", HARNESS_AUTO_INSTALL="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [["status"]])

    def test_selection_is_an_argument_array_and_invalid_startup_mode_fails(self):
        result = self.invoke("true", HARNESS_NAMES="codex grok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [["ensure", "codex", "grok"]])
        result = self.invoke("true", HARNESS_AUTO_INSTALL="sometimes")
        self.assertEqual(result.returncode, 64)
        self.assertIn("0 or 1", result.stderr)


class ImageInvocationTests(unittest.TestCase):
    def test_interactive_is_opt_in_and_command_arguments_remain_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            command = folder / "docker"
            command.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            command.chmod(0o755)
            env = {**os.environ, "PATH": str(folder) + os.pathsep + os.environ["PATH"],
                   "WORKSPACE": str(folder), "PUID": "0", "PGID": "0"}
            env.pop("CA_CERTIFICATE", None)
            for flags in ([], ["--interactive"]):
                result = subprocess.run(["bash", str(ROOT / "scripts/run-image.sh"), *flags,
                                         "example:image", "bash", "-c", "printf 'argument with spaces'"],
                                        env=env, capture_output=True, text=True, check=True)
                arguments = json.loads(result.stdout)
                self.assertEqual("-it" in arguments, bool(flags))
                self.assertEqual(arguments[-4:], ["example:image", "bash", "-c", "printf 'argument with spaces'"])
                self.assertIn("HARNESS_AUTO_INSTALL", arguments)


if __name__ == "__main__":
    unittest.main()
