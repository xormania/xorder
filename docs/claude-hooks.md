# Automatic UTC context for Claude Code

The optional clock hook reads the host clock before each submitted prompt and
adds `Current UTC time: 2026-10-11T02:13:58Z` as context. It requires Python 3,
uses no network, and neither reads nor stores the prompt supplied on stdin.
An MCP clock tool requires an agent to call it; this hook runs automatically.

Install it explicitly for a project:

```sh
python3 /path/to/xorder/scripts/claude_prompt_clock.py install --project /path/to/project
```

This appends one `UserPromptSubmit` command hook to
`.claude/settings.local.json`. Existing settings and other hooks are preserved;
repeating the command does not append duplicates. Invalid existing JSON or hook
structure is reported before any write. A new settings file is private (`0600`);
existing permissions are retained. No consumer repository is modified merely by
using an xorder image or starting a stack.

The installer uses Claude Code's documented exec form:

```json
{
  "type": "command",
  "command": "python3",
  "args": ["/path/to/xorder/scripts/claude_prompt_clock.py"],
  "timeout": 5
}
```

Keep that xorder checkout and Python 3 accessible to the Claude Code session.
Install again if the checkout moves, removing the old hook entry. Project-local
settings must be present inside a cloud session; machine-level settings do not
automatically carry into it. Use `/hooks` to inspect the active hook. For delivery
verification, start Claude Code with `--debug-file /tmp/claude-clock-debug.log`;
the timestamp is context for Claude and does not require a visible transcript
entry. To remove the hook, delete its one handler or group from local settings.

The output is successful hook JSON with
`hookSpecificOutput.hookEventName = UserPromptSubmit` and
`hookSpecificOutput.additionalContext` containing an ISO 8601 UTC timestamp.
It does not block a prompt, change its text, or change the session title. The
timestamp describes the hook's invocation, so a later update needs another clock
observation after a long-running task.

Protocol reference: [Claude Code hooks](https://code.claude.com/docs/en/hooks),
especially UserPromptSubmit, hook locations, and command exec form.
