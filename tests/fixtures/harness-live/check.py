"""Check installed harness capabilities offline, without credentials or model turns."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path('/consumer')
LOCK = json.loads(Path('/proof/consumer.json').read_text())
for name, expected in LOCK['files'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
assert os.environ['HOME'] == '/home/dev', 'Harness credentials must persist for root and non-root users'
assert not any((Path.home() / name).exists() for name in ('.codex/auth.json', '.claude/.credentials.json', '.grok/auth.json'))
sys.path.insert(0, str(ROOT / 'src'))
from xordination.adapters import doctor  # noqa: E402


def command(*argv):
    result = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=90)
    return result.stdout


before = json.loads(command('harnesses', 'status'))
# Repeated initialization on a disconnected network must reuse every installed selection.
command('harnesses', 'ensure')
after = json.loads(command('harnesses', 'status'))
assert before == after, 'Readiness must not change selected versions or installation receipts'
observations = {name: doctor(name) for name in ('codex', 'claude', 'grok')}
for name, value in observations.items():
    assert value['status'] == 'supported', (name, value)
    assert value['version'].get('returncode') == 0, (name, value['version'])
    assert value['live_round_trip'] == 'unverified', 'Offline readiness must not claim a live round trip'
result = command(sys.executable, str(ROOT / 'scripts/testing/live_tmux.py'), 'self-check')
tmux = json.loads(result)
assert tmux and all(value is True for value in tmux.values()), tmux
print(json.dumps({'schema_version': 1, 'consumer': LOCK, 'uid': os.getuid(),
                  'installed': after, 'harnesses': observations, 'tmux': tmux,
                  'network': 'none', 'authenticated': False, 'model_calls': 0}, indent=2, sort_keys=True))
