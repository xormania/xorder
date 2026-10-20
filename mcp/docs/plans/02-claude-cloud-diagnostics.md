# Session B: Claude cloud diagnostic delivery

**Work branch:** `poc/mcp-claude-cloud`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/claude-cloud-diagnostics/`.

**First target:** an actual Claude cloud session with one repository.

## Question and first result

Does a native hosted callback deliver guidance that changes useful work when the
task never asks the agent to find a packet? This is the primary test of whether
context delivery solves the repeated-explanation problem.

Start with one small task/control pair. Do not wait for A's full server: a cached
packet and native command adapter can test automatic delivery independently.

## Prerequisites to establish immediately

Identify the exact cloud product/launch mode and who controls its repository
settings. Verify current [environment][env], [MCP][mcp], and [hook][hooks]
documentation. A CLI launched inside another vendor's workspace is an owned-host
control, not this hosted target.

If the session cannot access the target product, produce the runnable fixture
and exact configuration/handoff needed, and report the missing access early.
Do not substitute synthetic callbacks for a native result.

## Work

1. Use one small existing test-kit convention as the consumer fixture. Keep its
   real import/helper behavior and a clean control; avoid implementing a broad kit.
2. Include a small versioned packet with the shared marker and useful guidance.
   Make it explicit that the fixture is experimental.
3. Prepare the runtime and MCP executable before harness launch. Use stable
   paths and explicit arguments. A SessionStart hook must not be assumed to
   complete installation before MCP discovery.
4. Register a command hook on the relevant supported event. Return the essential
   explanation inline with identity and retrieval information.
5. In a connectivity session, verify explicit packet retrieval using A's server
   or a clearly labeled temporary SDK stub.
6. In a fresh behavioral session, assign a realistic test-writing task without
   mentioning the packet. Retain callback input/output, model-delivery evidence,
   and the resulting test.
7. Compare a fresh run without the adapter using the same task/instructions.
   Include a clean case that should produce no diagnostic.
8. After the first useful result, cover a shell write, repeated events, and a
   supported resume/compaction or fresh-task transition.

## Known implementation gaps

The earlier isolated adapter probes found a missed Python file write embedded in
shell input and repeated diagnostics across identical events. Supplement command
inspection with bounded relevant-file checks, accounting for pre-existing dirty
files. Suppress duplicates using meaningful content/session state.

Use current practical diagnostic wording. Do not import legacy authority claims
or a project-specific kit path as a universal convention.

## Acceptance and early decision

A successful case identifies the native callback, shows useful guidance reaching
the model, and shows the appropriate resulting behavior. Packet reads alone do
not pass. Advisory timing is recorded separately from action blocking.

If delivery works but behavior does not improve, repeat with one clearer,
shorter diagnostic before expanding the machinery. If it still fails, report
the observed limitation and examples promptly. A small paired comparison is
directional evidence, not a statistical effectiveness claim.

Deliver runnable instructions, fixtures, sanitized traces, and `RESULTS.md`.
Open a PR to `feat/xorder-mcp`; do not merge it.

[env]: https://code.claude.com/docs/en/cloud-environments
[mcp]: https://code.claude.com/docs/en/mcp
[hooks]: https://code.claude.com/docs/en/hooks
