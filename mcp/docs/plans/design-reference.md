# xorder MCP design reference

**Status:** supporting proposal, not a mandatory build sequence or fixed tool set. The current [scope](../scope.md) and selected [session plan](README.md) guide implementation. Prove the smallest useful path before expanding the proposed interface.

**Date:** 20 October 2026.

**Development location:** `mcp/` on `feat/xorder-mcp`; every PoC belongs in `mcp/poc/<poc>/`.

**Cloud requirement:** local and cloud delivery are part of the development scope. See [cloud readiness](../research/cloud-readiness.md) for research findings and live acceptance requirements.

## 1. Purpose and established direction

xorder MCP should help an agent find and use relevant xorder resources, including reusable context packets. Jev can help select relevant material. Harness hooks and diagnostics provide the delivery mechanism when simply making that material discoverable is insufficient.

The intended outcome is less repeated explanation and less repeated invention: an agent encounters the existing test-kit approach before creating another one, understands established CI practices while changing a workflow, and can retrieve concepts such as CUE when they are useful.

The following direction comes from the current discussion:

- Provide context packets through xorder.
- Use an xorder MCP to navigate catalogs and retrieve context.
- Explore Jev recommendations for selecting relevant packets.
- Build on experience with hooks that explain a diagnostic and direct the agent to a skill or further context.
- Support local installation and cloud deployment, including actual hosted-session registration and guidance delivery; verify the capabilities of each target surface.
- Reuse relevant experience from `uscient/agentscient`, specifically branch `shit`.

Everything below that specifies tool names, new metadata, implementation order, or defaults is a **proposal**. Existing behavior is identified explicitly. Unresolved decisions remain open rather than silently becoming requirements.

The central distinction is between **availability, delivery, and use**. A registered MCP makes a packet available. A hook can deliver a diagnostic. Neither establishes that the agent loaded the packet or applied its guidance. The design must make those stages observable separately.

## 2. Scope

| Area | Proposed responsibility |
| --- | --- |
| Catalog navigation | Search, inspect, and compare xorder resources and profiles, preserving their identities and evidence. |
| Context delivery | Retrieve a packet summary or selected sections from an exact release. |
| Recommendations | Use task facts, catalog metadata, and optionally Jev to identify relevant packets. |
| Diagnostic evaluation | Match observed work against configured rules and return actionable guidance with packet references. |
| Harness integration | Register the MCP, normalize native events, deliver diagnostics, and report actual adapter capabilities. |
| Installation | Provide repeatable local installation, inspection, updating, and removal of owned configuration. |
| Cloud integration | Deliver the same operations through local stdio and remote Streamable HTTP, with hosted-session registration and supported native or asynchronous feedback routes. |

The first implementation should expose read-only catalog and guidance operations. These can use caches and operational logs, but should not modify a consumer project, apply a profile, change CI, or install a resource as a side effect of discovery.

Later write operations are possible. They should be explicit tools with their own contracts, using existing xorder planning, application, and ownership machinery. This is a sequencing choice, not a permanent limitation on xorder.

xorder MCP does not need to become a second catalog, a general shell proxy, a replacement agent harness, or the owner of every project workflow. Packet content can describe a workflow without transferring ownership of that workflow to the MCP.

## 3. Existing foundations

The xorder baseline inspected for this document is commit `46cf55f87d1913dafb88f99d8b74247b581de588`. The Agentscient baseline is branch `shit` at `456457b9a0a9eb1ff285ee2d3e40535b6f722cdb`. These are source observations, not evidence that an integration has been tested in a current cloud session.

