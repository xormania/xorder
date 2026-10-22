# Cloud capability probe report: Claude Code on the web

**Report time:** 2026-10-20 10:24 UTC
**Observations:** 2026-10-20 10:00–10:17 UTC
**Handoff:** `mcp/poc/cloud-capability-fixture/HANDOFF.md`, identical to the uploaded copy
**Fixture source:** `7cbf2ed` on `origin/feat/xorder-mcp`, clean tree when built and run
**Session branch:** `claude/new-session-iyf2qq`, reset to `7cbf2ed`. Nothing is committed or pushed yet.

## Decisive result

**This session did not register the fixture natively, so no native MCP call was
made.** The documented route for this surface is a committed project
`.mcp.json`, which a session loads when it starts. The agent's write of
`.mcp.json` and its hook edit to `.claude/settings.json` were both refused by the
auto-mode permission classifier as *Self-Modification*. A later commit and push
of the results was refused as *Instruction Poisoning*. No denial was worked
around.

Every MCP call recorded here was made by the fixture's SDK test client
(`smoke.py`), which this session started through its Bash tool. None was made
by the cloud conversation itself.

## 1. Surface and caller identity

| Item | Observed value | Source |
| --- | --- | --- |
| Product / UI entry point | Claude Code on the web (claude.ai/code); session origin `web_claude_ai` | `get_session` |
| Environment type | `environment_kind: anthropic_cloud`; `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`; `CLAUDE_CODE_ENTRYPOINT=remote` | `get_session`, process environment |
| Running harness | `/opt/claude-code/bin/claude`, version 2.1.304 (pid 88). The env var `CLAUDE_CODE_VERSION=2.1.42` does not match the running binary. | `/proc/88/exe`, `--version` |
| VM | Firecracker init, Ubuntu 24.04.5, x86_64, single root disk `/dev/vda` | `ps`, `mount`, `os-release` |
| Repositories | One (`xormania/xorder`) | `get_session` |
| Permission mode | auto | `get_session` |
| Host Python | 3.13.16 | `python3 --version` |

The configured git identity is `Claude <noreply@anthropic.com>`. AGENTS.md
disallows that identity, so any commit needs an explicit accountable author.

## 2. Branch state

`poc/mcp-cloud-capability-fixture`, named in the handoff, no longer exists on
origin. Its content was merged into `feat/xorder-mcp` as PR #80 (`7cbf2ed`). The
session branch was reset onto that commit.

## 3. Native fixture smoke test

| Check | Result |
| --- | --- |
| Hash-locked install (`mcp==2.3.0`, `--require-hashes --only-binary=:all:`) | Passed |
| Fixture unit tests | 4 passed |
| `smoke.py`, automatic negotiation | Passed; stdio and loopback HTTP negotiated `2026-07-28` |
| `smoke.py --protocol-mode legacy` | Passed; both negotiated `2025-11-25` |
| Discovery, fresh challenge, exact packet and section hashes, unknown identity, input bound, diagnostic error, receipt retry | Passed on all four client/transport combinations |
| Surface launcher `serve-native.sh` over SDK stdio | Passed. Reported `source_commit` `7cbf2ed…-dirty`, because this probe's own files were untracked. |

## 4. Docker image

| Step | Result |
| --- | --- |
| Container runtime | The Docker 29.9.1 client is installed but no daemon was running. `dockerd` was started manually and came up with overlayfs and cgroup v1. |
| Base pull | The pinned GHCR digest pulled through the session proxy. |
| Build with the README command exactly as written | **Failed.** `pip`: `CERTIFICATE_VERIFY_FAILED`, self-signed certificate in chain. The build container's HTTPS goes through TLS interception. |
| Build with `--secret id=xorder_ca,src=<session CA bundle>` | **Passed.** Image `sha256:51308f2c2c74cc41aab9cf264d6be743925d96727acea44fece0880a3e925944`, revision label `7cbf2ed`, local tag only. |
| `verify-image.sh` as committed | **Failed** at the published-port HTTP check (`httpx2.ReadError`). The offline in-container run and host stdio passed first, with UID 1000. |
| Failure cause | **Readiness race, reproduced.** Docker's published port accepts TCP before the server inside listens, so the verifier's socket-connect check passes too early. An immediate smoke run failed; the same run after the server was up passed. |
| Scratch verifier copy with an HTTP-response readiness check | **Passed** offline runtime, stdio, published HTTP port, UID 1000, and one marker shared by two containers. The fixture files were not modified. |

The scratch readiness probe sent `Host: 127.0.0.1` without a port. The server
rejected it with "Invalid Host header", but that response was enough to show it
was listening.

## 5. Native MCP registration

- **Documented route** (code.claude.com docs, read 2026-10-20):
  - A one-repository cloud session loads the repository's `.mcp.json` at start.
  - Cloud sessions load project-scoped servers without an approval prompt.
  - Servers added with `claude mcp add` at user or local scope do not reach cloud sessions.
  - A committed `enabledMcpjsonServers` is ignored in an untrusted folder.
