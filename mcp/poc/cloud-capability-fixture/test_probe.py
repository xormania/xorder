"""Guard the fixture's meaningful negative cases; transport checks live in smoke.py."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import probe


class FixtureTests(unittest.TestCase):
    def test_packet_tampering_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_bytes((probe.ROOT / "manifest.json").read_bytes())
            (root / "packet.md").write_bytes((probe.ROOT / "packet.md").read_bytes() + b"modified")
            with patch.object(probe, "ROOT", root), self.assertRaisesRegex(ValueError, "integrity"):
                probe.packet()

    def test_hook_uses_native_event_and_does_not_copy_private_input(self):
        result = probe.hook("test-challenge", json.dumps({"hook_event_name": "PostToolUse", "tool_input": "private"}))
        body = result["hookSpecificOutput"]
        self.assertEqual("PostToolUse", body["hookEventName"])
        self.assertIn("test-challenge", body["additionalContext"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("permissionDecision", body)

    def test_unsupported_hook_is_rejected(self):
        for raw in ('{"hook_event_name":"Stop"}', '[]', 'not JSON'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                probe.hook("test-challenge", raw)

    def test_marker_read_does_not_recreate_missing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                probe.state("read", root, "fresh-session")
            created = probe.state("create", root, "fresh-session")
            self.assertEqual(created, probe.state("read", root, "fresh-session"))
            with self.assertRaises(FileExistsError):
                probe.state("create", root, "fresh-session")
            with self.assertRaises(ValueError):
                probe.state("read", root, "../outside")


if __name__ == "__main__":
    unittest.main()
