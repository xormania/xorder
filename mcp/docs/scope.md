# Scope of xorder MCP

**Status:** development scope, 20 October 2026. Current maintainer direction
takes precedence over prior proposals and research recommendations.

## Purpose

Make xorder's resources and reusable knowledge useful to agents across local and
cloud work. Reduce repeated explanation and reinvention of established approaches,
including test kits, CI practices, and concepts such as CUE.

The service provides catalog navigation and context retrieval. Jev recommends
relevant packets. Native hooks and supported asynchronous delivery bring useful
guidance into the agent's work when optional discovery is insufficient.

## Capabilities in scope

| Capability | Intended result |
| --- | --- |
| Catalog navigation | Find and inspect resources/profiles using xorder's existing model and release evidence |
| Context packets | Retrieve summaries or sections of selected, versioned context with identity and provenance |
| Jev recommendations | Select useful material for a task, including several relevant packets, with honest fallback behavior |
| Diagnostics | Explain an observed condition and provide actionable guidance plus the relevant packet |
| Native harness integration | Observe supported events and deliver context at the useful point in the workflow |
| Asynchronous delivery | Deliver external findings to supported subscribed conversations, with an identified observer |
| Local operation | Install and launch an MCP through native harness configuration, initially stdio |
| Cloud operation | Serve remote Streamable HTTP and support actual hosted-session registration, authentication, updates, and lifecycle behavior |
| Deployment choices | Hosted HTTPS and supported private/local-server tunnel routes |
| Installation and maintenance | Repeatable setup, explicit versions, preservation of unrelated configuration, updates and recovery |

Local and cloud support are part of the goal from the start. A particular host's
missing interface must be identified and tested; it does not remove cloud from
scope. Support claims remain specific to the capabilities actually demonstrated
on the named product and version.

## Relationship to existing xorder

Use the accepted catalog and existing resolver. A packet uses the `context`
resource kind; profiles compose resources. Keep relevance, compatibility,
availability, selection, and delivery distinct.

MCP is an additional interface to xorder. Existing URL discovery and direct usage
remain useful. Reading a packet does not implicitly install configuration.
Existing pins, release records, and ownership semantics remain intact.

PoCs may use explicit experimental fixtures outside the published catalog.
Production context releases follow the existing resource publication path.

## Proof before expansion

The [session plans](plans/README.md) investigate the uncertain parts concurrently:
transport, native cloud diagnostics, Work retrieval, Work Events, Codex Cloud
registration, and Jev recommendation quality.

The first useful result is a small task where the agent receives relevant
guidance without being told to look for it, and the resulting work improves.
A registered server, a retrieved packet, or sixteen synthetic adapter checks
alone cannot establish that outcome.

Initial query tools and fixture diagnostics can be small. The larger tool set in
the [design reference](plans/design-reference.md), implementation language,
framework, and final packaging remain proposals. Later installation or other
write tools can be added explicitly when useful; starting with read-only
retrieval does not forbid them.

## Location and workflow

- Main MCP work: `mcp/`.
- Scope: `mcp/docs/scope.md`.
- Specific plans: `mcp/docs/plans/`.
- Every PoC: `mcp/poc/<poc>/`.
- Session work branches start from and integrate into `feat/xorder-mcp`.

Each experiment owns its code, fixtures, run instructions, and sanitized results.
Promote reusable code after its contract is demonstrated. Reuse existing xorder
runtime and resource machinery where it helps; a new universal policy platform
is not a prerequisite.

## Completion criteria

Cloud readiness requires actual-session registration and packet retrieval through
the intended deployment route, supported authentication, bounded failure behavior,
and demonstrated relevant lifecycle/update handling. Automatic guidance additionally
requires observed event delivery and useful resulting work.

Keep availability, delivery, useful application, and blocking separate. Blocking
belongs to a specific requested rule and a demonstrated native contract. Report
coverage gaps and negative findings promptly so the maintainer can choose what
to continue, change, or stop.
