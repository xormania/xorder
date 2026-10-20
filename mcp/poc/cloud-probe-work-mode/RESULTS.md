# Work Mode probe results — 2026-10-20

**Decision: blocked on native registration access.** The shared fixture passes
its local Python SDK checks in this session's command runtime. This outer
ChatGPT Work conversation exposes no operation to create a custom MCP plugin
or provision a tunnel, and no xorder tool was present in its callable tool
inventory. No native `xorder_probe_status` call or packet retrieval occurred.
This is a finding about the exposed session interface; Work's documented custom
MCP route remains available to investigate.

The smallest next step is a reachable endpoint or workspace-associated Secure
MCP Tunnel, followed by **Plugins → + → Add custom MCP server**, plugin
installation, and a new Work conversation using that plugin. The tested stdio
command is retained in [the evidence](evidence/tested-stdio-command.json).
Tunnel forwarding supports stdio, so changing the fixture into an OAuth or HTTP
deployment is not a prerequisite for that documented alternative. Account UI,
tunnel permissions, workspace associations, and availability were not inspected.

## Identity and execution boundary

| Item | Observed value |
| --- | --- |
| Product | ChatGPT Work Mode, identified by the provided product context |
| UI entry point | Existing outer Work conversation; initiating navigation path and build not inspected |
| Execution environment | Managed Linux/x86_64 command runtime through `functions.exec` / `exec_command` |
| Native caller under investigation | Outer hosted conversation |
| Caller for successful transport checks | Official MCP SDK test client launched through a shell tool |
| Inner harness | No Codex or Claude CLI executed; neither executable found |
| Source | `7cbf2ed56dc6381d431d8b428999d06e0ecef6ba`, clean before evidence/setup |
| Python / SDK | Python 3.12.14 / `mcp==2.3.0` |
| Image | Not built; no resulting image ID or digest |
| Packet | `context/poc-test-kit`, `0.0.0-poc.1` |
| Packet SHA-256 | `a7e9e45f5d0bd820eadf87b2ae62a66baf7ceb34ac09f740b92a4e11e88dc206` |

The handoff's fixture branch had been merged and deleted remotely. The
experiment branched from its integration commit on `feat/xorder-mcp` and did
not change shared fixture or catalog bytes. This is not a Codex Cloud product
probe merely because the assistant has a Codex identity or can run commands.

Server status reports its source label as `unrecorded` in these local runs.
The checkout commit above was measured separately; retained fixture file hashes
bind the exercised source bytes without claiming an image provenance label.

## Executed checks

| Check | Result and limit |
| --- | --- |
| Local install | Fresh venv; locked binary dependencies installed with hash verification |
| Focused fixture tests | 4 passed |
| stdio and loopback HTTP, automatic mode | Passed; protocol `2026-07-28` |
| stdio and loopback HTTP, legacy mode | Passed; protocol `2025-11-25` |
| Discovery and fresh status challenges | Passed in all four SDK runs; challenges and boot IDs retained |
| Full packet / section hash | Passed; exact source fixture identity matched |
| Invalid identities / argument bounds | Expected errors returned |
| Deliberate diagnostic and receipt retry | Passed in the programmed SDK client; not fresh-model behavior |
| Process lifetimes | Four distinct boot IDs and stable packet hash; no hosted reconnect test |
| Generic diagnostic command | JSON serialization passed; no native hook invocation or delivery |
| Marker create/read | Matching exact hash in two independent Python processes in this conversation |
| Setup egress | Repository fetch and pinned package installation succeeded; no general egress claim |
| Docker build / image verifier | Not executed; `docker version` could not start because the executable is absent |

Repository validation also passed: `python3 scripts/library.py check` and
`python3 -m unittest discover -s tests`. Exact exit codes and the unit-suite
output are retained in [repository-checks.json](evidence/repository-checks.json)
and its referenced logs. The attribution history audit passed before this
result commit.

The smoke client retrieves the packet before running its negative check and
uses a programmed receipt. Its trace does not demonstrate an agent discovering
the packet in response to a diagnostic. This setup conversation has also read
fixture source, so a fresh task is required for that behavior experiment.

## Native checks still unexecuted

- **Registration and native tool call:** no registration/tunnel provisioning
  operation exposed, no xorder native tools, and no supplied remote endpoint or
  tunnel. This does not establish whether the account has the necessary UI.
- **Native diagnostics:** no supported host event was registered or observed.
  Official documentation says plugin command hooks do not run in cloud
  orchestrated Work. Enterprise managed MCP hooks are a separate facility;
  account applicability was not investigated.
- **Authenticated remote connection:** no tunnel or authenticated remote plugin
  was created or called.
- **Fresh-session reuse:** not tested. The marker remains at the candidate
  scratch path recorded in [persistence.json](evidence/persistence.json). A
  future session must read it before setup can recreate state. The retained
  evidence copy is not proof of persistence. Configuration and native tool
  visibility also need independent checks in that session.

No hook delivery, installation persistence, automatic context delivery, or
cloud compatibility claim follows from the local transport checks.

## Evidence and continuation

- [Comparable result record](result.json)
- [Environment / Docker probe](evidence/environment.json)
- [Exposed registration-related tool inventory](evidence/outer-tool-inventory.json)
- [Automatic SDK results](evidence/sdk-auto.json) and [trace](evidence/sdk-auto.log)
- [Legacy SDK results](evidence/sdk-legacy.json) and [trace](evidence/sdk-legacy.log)
- [Install outcome](evidence/install.log) and [fixture tests](evidence/fixture-tests.log)
- [Manual diagnostic serialization](evidence/diagnostic-serialization.json)
- [Marker evidence](evidence/persistence.json)
- [Runnable next steps and read-before-setup command](README.md)

The supported platform paths and limits above were verified against the
[official Work MCP guide](https://learn.chatgpt.com/docs/extend/mcp),
[custom MCP connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt),
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
and [plugin hook scope](https://learn.chatgpt.com/docs/plugins) on 2026-10-20.
They are documented capabilities, distinct from this session's observations.