| Existing foundation | Consequence for this design |
| --- | --- |
| xorder has `image`, `binary`, `environment`, `configuration`, and `context` resource kinds. Profiles compose resources. | A context packet should use the existing `context` kind. A profile remains a composition, not a sixth payload kind. |
| `discovery.json`, `catalog-v2.json`, and `catalog.json` are generated views with different purposes. | MCP and any search index should derive from the same accepted records. |
| Definitions, release records, profiles, resolution locks, and installation receipts have distinct roles. | Discovery must not blur authored intent, verified availability, target compatibility, and installed state. |
| `context/project-guidance` is a public example with Codex audience, project scope, and an `AGENTS.md` destination. | Reuse its resource model; do not treat the sample as the user's personal guidance or require every packet to become an `AGENTS.md` file. |
| xorder already has an optional Jev adapter for bounded failure triage. | Reuse provider integration and validation patterns where appropriate. Relevance selection needs its own semantics and evaluation. |
| Agentscient contains native hook adapters, generated harness profiles, progressive MCP discovery, skill retrieval, and test-kit diagnostics. | Extract useful mechanisms. Its policies, authority model, and project-specific imports are not automatically xorder requirements. |

Sources: [xorder architecture][x-architecture], [context example][x-context], [failure triage][x-triage], and the [Agentscient mechanisms][a-profiles].

## 4. Architecture and ownership

Use a shared xorder operation layer behind MCP tools and hook adapters:

| Component | Owns | Does not establish |
| --- | --- | --- |
| Existing catalog and resolver | Resource identities, accepted releases, dependency and target checks | That a model understands or follows a packet |
| Context reader | Verified packet bytes, section selection, bounded responses | That reading activates project configuration |
| Recommendation service | Candidate construction, Jev requests, recommendation results | Compatibility, permission, or instruction authority |
| Diagnostic evaluator | Rule matching and structured diagnostics | That the harness delivered or enforced a result |
| Harness adapter | Native event mapping, local observations, output delivery | Support in a different harness or session type |
| MCP transport | Exposing typed operations to a client | Automatic invocation or native tool interception |

The MCP and local hook command should call the same operation layer. A hook should not require the agent to invoke an MCP tool before it can provide its first useful diagnostic. It can use locally available packet metadata and content, then direct the agent to MCP for expansion.

Recommendation and diagnostic calls should be stateless by default. If pagination, caching, or an experiment requires state, identify it explicitly with a catalog revision, cursor, or application handle. Do not depend on an implicit conversation being retained by the MCP transport.

The implementation language remains open. Reusing xorder's current Python validation and resolution code is a practical starting point. A separate hosted service is possible, but it should not recreate resolver semantics in another language without a concrete reason.

## 5. Context packet model

### 5.1 Preserve the existing resource contract

A packet is a versioned `context/<name>` resource. Its existing catalog fields include identity, version, purpose, capabilities, targets, prerequisites, documentation, release record, lifecycle, verification, and details. Authoring definitions currently use `revision`; catalog releases use `version`. The MCP should preserve that distinction. [Catalog schema][x-schema]

Existing context semantics remain authoritative:

- `details.audience` describes a harness, a list of harnesses, or explicit `any`; it is not a human role.
- `details.scope` describes the delivery scope.
- Missing harness facts remain missing facts when a concrete audience is required.
- Existing file destinations are delivery instructions for an installation path. MCP retrieval alone does not write those files.
- Artifact identity, downloaded archive digest, and a section's content hash describe different things.

### 5.2 Proposed metadata extensions

Keep the current definition format and Markdown payloads initially. Add metadata only where retrieval or diagnostics need it, with validation in xorder's shared code.

| Proposed field or concept | Purpose |
| --- | --- |
| Task tags and applicability hints | Describe situations such as adding tests, changing CI caching, or evaluating configuration languages. These are matching inputs, not proof of compatibility. |
| Named sections | Stable section IDs, titles, short summaries, content locations, and size information for selective loading. |
| Related references | Link to other packets, tools, examples, configurations, or profiles without duplicating their facts. |
| Authorship and provenance | Identify the source and revision of the guidance. |
| Review information | Record when content was reviewed and what may make it stale; age alone need not invalidate it. |
| Supersession or conflict notes | Describe migration and known conflicting approaches. They do not authorize automatic replacement. |
| Diagnostic associations | Associate a packet or section with named diagnostic rules. Rules still require an installed binding. |

