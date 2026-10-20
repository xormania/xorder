# Session F: Jev packet recommendation value

**Work branch:** `poc/mcp-jev-relevance`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/jev-relevance/`.

## Question and first result

Does Jev select useful context better than a small deterministic metadata
baseline, at an acceptable latency and context cost?

This session can run entirely independently of the cloud adapters. It must not
block a deterministic packet from proving delivery.

## Work

1. Inspect `docs/failure-triage.md` and
   `examples/jev/failure_triage.py`. Reuse bounded requests, candidate
   validation, credential separation, timeouts, and unavailable results.
   Failure classification is not automatically the right relevance question.
2. Prepare a small explicit fixture catalog covering test-kit reuse, CI practices,
   CUE, and unrelated controls. Record packet identities and applicability.
   Fixtures remain separate from accepted releases.
3. Write approximately twelve representative tasks before tuning selection.
   Include single-topic, testing-plus-CI, CUE-helpful-but-optional, no-relevant-
   packet, missing-target-fact, and incompatible-packet cases.
4. Define expected relevant sets and a practical judgment rubric. Keep several
   tasks untouched until the final comparison; avoid tuning every task to pass.
5. Implement a simple metadata/tag baseline and one Jev approach. Verify the
   current [Choice][choice] and [API][api] contracts.
6. For multi-packet relevance, evaluate independent relevance judgments or
   another supported formulation. A Choice distribution ranks alternatives; it
   is not an independent probability that each packet is useful.
7. Apply deterministic eligibility/access constraints first. Preserve unknown
   target facts; Jev cannot override incompatibility or exact pins.
8. Run a small live comparison if the authorized provider configuration is
   available. Record requested/returned model, candidates, output, latency,
   payload size, usage when provided, and failure behavior.
9. Compare useful selection and missed relevant packets, unnecessary packets,
   invalid/incompatible recommendations, and estimated consumption cost.
   Keep explanations grounded in metadata; do not invent model reasoning.

## Acceptance and early decision

Report whether the measured sample supports continuing the chosen approach,
changing the relevance formulation, or using the deterministic baseline for now.
A small fixture result is directional, not a general quality guarantee.

If there are no credentials, provide a runnable harness and exact missing
configuration. Mock responses test integration only and cannot support a claim
that Jev improves selection.

If Jev adds latency without useful selection gains, retain that result rather
than hiding it behind more orchestration. The broader recommendation goal
remains open to a better formulation or better packet metadata.

## Deliverables

Provide the fixture catalog, task/rubric set, baseline, provider adapter,
reproduction commands, and `RESULTS.md`. Keep task data bounded and public-safe;
do not send unrelated repository content or credentials to the provider.

Return exact selected packet references so A can later expose the operation
without absorbing another catalog model. A provider outage must leave
deterministic search/retrieval useful and explicitly labeled.
Open a PR to `feat/xorder-mcp`; do not merge it.

[choice]: https://docs.typesafe.ai/primitives/choice
[api]: https://docs.typesafe.ai/api/system-one
