# xorder MCP cloud readiness

**Direction:** cloud readiness is part of the MCP development scope.

**Status:** requirements and research findings; live xorder cloud acceptance is
pending. Updated 20 October 2026.

This note incorporates the maintainer-supplied
`xorder-cloud-context-research-report-2026-10-20.md`. That report completed
documentation/source research and isolated adapter probes. The platform claims
below are documented routes reported by that research, not installations
performed by this branch.

## Required delivery paths

| Path | Role | Acceptance |
| --- | --- | --- |
| Local stdio | Native harness launches the server | Real client retrieves a marked, exact packet |
| Remote Streamable HTTP | Hosted or private/tunneled service | Actual cloud conversation registers tools and retrieves the same packet |
| Native diagnostic adapter | Observe relevant operations and insert essential guidance | Real callback, model-visible result, and useful resulting work |
| Asynchronous event delivery | External producer reports findings to a subscribed conversation | Correlated event, receipt, useful response, and tested lifecycle |

The core catalog, packet, resolution, and recommendation operations should be
shared. Native diagnostics and asynchronous events complement retrieval.
Each host exposes its own combination of these paths.

Cloud readiness includes configurable endpoints and storage, supported
authentication, bounded requests, secret separation, restart behavior, explicit
loaded versions, and installation/update instructions. Private packet access
must follow the authenticated caller. Server logs and output must not expose
credentials.

## Research findings to carry into implementation

| Target | Reported documentation finding | Next proof |
| --- | --- | --- |
| Claude cloud, one repository | Project MCP and repository hooks have a route to the actual harness | First hosted event-to-context experiment |
| Claude cloud, multiple repositories | Repository settings/hook behavior differs | Independent configuration and delivery probe |
| Personal ChatGPT Work | Remote MCP plugins support retrieval; public HTTPS or a supported private tunnel can provide reachability | New conversation retrieves a uniquely marked packet |
| Work MCP Events | Asynchronous delivery to a subscribed conversation is documented | Identify the producer and demonstrate one subscription |
| Current reusable Codex Cloud | Runtime preparation is documented; the controlling outer-session MCP configuration remains unresolved | Prove actual tool registration, then investigate callbacks |
| Native harness on an owned host | Host configuration provides a controlled deployment route | Reuse an accepted xorder runtime and test the exact native binary |

Useful official references from the report:
[Claude environments][claude-env], [Claude MCP][claude-mcp],
[Claude hooks][claude-hooks], [Work plugins][work-plugins],
[Work MCP Events][work-events], [Secure MCP Tunnel][tunnel],
[Codex environments][codex-env], and [configuration reference][codex-config].

Do not infer support in one product from a successful call in another. A CLI
installed inside a remote workspace is not necessarily the surrounding session's
harness. A private service reachable from the workspace may still be unreachable
from the hosted plugin caller.

## Native diagnostics

Provide the useful explanation inline, with the packet identity and a retrieval
route for more detail. Avoid turning every tool event into a remote Jev request.
Use a verified local subset or cache for known triggers; preserve Jev's broader
recommendation role.

The report distinguishes advisory delivery from prevention: context returned by
a pre-tool hook can reach the model on its next request, after the operation.
Measure that timing. Blocking requires a supported native decision contract and
a rule the maintainer wants enforced.

The isolated adapter probes reported sixteen expected outcomes, including two
expected limitations:

- Shell-text inspection missed a Python file write embedded in a command.
  Add a bounded check of relevant modified/untracked files after a supported
  operation; distinguish pre-existing workspace changes.
- Repeated events repeated the diagnostic. Use rule, content, packet, and
  session/context state for duplicate handling, permitting useful re-delivery
  after meaningful changes or compaction.

These were synthetic adapter observations, not native cloud model runs.
Rewrite inherited project-specific authority wording when extracting a rule.

## Asynchronous delivery

An event requires an observer. Candidate producers include a native hook,
instrumented test command, CI, or an explicit workspace observer. Record which
work each producer sees. CI cannot establish coverage of uncommitted edits.

Use exact packet references and identify the finding, producer, affected work,
source revision, and event ID. The installed subscription supplies the response
workflow. Check duplicate/late delivery, callback authentication, expiry and
cancellation, and continuity after producer restart. Persist subscription state
where the chosen protocol requires it.

A delivery acknowledgement is not proof that the model received useful context
or completed corrective work. Keep each observation separate.

## First acceptance experiment

Use the [parallel PoC plans](../plans/README.md) and their separate [experiment directories](../../poc/README.md).
Establish a local control and a Claude single-repository hosted run, with the same
small packet and consumer convention. Work retrieval and a Work event probe can
then use that core. The Codex Cloud registration investigation remains a named
task rather than a general cloud blocker.

Record:

1. Exact product, launch mode, native version, source revision, and configuration owner.
2. Server startup and actual-session tool registration.
3. Retrieval of the selected packet identity.
4. Native event input, diagnostic output, and model-delivery evidence.
5. Resulting work from a fresh task that did not name or pre-load the packet.
6. A quiet clean control and a supported shell-edit case.
7. Resume/compaction, fresh-session, restart, and update behavior relevant to the target.
8. Measured latency/context volume and known coverage gaps.

Document unsupported paths precisely. A target can establish useful retrieval
while its automatic feedback path remains under investigation. Claim cloud
readiness only for the actual capabilities demonstrated on the named target.

[claude-env]: https://code.claude.com/docs/en/cloud-environments
[claude-mcp]: https://code.claude.com/docs/en/mcp
[claude-hooks]: https://code.claude.com/docs/en/hooks
[work-plugins]: https://developers.openai.com/plugins/quickstart
[work-events]: https://developers.openai.com/plugins/build/mcp-events
[tunnel]: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
[codex-env]: https://learn.chatgpt.com/docs/environments/cloud-environments
[codex-config]: https://learn.chatgpt.com/docs/config-file/config-reference