For example, a proposed `context/test-kit` packet could have `overview`, `when-to-use`, `adapting-an-existing-kit`, and `examples` sections. These are illustrative names, not currently published resources.

Keep reusable guidance separate from consumer bindings. “Use the established test kit” belongs in a packet; the actual import path, test directories, and exceptions belong in the consuming project's configuration. Agentscient's `ops.testkit` convention must not become a universal requirement.

A packet may contain conceptual material, procedures, examples, or skill instructions. Text describing a command is not permission to run it. Installation or execution remains an explicit operation governed by the current task and harness.

## 6. Catalog and selection semantics

The default search view should favor current available, verified releases. Exact lookup should retain access to accepted historical records and report lifecycle values accurately: `available`, `deprecated`, or `withdrawn`. Visibility of a record does not imply it is selectable.

Profiles should appear as profiles, with readiness derived from their selections. The existence of a definition or profile must not be presented as an available release.

Every result should distinguish:

1. **Relevance:** whether this resource appears useful for the task.
2. **Availability:** whether an accepted release can be obtained.
3. **Compatibility:** whether known target facts satisfy its constraints.
4. **Selection:** whether it has actually been chosen or pinned.
5. **Delivery:** whether its content has been returned or installed.

An unknown target fact is not a known mismatch. Browse results may show a relevant packet with unresolved applicability; recommendation results should make that qualification visible. Resolution must use existing xorder checks before returning a compatible selection.

Once a packet is selected for retrieval or bound to a diagnostic, carry its exact reference. Do not silently switch to “latest” midway through the task. Existing pins remain effective unless an update is chosen.

Search results and cursors should identify their catalog snapshot. Any derived index must be rebuildable from the catalog and authorized overlays. It cannot become a second release ledger.

## 7. Proposed MCP tool contracts

These names and shapes are provisional. The initial interface should be small enough to advertise directly. All tools need input schemas, bounded output, stable errors, and read-only annotations where accurate. MCP annotations are descriptive hints, not access controls. [MCP tools][m-tools]

### 7.1 Shared types

| Type | Proposed meaning |
| --- | --- |
| `ResourceRef` | `id`, `version`, and canonical release `identity`; optional catalog revision for provenance |
| `ProfileRef` | Profile ID and source revision/hash; not an invented artifact release identity |
| `TargetFacts` | Relevant observed or supplied platform, harness, scope, commands, and project facts, with provenance |
| `PacketRef` | A `ResourceRef` whose kind is `context`, optionally identifying section IDs |
| `Budget` | Maximum result count and bytes; optional estimated token budget |
| `Diagnostic` | Rule ID/version, matched evidence, concise explanation, suggested action, exact packet references, and delivery metadata |

Remote tools must not interpret a client-supplied filesystem path as permission or ability to inspect that client's machine. Local adapters can gather supported observations through existing read-only checks and pass bounded facts.

### 7.2 Operations

| Proposed tool | Inputs | Result and invariants |
| --- | --- | --- |
| `xorder_catalog_search` | Query; resource/profile filters; resource kinds; optional target facts; budget; cursor | Bounded metadata cards, relevance basis, applicability gaps, catalog revision, next cursor. No bulk packet bodies. |
| `xorder_catalog_get` | Resource ID with optional version/identity, or profile reference | Definition/release distinction, exact identity where available, prerequisites, evidence links, lifecycle, and available choices. No activation. |
| `xorder_context_recommend` | Task description; target facts; selected resources and pins; already loaded packets; budget | Ordered packet references, reason grounded in metadata, unresolved facts, selection method, provider status, and provenance. Does not install or resolve away a conflict. |
| `xorder_context_get` | Exact packet reference; section IDs or section index request; byte limit; cursor | Verified requested content, section hashes, source references, and explicit truncation or continuation. No project writes. |
| `xorder_profile_resolve` | Profile reference or explicit profile document; target facts; pins; authorized overlay reference | Existing resolver output or concrete missing facts, conflicts, and alternatives. No apply operation and no silent upgrade. |
| `xorder_diagnostic_evaluate` | Configured binding reference; normalized event; bounded observations; target facts | Matched diagnostics or explicit no-match result, with evidence and packet references. Effective handling comes from configured bindings and adapter support. |
| `xorder_status` | Optional scope and explicit probe request | Server/catalog status, configured provider, and reported adapter capabilities. Distinguishes configured, checked, and observed states. Does not claim to inspect a remote harness it cannot reach. |

