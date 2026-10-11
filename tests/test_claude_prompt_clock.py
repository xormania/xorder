import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/claude_prompt_clock.py"
spec = importlib.util.spec_from_file_location("claude_prompt_clock", SCRIPT)
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


class PromptClockTests(unittest.TestCase):
    def test_hook_observes_utc_without_echoing_prompt(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = subprocess.run(["python3", str(SCRIPT)], input='{"prompt":"private prompt sentinel"}',
                                capture_output=True, text=True, check=True)
        after = datetime.now(timezone.utc).replace(microsecond=0)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        observed = datetime.fromisoformat(output["additionalContext"].removeprefix("Current UTC time: ").replace("Z", "+00:00"))
        self.assertLessEqual(before, observed)
        self.assertLessEqual(observed, after)
        self.assertNotIn("private prompt sentinel", result.stdout + result.stderr)

    def test_installer_preserves_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="clock ' $ ") as temporary:
            project = Path(temporary)
            settings = project / ".claude/settings.local.json"
            settings.parent.mkdir()
            original = {"permissions": {"allow": ["Read"]}, "hooks": {
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo existing"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]}}
            settings.write_text(json.dumps(original))
            settings.chmod(0o640)
            self.assertEqual(clock.install(project)["status"], "installed")
            data = json.loads(settings.read_text())
            self.assertEqual(data["permissions"], original["permissions"])
            self.assertEqual(data["hooks"]["Stop"], original["hooks"]["Stop"])
            self.assertEqual(data["hooks"]["UserPromptSubmit"][0], original["hooks"]["UserPromptSubmit"][0])
            handler = data["hooks"]["UserPromptSubmit"][1]["hooks"][0]
            self.assertEqual(handler["command"], "python3")
            self.assertEqual(handler["args"], [str(SCRIPT)])
            self.assertEqual(settings.stat().st_mode & 0o777, 0o640)
            saved = settings.read_bytes()
            self.assertEqual(clock.install(project)["status"], "already-installed")
            self.assertEqual(settings.read_bytes(), saved)

    def test_invalid_existing_settings_are_never_overwritten(self):
        for contents in ('{broken', '[]', '{"hooks": []}', '{"hooks":{"UserPromptSubmit":[{"hooks":false}]}}'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as temporary:
                settings = Path(temporary) / ".claude/settings.local.json"
                settings.parent.mkdir()
                settings.write_text(contents)
                with self.assertRaises(ValueError):
                    clock.install(temporary)
                self.assertEqual(settings.read_text(), contents)

    def test_new_settings_file_is_private_and_hook_can_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = clock.install(temporary)
            settings = Path(result["settings"])
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            handler = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]
            completed = subprocess.run([handler["command"], *handler["args"]], check=True,
                                       capture_output=True, text=True)
            self.assertIn("Current UTC time: ", completed.stdout)
