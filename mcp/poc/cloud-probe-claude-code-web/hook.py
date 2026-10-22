#!/usr/bin/env python3
"""Native Claude command-hook adapter: fresh per-call challenge and a bounded execution log.

The challenge exists only in this process, the log, and the hook output, so a later
model response that repeats it is evidence of delivery. Event bodies are not logged.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
PROBE = ROOT.parent / "cloud-capability-fixture" / "probe.py"
LOG = ROOT.parents[2] / "out" / "cloud-probe-claude-code-web" / "hook-log.jsonl"

raw = sys.stdin.read(65537)
try:
    event = json.loads(raw)
except ValueError:
    event = {}
challenge = "hook-" + uuid.uuid4().hex[:12]
result = subprocess.run([sys.executable, str(PROBE), "diagnostic", "--format", "claude-hook",
                         "--challenge", challenge], input=raw, capture_output=True, text=True)
entry = {"observed_at": datetime.now(timezone.utc).isoformat(),
         "hook_event_name": event.get("hook_event_name"), "tool_name": event.get("tool_name"),
         "session_id": event.get("session_id"), "challenge": challenge,
         "exit_code": result.returncode,
         "stdout_sha256": "sha256:" + hashlib.sha256(result.stdout.encode()).hexdigest()}
LOG.parent.mkdir(parents=True, exist_ok=True)
with LOG.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(entry, sort_keys=True) + "\n")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