If an unversioned lookup finds several viable choices, return choices. It should not imply a pin has been created. Exact references are required when loading content that will be cited in a diagnostic or used as an established selection.

### 7.3 Results, errors, and budgets

Use a versioned application result schema, separate from the negotiated MCP protocol version. A proposed envelope contains `schema_version`, `status`, `data`, `catalog_revision`, `warnings`, and pagination/truncation information where applicable.

Return typed structured content and a concise text rendering for clients that need it. Validate outputs against their declared schema. Relevant error codes include `invalid_argument`, `not_found`, `missing_target_facts`, `incompatible_target`, `release_unavailable`, `integrity_mismatch`, `provider_unavailable`, and `budget_exceeded`. An empty search or no matching diagnostic is an ordinary result.

Proposed starting budgets for measurement:

- Search: five results by default, twenty maximum per page.
- Packet content: 16 KiB per response by default, with section-based continuation.
- Inline hook guidance: approximately 2 KiB, including the actionable explanation.
- Provider requests: bounded candidates and state, a timeout, and no unbounded retries.

These are tuning hypotheses. Measure usefulness and latency before making them defaults. Never truncate silently, cut executable examples into misleading fragments, or label an estimate as an exact token count.

Agentscient's search/describe/invoke approach is useful evidence for progressive discovery. Start with the small typed tool set above; introduce an additional indirection layer only if tool growth or client limits justify it. Do not use a generic invocation tool to hide permissions or bypass individual operation schemas. [Agentscient MCP][a-mcp]

### 7.4 Asynchronous diagnostic delivery

Provide an optional event interface alongside request/response tools. The cloud research identifies Work MCP Events as a documented route; its live integration remains to be proved.

A proposed diagnostic-available event identifies the event, producer, workspace/task correlation, finding, relevant source revision, and exact packet references. Subscriptions need persistent state, expiry/cancellation handling, authenticated callback delivery, and duplicate handling. This state belongs to the event delivery component; ordinary catalog and recommendation requests need not become conversational sessions.

The producer must be identified: a native hook, an instrumented command, CI, or an explicit workspace observer. Delivery cannot establish coverage of work the producer did not observe. Acknowledgement, conversation receipt, packet retrieval, useful action, and any blocking behavior remain separate observations. Late findings must retain their source revision so they are not presented as observations of newer work.

Use the target platform's supported subscription protocol. This section proposes application data and behavior, not new protocol method names. See [cloud readiness](../research/cloud-readiness.md).

## 8. Jev recommendation design

### 8.1 Selection pipeline

1. Build a candidate set from authorized catalog records and packet metadata.
2. Apply deterministic constraints, preserving unknown facts separately from known incompatibilities.
3. Supply Jev with bounded task state, selection criteria, and eligible candidate descriptions.
4. Validate its response against the submitted candidates and expected output shape.
5. Return exact packet references and metadata-based explanations.
6. Record enough provenance to reproduce the selection without retaining unnecessary task content.

Jev recommends relevance. The xorder resolver determines compatibility and exact resource selection. A model response cannot promote an unpublished definition, override a target mismatch, authorize private access, or replace a pin.

### 8.2 Choose the decision primitive deliberately

