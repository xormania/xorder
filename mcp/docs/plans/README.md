# Parallel PoC session plans

**Goal:** learn quickly whether xorder MCP can deliver useful context in the
intended local and cloud sessions. These are work assignments for Sol sessions,
not claims that any PoC has run.

Read [scope](../scope.md). All sessions can start immediately. Each owns one
directory and one branch; none must wait for a complete production server.

## Assign sessions

| Session | Plan | Owns | Branch | First decisive result |
| --- | --- | --- | --- | --- |
| A | [Core and transports](01-core-and-transports.md) | `mcp/poc/core-transports/` | `poc/mcp-core-transports` | A real MCP client gets the same exact packet through stdio and HTTP |
| B | [Claude cloud diagnostics](02-claude-cloud-diagnostics.md) | `mcp/poc/claude-cloud-diagnostics/` | `poc/mcp-claude-cloud` | A native hosted callback delivers useful guidance on an unprompted task |
| C | [Work retrieval](03-work-retrieval.md) | `mcp/poc/work-retrieval/` | `poc/mcp-work-retrieval` | A new Work conversation retrieves the unique packet through an installed plugin |
| D | [Work Events](04-work-events.md) | `mcp/poc/work-events/` | `poc/mcp-work-events` | A real subscription delivers one external finding to the intended conversation |
| E | [Codex Cloud registration](05-codex-cloud-registration.md) | `mcp/poc/codex-cloud-registration/` | `poc/mcp-codex-cloud` | The actual hosted session exposes the fixture MCP, or a precise missing interface is established |
| F | [Jev relevance](06-jev-relevance.md) | `mcp/poc/jev-relevance/` | `poc/mcp-jev-relevance` | A measured recommendation result improves on a simple metadata baseline |

With fewer slots, start B and E first to expose delivery/registration failures,
A alongside them, then C/D and F as capacity permits. This is prioritization,
not a dependency that prevents the other sessions from starting.

## Shared starting contract

Use a small SDK-based fixture server or a direct diagnostic fixture as needed.
A session can create a disposable stub inside its own directory to prove a host
interface before A is available. Mark the stub explicitly and replace/retest
against A's server after integration; do not grow six production servers.

For first cross-session interoperability, use:

- Packet ID: `context/poc-test-kit`.
- Version: `0.0.0-poc.1`; explicitly experimental, not a catalog release.
- Marker: `xorder-poc-context-v1`.
- Named sections: `overview` and `usage`.
- Exact content digest computed from the actual UTF-8 payload bytes.
- Retrieval operation: `xorder_context_get`; typed inputs include packet ID,
  version, and optional section, with returned identity/content/source.
- Selection operation where needed: `xorder_catalog_search`, returning metadata
  rather than every packet body.

A owns the concrete shared fixture and initial typed schemas in its PoC directory.
Other sessions preserve their own fixture hashes until they adopt A's exact
bytes. Matching names or markers do not prove matching content.

Report SDK/protocol/client versions. Use a maintained SDK and verify its current
API before implementation; do not invent MCP wire methods from these application
contracts. Provider/harness setup instructions in research are leads to verify
for the actual session, not guarantees.

## First checkpoint and decision

Aim for the first observed result within **30–60 minutes of implementation**.
This is a suggested checkpoint, not an estimate or a cap on an authorized task.

At that checkpoint report one of:

- **Continue:** the uncertain capability works; identify the next smallest check.
- **Change approach:** the attempted route failed, but a specific supported
  alternative is available to test.
- **Blocked on access:** name the account action, credential, endpoint, or target
  session needed, and retain the runnable probe.
- **Route failed:** retain the evidence and exact product/version boundary.
  Do not generalize one failed route into impossibility of the whole goal.

Do not substitute more documentation or a simulated inner harness for the
missing real-session result. First prove the disputed interface, then spend time
on packaging, abstractions, broad compatibility, and optimization.

## Session workflow and deliverables

1. Branch from the current `feat/xorder-mcp`; use a separate checkout/worktree.
2. Read the assigned plan and root repository guidance.
3. Implement within the assigned PoC directory.
4. Run the first decisive experiment before broadening the implementation.
5. Add exact setup/run/cleanup commands and `RESULTS.md` in that directory.
6. Open a PR targeting `feat/xorder-mcp`. Do not merge another session's work.

A result records the question, versions, source/packet identities, actual caller,
observed inputs/outputs, outcome, coverage, and next decision. Sanitize credentials
and unrelated private content. Separate direct traces, indirect evidence, and
simulation. Negative results and runnable blocked probes are useful deliverables.

Follow the repository's required checks and add focused checks for changed
behavior. Report environmental limits honestly. Do not trigger broad image
rebuilds merely because a PoC exists.

## Integration

A supplies the shared transport/fixture baseline. B–E rerun their successful
host path against it; F integrates recommendations only after its evaluation
shows value. Transport parity and target lifecycle checks then support a
cloud-ready implementation.

Keep the first integration decision small: which routes are working, which are
blocked, whether guidance helps, and which component is worth promoting.
The maintainer decides continuation and merging. The earlier
[design reference](design-reference.md) supplies ideas, not an obligation to
build every proposed feature before this decision.
