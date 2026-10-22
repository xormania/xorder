#!/usr/bin/env bash
# Native stdio launcher registered by the repository's .mcp.json for this cloud surface.
# stdout belongs to MCP; installation output goes to stderr.
set -euo pipefail
fixture=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../cloud-capability-fixture" && pwd)
venv="$fixture/.venv"
# A fresh clone has no venv; a SessionStart hook is not assumed to finish before MCP discovery.
if ! "$venv/bin/python" -c 'import mcp' 2>/dev/null; then
  python3 -m venv "$venv" >&2
  "$venv/bin/python" -m pip install -q --require-hashes --only-binary=:all: \
    -r "$fixture/requirements.lock" >&2
fi
source_commit=$(git -C "$fixture" rev-parse HEAD 2>/dev/null || echo unrecorded)
if [ -n "$(git -C "$fixture" status --porcelain 2>/dev/null)" ]; then source_commit="$source_commit-dirty"; fi
export XORDER_PROBE_SOURCE="$source_commit"
exec "$venv/bin/python" "$fixture/probe.py" serve