TypeSafe Choice selects among alternatives and returns a distribution over those alternatives. That distribution is not an independent probability that each packet is useful. Its confidence should not be presented as a calibrated probability of correctness. Several packets may be useful together. [TypeSafe Choice][t-choice]

Evaluate two approaches:

- Independent relevance questions for packets, using suitable boolean or scoring primitives.
- Choice for genuinely exclusive routing, such as selecting which topic family to explore first, followed by retrieval within that family.

Do not assume repeatedly taking the highest Choice result produces a sound multi-packet recommendation. Measure against examples where both test-kit and CI guidance are relevant.

Candidate construction is part of recommendation quality. Record candidate IDs and exclusions. When the set fits the provider's limits, avoid unnecessary narrowing; for larger catalogs, evaluate retrieval or hierarchical selection for recall rather than silently excluding material by keywords.

The API returns structured answers; it does not supply a free-form reasoning narrative for this use. “Why recommended” should cite matched task facts and authored applicability metadata. Do not invent a Jev explanation.

### 8.3 Reuse and failure behavior

xorder's existing failure-triage adapter demonstrates bounded requests, candidate validation, credential separation, redaction, timeouts, and explicit unavailable results. Reuse those patterns without importing the failure-classification question map into packet selection. [Existing adapter][x-jev]

The documented API accepts state, model, and questions and returns typed answers. Record both the requested model and returned model; aliases can resolve to a different concrete model. The alias-versus-pinned-model policy is an open decision. [TypeSafe API][t-api]

If Jev is unavailable, catalog search and packet reading should still work. A deterministic fallback may return metadata matches, explicitly labeled `deterministic_fallback`. It must not claim that Jev selected them.

Provider credentials stay in the service or adapter configuration, never in packets or model-visible results. Candidate selection must apply access filtering before external requests. Sending task state to Jev must be an explicit installation/configuration choice, with a documented bounded payload.

## 9. Hooks and diagnostic delivery

### 9.1 A useful diagnostic contains guidance

A weak diagnostic says only “read the test-kit skill.” A useful diagnostic says what was observed, why it matters, the next action, and which section contains the details.

Illustrative output:

> A new test file was added, but this project's configured test-kit entry point was not found. Check whether the existing kit covers this test before introducing another fixture pattern. See the selected test-kit packet, section “adapting-an-existing-kit.” If this test intentionally falls outside the kit, use the project's documented exception.

The actual rule must use the consumer's configured entry point and evidence. This example does not establish an import convention or make every missing import an error.

### 9.2 Normalized events and results

Adapters should map supported native events into a shared contract: event ID, phase, harness identity, workspace binding, operation, affected targets, observation source, and bounded evidence. Potential phases include session start/resume, before or after a tool operation, after a failure, and task completion. Each adapter declares which it can actually observe.

Rules must account for equivalent mutation paths: shell writes, editor tools, patches, and MCP-backed edits where visible. Partial visibility should be reported. For patch events, evaluate every affected target, not just the first path.

The cloud research reproduced a shell-inspection gap for a Python file write embedded in a shell command. Supplement command-shape inspection with bounded checks of relevant changed and untracked files after a supported operation. Compare with pre-existing workspace state rather than attributing every dirty file to the latest command.

A diagnostic result should include:

- Stable rule ID/version and a fingerprint for duplicate suppression.
- The observed evidence and the rule's applicability.
- A short explanation and a concrete next action.
- Exact packet and section references.
- Requested handling, supported handling, and observed delivery outcome as separate values.

An MCP diagnostic call is also useful for inspection and testing, but it does not replace native interception. The native adapter must be wired into the relevant harness event.

### 9.3 Advisory and enforced behavior

The mechanism must support configured advisory feedback and, where the harness supports it, blocking a relevant operation until a concrete condition is resolved. Enforcement is attached to specific project rules, not to a generic assertion that the agent “has understood” a packet.

An agent's acknowledgment or a packet-read receipt is evidence of access, not understanding. A blocker should use a checkable condition, offer a recovery path, and respect explicit project exceptions and the user's current direction.

