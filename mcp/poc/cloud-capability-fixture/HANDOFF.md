# Handoff: remaining OpenAI cloud probes

Run this assignment in each OpenAI cloud entry point the maintainer is testing.
Claude's investigation is already handled, per the maintainer. Your task is to
establish how **this actual OpenAI session** can use xorder MCP and reuse its
setup. Perform the smallest real experiment that answers that question.

## Start from the merged fixture

- Repository: <https://github.com/xormania/xorder>.
- Base branch: **`feat/xorder-mcp`**. PR #80 was merged there as
  `7cbf2ed56dc6381d431d8b428999d06e0ecef6ba`; fetch the current branch.
- Fixture: **`mcp/poc/cloud-capability-fixture/`**.
- Read root and `mcp/AGENTS.md`, this directory's [README](README.md), and
  [RESULTS](RESULTS.md). The former `poc/mcp-cloud-capability-fixture` branch
  is no longer the starting point. Do not assume the fixture is on `master`.

Use the existing fixture. It already passes real SDK tests for stdio and HTTP
with current and legacy negotiation. The original session could not build its
image because Docker was unavailable; that is an observation about that session,
not a restriction on yours. Do not replace the server to get started.

The wider goal is rapid access to engineering resources and context packets.
Jev is an intended component; this assignment tests cloud integration, not
whether Jev or local MCP is worth using. Earlier plans are background; follow
the current OpenAI assignment here.

## 1. Identify the surface and its registration interface

Record the product name, UI entry point, environment/task type, exposed tools,
and observable runtime versions. Distinguish the outer conversation from an
SDK client or a separately launched CLI. A model name or installed `codex`
executable does not identify the surrounding product.

Use these working labels only when they match the observed surface:

| Surface | First question | Result directory |
| --- | --- | --- |
| `openai-work` | How does this conversation connect/install a custom MCP plugin? | `mcp/poc/cloud-probe-openai-work/` |
| `openai-codex-cloud` | Which configuration is consumed by the hosted task's actual harness? | `mcp/poc/cloud-probe-openai-codex-cloud/` |

If the UI uses another name or a legacy environment, record it explicitly and
adapt the directory label. Two entry points might share infrastructure; establish
that from evidence rather than assuming two different systems.

For **ChatGPT/Work**, investigate the supported personal plugin connection flow
first. The official [quickstart][plugins] connects an MCP server, installs the
resulting plugin, and tests it in a new Work chat. Determine whether this account
exposes that flow. Use an accessible HTTPS endpoint or the documented
[Secure MCP Tunnel][tunnel] route when available. Check the actual caller's
reachability and who must keep the server/tunnel running.

For **Codex Cloud**, locate the controlling environment/harness configuration
before editing files. The current [environment guide][environment] distinguishes
dependency installation and service startup. Those do not, by themselves,
establish outer-session MCP registration. The [MCP configuration guide][mcp]
documents remote-executor stdio as one lead; test it only where you can identify
the configuration consumer. A workspace `config.toml` or successful inner
`codex mcp` command needs separate evidence that the outer session uses it.

These official pages were checked on 2026-10-20. Verify their applicability to
your account and exact surface; documentation is a lead, not observed support.

## 2. Prove a native call with the existing fixture

Run the README's native installation and smoke check if your runtime needs
preparation. If an image is useful and Docker works, build it and run
`verify-image.sh`, retaining the image ID. Docker availability is a separate
finding; image preparation should not delay testing a usable native route.

Register the fixture through the supported interface you identified. Then have
the **actual outer session**:

1. Discover `xorder_probe_status` and call it with a fresh, non-secret challenge.
2. Retain the native call/result, echoed challenge, server `boot_id`, and packet
   digest. Record which configuration or plugin registration made it available.
3. Call `xorder_context_get` for `context/poc-test-kit`, version `0.0.0-poc.1`,
   and retain its content and digest.

An HTTP response, SDK smoke result, or inner CLI tool call is useful transport
evidence. Label its caller accurately; it does not establish outer registration.
If a new chat/task is required, complete the available setup and give the
maintainer the exact next-session prompt and settings to test.

If an account/UI action blocks progress, finish all available preparation and
report the concrete command or endpoint, settings, and remaining action. If the
endpoint is not deployed or reachable, say so; a hypothetical URL is not ready.
Record missing access, a rejected route, and an unknown interface distinctly.
Continue independent checks while the blocked native test remains pending.

## 3. Test feedback separately from retrieval

First exercise the fixture's deliberate tool failure and recovery. In a fresh
behavioral session, ask the agent to run `xorder_probe_check` and handle its
result, without supplying the packet's receipt. Retain the sequence from error
feedback to packet retrieval to retry. This proves a tool-result recovery path.

Then investigate automatic context delivery available on this OpenAI surface:
startup instructions/skills, native diagnostic callbacks, or subscribed events.
Identify the actual producer, trigger and delivery route before implementing an
adapter. The fixture's generic `diagnostic` command supplies a marked payload;
its `claude-hook` mode is a Claude adapter, not an OpenAI hook interface.

Consult current surface-specific support and account controls. Keep startup
context, per-tool feedback, and asynchronous events as separate results. Do not
infer that executing a diagnostic command delivered anything to the model.
If a supported event route exists, demonstrate it; otherwise report the exact
missing interface and the useful routes you did establish.

## 4. Establish what can be reused

Use `state create` at an explicitly chosen candidate persistent location and
retain its marker/hash externally. In a new task/session, use `state read`
**before** setup can recreate or copy the marker. Also check MCP registration,
tool visibility and whether the server must be restarted.

Distinguish a resumed conversation, a new conversation/task in the same saved
environment, and a newly created environment. Record which installation files,
configuration and services survive each transition. If this session cannot
launch the next one, leave exact continuation steps and mark that test pending.

The practical answer should tell the maintainer where to configure xorder once,
what must run each time, and how to start another session with it available.

## Return evidence and a decision

Create a separate work branch from current `feat/xorder-mcp`; preserve existing
work. Own only your surface's result directory. Copy
[result-template.json](result-template.json) there, add `RESULTS.md` and exact
setup/retest/cleanup steps, and retain sanitized native evidence. Include the
source commit, fixture hashes, caller, configuration source and observed errors.

Aim for a first decisive result within 30–60 minutes: a native call, a tested
failed configuration, or a precise owner/access action. Report it before growing
the experiment. Keep unexecuted checks `not_tested`; retain negative evidence.

Finish with:

- **Working route:** exact setup and native evidence, if established.
- **Reuse:** what survives, what restarts, and what remains to test.
- **Blocker:** exact missing interface/access/action, if any.
- **Decision:** continue, change approach, blocked on access, or route failed.

Open your PR against `feat/xorder-mcp`; the maintainer handles merging. Leave
accepted catalog availability unchanged. Coordinate fixture fixes separately
and preserve packet identity when comparing results across sessions.

[plugins]: https://developers.openai.com/plugins/quickstart
[tunnel]: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
[environment]: https://learn.chatgpt.com/docs/environments/cloud-environments
[mcp]: https://learn.chatgpt.com/docs/extend/mcp?surface=cli
