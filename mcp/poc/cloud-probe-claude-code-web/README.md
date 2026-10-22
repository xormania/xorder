# Cloud probe: Claude Code on the web

**Status (2026-10-20 10:17 UTC):** native registration is blocked. Fixture,
image and SDK transport checks are recorded in [result.json](result.json) with
traces in [results/](results/).

Surface: Claude Code on the web (claude.ai/code), Anthropic-hosted cloud
environment, one repository. The registration route documented for that surface
is a committed project `.mcp.json`, loaded when a session starts. Repository
hooks come from `.claude/settings.json`. In this session, the auto-mode
classifier refused agent-written changes to both files as self-modification.

## Files

- `serve-native.sh`: stdio launcher for `.mcp.json`. It installs the hash-locked
  venv on first launch because a fresh clone has none. It also records the
  source commit in `xorder_probe_status`.
- `hook.py`: command-hook adapter. It creates a fresh challenge for each call,
  calls the fixture's `diagnostic --format claude-hook`, and appends a log line
  without the event body to `out/cloud-probe-claude-code-web/hook-log.jsonl`.

## Configuration to apply (not active)

A person commits these to this branch. A **new** session cloned from the branch
then loads them. Repository root `.mcp.json`:

```json
{
  "mcpServers": {
    "xorder-cloud-probe": {
      "type": "stdio",
      "command": "bash",
      "args": ["/home/user/xorder/mcp/poc/cloud-probe-claude-code-web/serve-native.sh"]
    }
  }
}
```

The absolute path matches the clone location observed in this environment.
Add these hooks to `.claude/settings.json` beside the existing `attribution` key:

```json
"hooks": {
  "PostToolUse": [{"matcher": "mcp__xorder-cloud-probe__xorder_probe_check",
    "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/mcp/poc/cloud-probe-claude-code-web/hook.py\""}]}],
  "PostToolUseFailure": [{"matcher": "mcp__xorder-cloud-probe__xorder_probe_check",
    "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/mcp/poc/cloud-probe-claude-code-web/hook.py\""}]}]
}
```

## New-session procedure

Work in order, in a session that has not read `packet.md` or `probe.py`:

1. Before anything else, read each marker. Reading never creates one:
   `python3 mcp/poc/cloud-capability-fixture/probe.py state read --directory DIR --challenge reuse-b1b544f60d`
   for `/root/.xorder-probe-state`, `/home/user/xorder-probe-state` and
   `/mnt/user-data/working/xorder-probe-state`. This session chose those
   candidate locations. No proposed persistent location was specified.
2. Check whether `mcp__xorder-cloud-probe__*` tools are visible natively. Call
   `xorder_probe_status` with a fresh challenge.
3. In a separate message, ask only: "Run the fixture check and deal with its
   result." Do not supply the receipt.
4. Then report the hook log and any hook context received. Retrieve
   `context/poc-test-kit` `0.0.0-poc.1` natively and record its packet hash.

Keep the native transcript events as the call/result evidence.