Do not silently downgrade a configured blocking rule to advisory behavior when a harness cannot enforce it. Report the unsupported capability during installation or preflight. A model-supplied tool argument cannot grant itself a new enforcement policy.

### 9.4 Timing, caching, and repetition

Keep deterministic rule matching on the fast path. Use cached packet references and concise local guidance where possible; avoid requiring a fresh Jev request for every tool event.

Suppress duplicates by rule, relevant content, and event context. Re-emit when the relevant file, packet version, binding, or session context changes. Avoid repeated stop-hook loops and permanent suppression after a single old acknowledgment.

On provider or network failure, local diagnostics should use verified cached guidance when available and identify stale data. Rules that cannot be evaluated should report that state; their configured failure behavior should be explicit.

Agentscient supplies useful event normalization and kit-import diagnostic experience, including advisory hook tests. Those sources demonstrate mechanisms, not universal blocking behavior. [Native events][a-native], [hook guidance tests][a-tests]

## 10. Installation and runtime requirements

### Local

Provide an installation plan that identifies the server command, catalog source, cache, selected packets/profile, harness adapter, hook bindings, and secret references.

The installer should:

- Register a local stdio MCP server using the supported harness configuration.
- Install selected hook bindings and a minimal bootstrap reference.
- Preserve unrelated configuration and existing project guidance.
- Detect ownership conflicts before writing.
- Support idempotent reruns, inspection, updates, and removal of owned entries.
- Verify server startup separately from native hook delivery and model-visible output.

Use existing xorder ownership/receipt mechanisms where they fit. Do not require Docker solely to deliver context.

### Cloud

Cloud readiness is an implementation requirement. Expose the same operation layer through local stdio and remote Streamable HTTP, and support a local process inside a hosted workspace where the surrounding harness can register it. MCP defines both transports; actual client support must be tested. [MCP transports][m-transports]

Deployment options include a hosted HTTPS service and a private/local service reached through a supported tunnel. Keep endpoint, authentication, catalog location, and packet storage configurable. A server must not require access to the caller's filesystem merely to search or retrieve packets.

Provide native hook delivery where supported and an optional asynchronous event route with an identified producer. The cloud research adds Work MCP Events, local-server tunnel reuse, and precise hook timing. Advisory pre-tool feedback may reach the model after the operation; prevention needs a separate native check.

Installing a CLI inside a workspace does not establish that the surrounding cloud session uses its configuration or hooks. Remote MCP registration also does not establish native hook access.

For each cloud target, record the actual session product, installation owner, supported transport, authentication route, persistence, and proven event-delivery capabilities. [Cloud readiness](../research/cloud-readiness.md) carries the research findings and acceptance cases. This specification does not declare a cloud target supported.

### Shared

Use an SDK with explicitly tested protocol versions. The protocol baseline consulted here is `2026-07-28`; do not assume every client supports that revision. Keep an adapter compatibility matrix and validate actual tool behavior.

Remote deployment needs normal authorization, transport security, and request limits. Private overlays and packets must remain scoped to the authenticated principal. Cache keys, cursors, and recommendation logs must preserve that isolation.

Neither a client registration nor a server health response is proof of end-to-end delivery.

