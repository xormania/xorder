# Work Mode cloud probe

This experiment runs the shared cloud capability fixture from an actual outer
ChatGPT Work Mode conversation. See [RESULTS.md](RESULTS.md) and
[result.json](result.json) for the observed boundary. Shell-driven SDK checks
are identified separately from native conversation calls.

Source: `7cbf2ed56dc6381d431d8b428999d06e0ecef6ba` on `feat/xorder-mcp`.
The handoff's `poc/mcp-cloud-capability-fixture` branch no longer existed remotely;
the fixture had been merged as #80. The shared fixture bytes were not changed.

## Repeat the local checks

From the repository root, follow the shared
[native setup](../cloud-capability-fixture/README.md#install-and-run-without-docker).
Then run:

```sh
PROBE=mcp/poc/cloud-capability-fixture
OUT=mcp/poc/cloud-probe-work-mode/evidence
"$PROBE/.venv/bin/python" -m unittest discover -s "$PROBE" -p 'test_*.py' -v
"$PROBE/.venv/bin/python" "$PROBE/smoke.py" --output "$OUT/sdk-auto.json"
"$PROBE/.venv/bin/python" "$PROBE/smoke.py" --protocol-mode legacy --output "$OUT/sdk-legacy.json"
```

The smoke client starts and stops its own stdio and loopback HTTP processes.
It does not install a plugin or modify native harness settings. Repeating it
overwrites the chosen SDK evidence files; retain earlier observations separately
when comparing environments.

## Continue the native registration experiment

The tested absolute stdio command and arguments are retained in
[tested-stdio-command.json](evidence/tested-stdio-command.json). Paths refer to
this experiment's execution environment, not the maintainer's own computer.

Official Work documentation supports custom MCP plugins through either a
public HTTPS Streamable HTTP endpoint or Secure MCP Tunnel. No remote endpoint
or tunnel was created by this experiment. The local loopback endpoint used by
the smoke client is not an endpoint for ChatGPT's hosted caller.

For a private tunnel, provision or select a tunnel associated with the target
ChatGPT workspace and a runtime key with the documented tunnel permissions.
Run the supported `tunnel-client` on a host that can run the fixture's tested
stdio command. The tunnel documentation supports stdio directly; this route
does not require adding an HTTP listener to the fixture.

In ChatGPT **Plugins → + → Add custom MCP server**, choose **Tunnel** and the
matching tunnel, configure authentication as required, then create and install
the plugin. A public HTTPS endpoint is the documented alternative. These are
documented setup steps, not an observation that this account exposes the UI or
has the required permissions.

Start a new Work conversation with the resulting plugin selected. Ask it to
call `xorder_probe_status` with a fresh non-secret challenge, then retrieve
`context/poc-test-kit` version `0.0.0-poc.1`. Retain the actual native calls and
results, including the echoed challenge, boot ID, and packet hash.

For diagnostic recovery behavior, use a separate fresh conversation that has
not read the fixture's usage answer. Ask it to run `xorder_probe_check` and
handle the result. This setup conversation is contaminated by fixture source
inspection and cannot supply that behavior result.

## Read the persistence marker first in a new session

Before any setup, state creation, or copying files into the candidate path,
use the existing command if its environment is available:

```sh
/workspace/scratch/80fb065312eb/xorder-cloud-probe/mcp/poc/cloud-capability-fixture/.venv/bin/python \
  /workspace/scratch/80fb065312eb/xorder-cloud-probe/mcp/poc/cloud-capability-fixture/probe.py \
  state read --directory /workspace/scratch/80fb065312eb/cloud-probe-state \
  --challenge work-reuse-754c3f28462c4ebb8d1b8d756263767b
```

Expected marker file hash:
`sha256:6161f10edb7c33c52a900c1429fe53186be45fcdeb2e83cbdeab66712e4c076b`.
If the command environment is absent, record that fact before recreating setup.
If only Python setup is absent, a read-only byte hash of the original marker
file can still establish its presence; do not restore it from the evidence.
Recheck plugin configuration and native tool visibility independently. Identify
whether this is a resumed conversation, a genuinely new conversation sharing
execution state, or a new environment. Scratch durability is not guaranteed.

The marker directory is intentionally retained for this future check. Remove
only that owned directory after the persistence experiment has concluded.

## References checked 2026-10-20

- [Work MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
- [Custom MCP connection and new-conversation flow](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Secure MCP Tunnel and stdio support](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Plugin hooks and cloud Work scope](https://learn.chatgpt.com/docs/plugins)
