# Session D: asynchronous Work diagnostic delivery

**Work branch:** `poc/mcp-work-events`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/work-events/`.

## Question and first result

Can an external finding reach a subscribed Work conversation and cause useful
follow-up without relying on a voluntary discovery call?

The first result is one real fixture subscription and one matching event.
Do not build a generalized event bus to answer it.

## Establish the target first

Verify the current [MCP Events contract][events], required protocol/SDK support,
and availability on the actual account/workspace. The research reports protocol
`2026-07-28`; confirm the current supported contract before coding.

Use C's connected endpoint if ready. Otherwise implement an isolated minimal
fixture endpoint and producer under this PoC, then integrate with A/C after the
first result. Connection/access limitations must be reported immediately.

## Work

1. Implement one diagnostic-available event with a small, explicit payload:
   event ID, producer, workspace/task correlation, source revision, finding,
   exact packet reference, and timestamp.
2. Start with a deterministic fixture producer that can emit a matching finding
   and a clean control. Label this as simulated observation.
3. Use the platform's supported user-authorized subscription flow. Persist the
   required subscription state and follow its callback/authentication contract.
4. Deliver the event and distinguish transport acknowledgement, conversation
   receipt, packet retrieval, and useful follow-up.
5. Add one real observer, preferably an instrumented fixture test command, that
   emits a finding when the relevant condition actually occurs.
6. Exercise a duplicate, a late event referring to an older source revision,
   producer restart, and subscription cancellation/expiry as supported.
7. Record what the producer can observe. A command observer does not see work
   that bypasses the command; CI does not see uncommitted edits.

## Acceptance

- A real subscription exists in the intended conversation.
- The matching finding reaches that conversation and is correlated correctly.
- The response uses the referenced context in a useful way.
- A clean control causes no irrelevant action.
- Duplicate/late delivery and lifecycle behavior are explicit.
- The actual observer's coverage is demonstrated separately from callback delivery.

An acknowledged webhook alone does not pass. A native hook wrapper that runs
outside Work is only a producer, not proof of Work receipt.

## Early decision and deliverables

If the subscription interface is inaccessible, stop speculative event plumbing
and return the exact account/product blocker plus the runnable fixture.
If callbacks arrive but do not cause useful follow-up, test one corrected
subscription workflow and retain both outcomes.

Return setup/run/cleanup instructions, event schema, producer coverage, sanitized
traces, and `RESULTS.md`. Recommend whether the route is useful for diagnostics,
which latency/coverage limits matter, and what can be shared with A/C.
Open a PR to `feat/xorder-mcp`; do not merge it.

[events]: https://developers.openai.com/plugins/build/mcp-events