## 11. Requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| R1 | Use canonical xorder records and resolver semantics. | MCP and existing xorder operations agree on identities, target failures, pins, and alternatives for the same inputs. |
| R2 | Retrieve exact context progressively. | A caller obtains an index and one section without loading the full catalog or packet; hashes and truncation are explicit. |
| R3 | Separate relevance from compatibility and availability. | A relevant packet with a missing harness fact is qualified; an incompatible release is not returned as resolved. |
| R4 | Make Jev optional and observable. | Recommendation output identifies method and model; a provider outage preserves deterministic search and cached reading. |
| R5 | Deliver actionable native diagnostics. | A configured event produces useful model-visible feedback with an exact packet reference. |
| R6 | Describe enforcement honestly. | Unsupported blocking fails preflight clearly; a supported blocker demonstrably prevents the targeted operation until its condition is addressed. |
| R7 | Cover observed mutation paths and lifecycle changes. | Relevant rules behave consistently across supported edit tools, patches, and shell paths; resume and changed-content cases are measured. |
| R8 | Preserve user and project ownership. | Installation is repeatable, leaves unrelated content intact, reports conflicts, and removes only owned configuration. |
| R9 | Keep failures bounded and recoverable. | Timeouts, missing packets, stale catalogs, invalid provider output, and integrity failures have specific results. |
| R10 | Protect private content and credentials. | Unauthorized packets never enter results or Jev candidates; secrets are absent from model-visible output. |
| R11 | Avoid treating retrieval as instruction authority. | Reading a packet causes no hidden activation or project modification; conflicting guidance remains visible. |
| R12 | Measure useful behavior separately from plumbing. | Event firing, diagnostic delivery, packet loading, and observable task outcomes are reported separately. |
| R13 | Deliver a cloud-ready service with transport parity. | Local stdio and remote HTTP return equivalent identities and results; actual hosted-session registration, authentication, restart, and update behavior are demonstrated. |
| R14 | Support asynchronous feedback through a known observer. | A fixture subscription receives a correlated finding, survives the intended restart behavior, handles duplicates, and reports producer coverage. |

Run a small set of meaningful scenarios:

1. **Test-kit reuse:** add a test in a project with an existing kit. Compare MCP availability alone with configured diagnostic delivery; inspect whether the resulting test uses the appropriate established approach.
2. **CI work:** change a workflow where caching or test-selection guidance applies. Retrieve relevant sections and verify the resulting change against the project's actual constraints.
3. **Conceptual guidance:** ask about a configuration problem where a CUE packet might help. Verify retrieval without assuming CUE must be installed or chosen.
4. **Multiple relevant packets:** use a task spanning testing and CI. Check that selection can surface both without misrepresenting a Choice distribution.
5. **Target gaps and pins:** remove a required target fact and introduce a newer packet release. Verify explicit gaps and preservation of the selected version.
6. **Failure and integrity:** make Jev unavailable, remove a packet, and supply mismatched cached bytes. Check distinct, truthful outcomes.
7. **Hook lifecycle:** exercise supported edit paths, resume, repeated events, and changed content. Check coverage and duplicate suppression.
8. **Cloud delivery:** in each investigated host, demonstrate outer-session tool registration and native diagnostic delivery independently.

Use representative tasks with and without hooks and inspect the outputs. The primary question is whether this reduces repeated explanation and incorrect reinvention. Packet-read counts alone are not a success metric.

## 12. Proposed delivery sequence

1. **One complete local path:** expose existing catalog inspection and exact packet retrieval; publish one useful test-kit packet; bind one native diagnostic in one chosen harness; verify useful delivery.
2. **Recommendation evaluation:** add Jev-backed selection, deterministic fallback, and a small task set covering test kits, CI, and CUE. Keep candidate and outcome evidence.
3. **Reusable installation:** make configuration ownership, updates, pinning, diagnostics, and compatibility checks repeatable across additional local adapters.
4. **Cloud acceptance:** use the same core in remote HTTP and the selected hosted integrations. Prove personal Work retrieval, a separately scoped event subscription, and actual Codex Cloud registration where available. Track unresolved host interfaces without removing cloud support from scope.

Cloud transport and deployment configuration belong in the initial design, not a later rewrite. These slices describe the proposed order of proof, not permission to declare a local-only service complete.

This sequence includes hook delivery in the first useful slice. A catalog-only prototype is useful plumbing, but does not resolve the user's stated experience that agents ignore optional context.

## 13. Ideas worth exploring