- **This session** started with no `.mcp.json` and no user `mcpServers`.
- **Blocked:** the agent's write of `.mcp.json` was refused as Self-Modification.
- **Unresolved even with the file in place:** the docs do not describe loading a
  config change mid-session. A new session cloned from a branch containing the
  file is the testable path.

Prepared, uncommitted:

- `serve-native.sh`: a stdio launcher that creates the venv from the hash lock
  on first launch and records the source commit.
- `hook.py`: a command-hook adapter. It creates a fresh challenge per call,
  calls the fixture's `diagnostic --format claude-hook`, and logs without the
  event body. A manual run confirmed only the output format, not native execution.

## 6. Native diagnostic delivery

**Blocked.** The narrow `PostToolUse` and `PostToolUseFailure` hooks on
`mcp__xorder-cloud-probe__xorder_probe_check` could not be added to
`.claude/settings.json`; the classifier refused it as Self-Modification.
Behaviour was not evaluated. This session has read `packet.md` and `probe.py`,
so it is not a valid subject for that test anyway.

## 7. Persistence markers

No proposed persistent location is named in the handoff, plans or research
notes. Every candidate path sits on the same root disk and was created at
session start. This session chose three candidates:

| Location | Marker SHA-256 |
| --- | --- |
| `/root/.xorder-probe-state` | `e00629ecad2a6d0bfe1bf092e9af0aff446213f1e12821906bb53a95d0952b80` |
| `/home/user/xorder-probe-state` | `b1231ee2c28af7e06f63f39e12528e3dccc05481f11353f4c8e9f9f82999acd6` |
| `/mnt/user-data/working/xorder-probe-state` | `34c8866b89eaa6983baa5733a77787716b67652fdea6cdb4a26a1c3fea86c1f4` |

All three use challenge `reuse-b1b544f60d` and were created at 10:13:46 UTC.
No new session has read them. The docs say the environment cache keeps only what
the setup script writes. That predicts these session-written markers will be
absent in a new session, but it has not been observed.

## 8. Other permission denials

- Reading `/root/.claude/launcher-settings.json` was refused as Credential Exploration.
- Searching fetched documentation under `/root/.claude/projects/…` with shell `grep` was refused the same way. The dedicated Grep and Read tools worked on the same files.

## 9. Status summary

| Observation | Status |
| --- | --- |
| setup_install | passed (CA build secret required) |
| stdio_transport | passed (SDK client) |
| http_transport | partial (verifier race; passes with HTTP readiness) |
| outer_session_mcp_registration | blocked |
| native_diagnostic_delivery | blocked |
| diagnostic_retrieval_retry | partial (SDK client only) |
| process_restart | passed (distinct boot IDs, stable packet hash) |
| fresh_session_reuse | not_tested (markers created, unread) |
| host_egress | passed (targeted: PyPI, GHCR) |
| container_egress | partial (build only, via CA secret) |
| authenticated_remote_registration | not_tested |

Machine-readable record: [result.json](result.json). Traces: [results/](results/).

## Suggestions for future research

1. **Registration needs a human-authored config commit.** In auto mode,
   agent-written `.mcp.json` and hook settings are refused. Have a person
   commit both to a probe branch, then start a new session from that branch.
   The exact content is in [README.md](README.md). Record that new session's
   origin. A session started with `create_session` is not the same entry point
   as the web UI.
2. **Fix the image verifier's readiness check.** Wait for an HTTP response
   with a valid `Host` header including the port, or a successful MCP
   initialize. A TCP connect is not enough. Coordinate this with the fixture
   owner.
3. **Document the cloud build path.** In this environment the Docker daemon
   must be started, and the private-CA build secret is required. The README's
   plain build command fails here.
4. **Measure MCP startup time on a fresh clone.** The launcher installs the
   venv on first launch. Check whether that finishes inside the MCP startup
   timeout; the default was not found in the docs read. Compare with an
   environment setup script that prepares the venv before Claude Code starts,
   which is what plan 02 recommends.
5. **Find out which hook event an MCP tool error fires.** Configure both
   `PostToolUse` and `PostToolUseFailure` with per-call challenges, then compare
   the hook log and transcript hook events with the model's next response.
6. **Keep the behavioural subject clean.** `probe.py` hard-codes the receipt
   `packet-ack-v1`, so a session that reads the source learns the answer without
   retrieving the packet. Either test in sessions told not to read fixture
   sources, or take the receipt out of the server source in a new fixture revision.
7. **Test persistence against the documented route.** Read the three markers
   in a new session. Separately, write a marker from the environment setup
   script, which is the documented persistent path, and test resume after the VM
   is reclaimed.
8. **Test remote registration separately.** Registering a remote HTTP server
   through a claude.ai connector needs public HTTPS ingress, which this
   container does not provide. That route stays untested.
9. **Test container runtime egress.** The verifier runs with `--network none`.
   Container egress at runtime is untested beyond the build step.