| Idea | Value and boundary |
| --- | --- |
| Packet-to-skill projections | Generate harness-specific skill wrappers from a packet while keeping one content source and explicit versions. |
| Task-specific bootstrap | On start or resume, provide a small set of relevant pointers and concise guidance rather than the whole catalog. |
| Failure-to-context routing | Associate a failed test or CI diagnostic with an appropriate packet section; build on existing triage receipts without changing the test result. |
| Curated context profiles | Compose packet selections for recurring work without merging their bodies into one large instruction file. |
| CUE for validation | Explore validating packet or rule structure with CUE if it simplifies maintenance. This is separate from publishing a packet that teaches CUE. |
| Outcome feedback | Let the user explicitly mark a recommendation useful or irrelevant. Do not silently convert interaction history into new policy. |
| Context update plans | Show which pinned packets changed, why, and which bindings would be affected before an explicit update. |
| Catalog-aware alternatives | Explain nearby tools, configurations, or environments when a packet points to a practical resource, without automatically installing them. |

## 14. Open decisions

- Which harness and existing test-kit example should anchor the first complete local path?
- Which packet metadata is needed initially, and which can remain ordinary Markdown?
- Should recommendation use independent relevance judgments, hierarchical routing, or a measured combination?
- Which rule conditions warrant blocking, and what are their project-specific exceptions?
- Should the first server run directly in xorder's Python runtime, with a hosted wrapper later?
- Which public and private catalog/overlay arrangements need support first?
- What latency and context budgets are acceptable after observing actual tasks?
- Which cloud hosts expose enough control to meet the delivery requirement?

Resolve these through a small implementation and evidence. Do not treat uncertainty about a cloud host as a reason to reduce the overall goal to optional search.

## Sources and evidence boundary

Repository statements above come from the pinned source revisions below. Protocol and provider statements come from official documentation consulted on 20 October 2026. The later cloud research report adds documentation findings and sixteen isolated adapter outcomes, including two expected limitations. These are reported research evidence here; no native hosted-session or live Jev acceptance is claimed. See [cloud readiness](../research/cloud-readiness.md) for the distinction.

- [xorder README][x-readme], [architecture][x-architecture], [catalog schema][x-schema], [profiles][x-profiles], and [context example][x-context].
- [xorder failure-triage contract][x-triage] and [Jev adapter][x-jev].
- Agentscient branch `shit`: [harness profiles][a-profiles], [native events][a-native], [MCP discovery][a-mcp], [skill retrieval][a-skills], and [hook guidance tests][a-tests].
- Official [MCP tools][m-tools] and [transport specification][m-transports], revision `2026-07-28`.
- Official [TypeSafe Choice][t-choice] and [System One API][t-api] documentation.
- Research inputs supplied by the maintainer: `xorder-cloud-context-research-2026-10-20.md` and `xorder-cloud-context-research-report-2026-10-20.md`. The latter completes documentation/source research and isolated adapter probes; native cloud integration remains unverified. [Cloud readiness](../research/cloud-readiness.md) records the implementation implications and official source links.

[x-readme]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/README.md
[x-architecture]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/docs/architecture.md
[x-schema]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/schemas/catalog-v2.schema.json
[x-profiles]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/docs/profiles.md
[x-context]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/docs/resources/context-project-guidance.md
[x-triage]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/docs/failure-triage.md
[x-jev]: https://github.com/xormania/xorder/blob/46cf55f87d1913dafb88f99d8b74247b581de588/examples/jev/failure_triage.py
[a-profiles]: https://github.com/uscient/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/devlane/hooks/profiles.py
[a-native]: https://github.com/uscient/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/devlane/hooks/native.py
[a-mcp]: https://github.com/uscient/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/conductor/tools/dev_mcp.py
[a-skills]: https://github.com/uscient/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/conductor/tools/project_providers/symfony.py
[a-tests]: https://github.com/uscient/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/devlane/hooks/tests/test_guidance.py
[m-tools]: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
[m-transports]: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
[t-choice]: https://docs.typesafe.ai/primitives/choice
[t-api]: https://docs.typesafe.ai/api/system-one
