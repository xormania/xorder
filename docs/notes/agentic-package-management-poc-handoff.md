# Agentic Package Management System — PoC handoff

Prepared for xor · 10 November 2026

## Mission

Implement and run a small proof of concept for an **Agentic Package Management System**. Preserve its useful scenarios as executable contracts that can become future end-to-end tests.

The question is whether independently supplied software and context can be discovered, selected, delivered, and used by agents through a coherent interface, both directly and through an orchestrator. Demonstrate useful work and interchangeable implementations. Keep design choices revisable until the experiments provide evidence.

This packet is an implementation brief for an isolated PoC. Product adoption, a permanent standard, and production deployment remain undecided.

## Owner direction

The discussion established these goals:

- Reduce accumulated obsolete image versions and repeated preparation work.
- Reuse capabilities by type of work instead of maintaining a custom image for every project.
- Let projects configure or construct the environments they need.
- Make capabilities and relevant context easy for local and cloud agents to access.
- Allow Xorchestrate to consume Xorder or another compatible source through a replaceable interface.
- Explore the broader possibility of a global agent capability/context package-management ecosystem.
- Use the PoC to generate reusable end-to-end tests and inform a later decision.

“Global” has not been specified as a central registry, a daemon, global installation, or a particular deployment topology. The package format, implementation language, backend, port names, and standardization strategy are also undecided.

## Start with existing work

Inspect current repository instructions and refresh source heads before changing anything. Preserve the following revisions as research baselines; they are not mandatory implementation bases.

| Source | Inspected baseline | Relevant foundation |
| --- | --- | --- |
| [Xorder](https://github.com/xormania/xorder) | `09f1489c6c1ce4dc4ba32ff108c175a5f720f0f9` | Resource model, catalogs, profiles, resolution, exact identities, file application and build-component reuse. |
| [Xorder MCP branch](https://github.com/xormania/xorder/tree/feat/xorder-mcp) | `1b7911d2500456aca650ca0cee9fdc63b59f74f1` | Context-delivery design and a runnable stdio/HTTP transport fixture. |
| [Xorchestrate](https://github.com/xormania/xorchestrate) | `c545eb4781e35f12eee61e29c25b8bbc4debea25` | Application-owned ports, MCP/CLI providers, native sessions, effect tracking and reusable behavioral contracts. |

Read the relevant implementation before proposing replacements:

- Xorder: [architecture](https://github.com/xormania/xorder/blob/master/docs/architecture.md), [resolver](https://github.com/xormania/xorder/blob/master/scripts/xorder/resolve.py), [application](https://github.com/xormania/xorder/blob/master/docs/application.md), [prepared components](https://github.com/xormania/xorder/blob/master/docs/build-components.md), and [retention](https://github.com/xormania/xorder/blob/master/docs/retention.md).
- Xorchestrate: [ports](https://github.com/xormania/xorchestrate/blob/master/xorchestrate/ports.py), [capability adapters](https://github.com/xormania/xorchestrate/blob/master/xorchestrate/adapters/capabilities.py), [architecture](https://github.com/xormania/xorchestrate/blob/master/docs/hexagonal-architecture.md), and [testing framework](https://github.com/xormania/xorchestrate/blob/master/docs/testing-framework.md).
- Xordination: [Xorder delivery recipe](https://github.com/xormania/xordination/blob/master/docs/xorder.md). This separates executable, optional image, configuration, context and profile, with distinct package, service, adapter and communication checks.
- Agentscient: [retained MCP context experiment](https://github.com/xormania/agentscient/blob/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/conductor/reports/mcp-context-evaluation-2026-09-05.md). It measures exact-source parity across interfaces and change-only retrieval. Reuse applicable mechanisms and contract scenarios without importing historical role structures.

Relevant current limits:

- Xorder resolves explicit resource alternatives; it does not currently implement arbitrary capability composition across providers.
- Its file application helper reports images as external actions. An installation receipt does not establish a running environment.
- Prepared components are internal build inputs. Their existence does not establish a public plugin contract.
- Xorchestrate already has `CapabilityProvider.discover/invoke` and MCP/CLI adapters. Its current MCP provider is stdio-based; inspect current transport support before assuming remote HTTP support.
- The [Work probe](https://github.com/xormania/xorder/blob/feat/xorder-mcp/mcp/poc/cloud-probe-work-mode/RESULTS.md) verified SDK transport behavior but did not establish actual hosted-session registration or useful model behavior. Treat that as historical evidence, not a current platform prohibition.

## Questions the PoC must answer

1. Can one useful capability be consumed by a standalone client and by Xorchestrate without duplicating its domain logic?
2. Can a second independently authored source satisfy the same contract without changing consumer orchestration code?
3. Can a project compose selected resources while retaining project-owned paths, commands and dependency locks?
4. Can an agent receive the right guidance and use the delivered capability to complete ordinary project work?
5. Can updates, interruption, context changes and cleanup be understood from recorded identities and observed state?
6. Which portions need a common contract, and which work better as backend-specific extensions?

Report negative findings and partial support precisely. A smaller working boundary is a useful outcome; an untested path remains an open part of the objective.

## Experimental scope and working hypotheses

Start with a small shared operation layer and adapters. One plausible division is catalog/resolution, optional preparation/execution, and agent delivery. This is a hypothesis to test, not an architectural requirement.

Use existing payload formats and backends where practical. OCI images, native environment definitions, ordinary files and skill/context directories need not be converted into a new universal archive. A package may reference existing artifacts.

For the first experiment, write down the minimum information needed to describe:

- A provider and the operations it supports.
- A resource, its origin, version, exact content identity and retrieval location.
- Relevant requirements, compatibility evidence and usage/context references.
- A project selection and the exact resources it resolves to.
- A preparation operation, its owned outputs and observed result, when preparation is supported.
- Activation for a specific workspace and agent session, where that can be demonstrated.

Keep resource availability, selection, installation, runtime readiness, context delivery and useful application distinguishable. Providers may support different subsets of operations. A context-only repository should be a valid experimental source.

Use tentative schema and operation names. Record choices with the observed problem they solve. Avoid exposing the entire current Xorder implementation as the permanent external contract.

## Fixtures and real boundaries

### Providers

**Provider A: Xorder.** Adapt the current accepted catalog and resolver. Select real, available records and retain their actual identities. A planned image is not an available artifact.

**Provider B: a small independent repository.** Author its manifest and payload independently of Xorder's private build or release-record layout. It may supply a native tool, a context package, or a compatible alternative implementation. It should require only the proposed public contract and an adapter.

For substitution testing, both providers need at least one fixture resource with the same explicitly defined behavioral contract. Their implementations, versions and digests may differ. Compare observable outcomes rather than assuming their bytes or identity strings should match.

Host the second fixture through a disposable local repository or HTTP server. Exercise actual retrieval and integrity checking. Keep all experimental records separate from accepted public release catalogs.

### Consumer workload

Prefer a small existing consumer fixture. A suitable fallback is a tiny Python project with one real behavioral defect and an independently asserted expected result. A packaged test runner, project configuration and focused context must help exercise that project.

The check must execute real code and validate an actual output or behavior. Avoid a fixture whose only achievement is finding a magic receipt, echoing a marker, or making a scripted protocol conversation succeed.

Include a second project with different paths or configuration that can reuse the same package artifacts. This tests the original motivation for avoiding project-specific images.

Add one existing Xorder environment path when the available execution surface supports it. If it cannot run, retain successful catalog/resolution evidence and the exact execution gap. Do not equate that partial result with an executed Xorder environment.

### Clients and execution

- A standalone CLI or ordinary programmatic client.
- A real MCP client across a process or network boundary.
- Xorchestrate through configured adapters and its actual application invocation path.
- A fresh real agent session for the delivery/use experiment.

Start with supported local execution. Probe the intended cloud surface separately. Reuse the existing MCP fixture where useful, but its synthetic diagnostic is not the consumer workload.

## Execution sequence

1. **Inspect and bound the experiment.** Record repository revisions, available runtimes, reachable endpoints, actual harness access and existing reusable code. Choose a location and isolated branch or checkout. Follow its current `AGENTS.md`.
2. **Write the behavioral contract and fixture inputs.** Specify observable outcomes and independent expected values before wiring providers. Keep a short decision log identifying tentative choices.
3. **Complete one useful path.** Discover, resolve, acquire, prepare as needed, run the workload, and retain the result. Establish this before broadening the abstraction.
4. **Add the independent provider and second project.** Demonstrate reuse and substitution through configuration or an adapter. Identify any consumer-core changes substitution requires.
5. **Exercise the interfaces and Xorchestrate.** Reuse its current provider path first. Introduce a dedicated typed port only if the experiment demonstrates a distinct application responsibility; explain why.
6. **Exercise failure, update and recovery cases.** Use the scenario catalog below. Retain failed observations as well as successful reruns.
7. **Run the fresh-agent and cloud experiments.** Preserve native tool calls and task outputs. Continue other useful work if a platform registration step is inaccessible.
8. **Deliver a reproducible result.** Retain runnable tests, fixtures, commands, evidence and a recommendation about what deserves promotion.

This sequence is a practical starting order. Adapt it to evidence without silently discarding the original questions.

## Scenario catalog for future end-to-end tests

Use stable scenario IDs. Keep expected behavior separate from transport, provider and runtime setup.

| ID | Scenario and action | Observable result / independent oracle |
| --- | --- | --- |
| APMS-01 | Discover both providers from clean state. Include a context-only source and an unsupported optional operation. | Provider origins and supported operations are explicit; each source is usable for its supported purpose. Discovery does not install or activate anything. |
| APMS-02 | Resolve a project's selections with an existing lock, missing target facts, a known mismatch and an ambiguous alternative. | Compatible pins persist. Missing facts, incompatibility and ambiguity remain distinct. No fabricated target fact or silent provider substitution appears. |
| APMS-03 | Acquire an exact artifact; repeat with altered bytes at the same location. | The valid payload matches the expected digest and runs. The altered payload is rejected before activation; previously usable owned state remains inspectable. |
| APMS-04 | Use the same reusable package in two projects with different layout and configuration. | Both projects produce their independently expected results while sharing unchanged artifact identities. Project configuration does not leak into the other project. |
| APMS-05 | Substitute independently implemented providers for the same declared fixture capability. | The consumer use case and expected behavioral result stay the same. Origins and selected identities change explicitly; provider-specific differences remain visible. |
| APMS-06 | Repeat the same logical operation through CLI, MCP and Xorchestrate. | Exact resource selection and domain results agree for identical inputs. Transport/session metadata may differ. Tests cross real subprocess or network boundaries. |
| APMS-07 | Prepare a supported composition twice; then change one material component input. | The unchanged request reuses prepared output where reuse is advertised. The changed input yields a new identity and validation. Metadata-only changes do not claim changed executable bytes. Record actual work rather than inferring cache reuse from timing alone. |
| APMS-08 | Deliver guidance to a fresh agent performing an ordinary project task. | Native evidence shows discovery/retrieval and use of the relevant capability; independent project checks establish the result. The task prompt does not tell the agent the packet contents or the solution. |
| APMS-09 | Resume a session or start another, then change relevant package/context inputs. | Session bindings remain distinct; changed guidance is identified and retrievable. A delivered or loaded record does not itself claim comprehension or compliance. Measure any compact change response against exact sources. |
| APMS-10 | Lose a response or stop a preparation process at a meaningful boundary; repeat the request. | Recorded operation identity supports recovery without blindly duplicating effects. Unknown outcomes stay visible until evidence resolves them. A new request cannot reuse an identity for different intent. |
| APMS-11 | Deliberately upgrade a fixture package, preserve a local configuration edit, and attempt rollback. | The upgrade changes the intended selection explicitly. Unowned or modified files are preserved or reported as conflicts. Rollback restores only what its backend actually supports. |
| APMS-12 | Run cleanup against a disposable fixture cache containing active, shared, expired and abandoned objects. | Retained dependencies and active operations survive. Eligible owned fixture objects can be removed under a declared test policy. Reference counts or a complete fixture graph support the decision; production registry state is untouched. |
| APMS-13 | Exercise delivery in the selected cloud product and compare workspace access with local execution. | Actual hosted-session registration and native calls are recorded if available. A local path is not assumed to be visible remotely. Unsupported registration, mounts, networks or execution capabilities have precise evidence and gaps. |

For APMS-07, choose a cheap composition that the selected backend genuinely supports. This scenario need not introduce a universal dependency solver or rebuild the entire image library.

For APMS-08, use an ordinary prompt such as: “Fix the failing behavior in this project and run its documented checks.” Install the integration beforehand, then use a fresh session that has not read the fixture solution. Keep hidden expected results outside that session's initial context.

For APMS-12, use a deterministic test clock and owned disposable objects. The live Xorder retention policy is evidence to inspect, not permission to delete published artifacts.

## Evidence and test structure

Organize tests around reusable behavioral contracts. Provider and transport adapters supply concrete setup; a collected test module should not become the fixture library. Follow the host repository's established test framework where one exists.

Use a small declared matrix instead of an uncontrolled Cartesian product. Cover both providers, both direct and orchestrated consumption, supported transports, an available execution backend, and the named cloud probe. Add combinations when a specific difference needs verification.

Each scenario result should record:

- Scenario and run IDs, timestamp, source revisions and dirty-state information.
- Provider/catalog identities, package identities, project input identity and selected lock.
- Actual caller, transport, harness/product/version and execution target.
- Preconditions, action, expected observation and actual observation.
- Exit codes or protocol results, relevant logs and output artifact hashes.
- Outcome: `passed`, `failed`, `blocked`, `unsupported` or `not_run`, with a reason.
- Known limits, recovery performed and any remaining owned state.

Those outcome names are a reporting convention for the PoC, not a required production API schema.

Separate three evidence levels:

1. **Deterministic system behavior:** contracts through real I/O with controlled fixtures.
2. **Native delivery:** the intended agent session can discover and invoke the integration.
3. **Useful agent behavior:** a fresh agent uses it to complete an independently checked task.

An SDK client is valid evidence for level 1. An inner CLI agent is evidence for that inner harness. Neither establishes registration in the surrounding hosted conversation. Report which levels were actually exercised.

Reuse historical evidence only for the exact unchanged behavior it supports. Do not present previous test counts as results of this PoC. Run relevant repository checks and the agreed scenarios; broaden verification when changes or findings justify it.

## Working boundaries

- Keep the experiment isolated and reviewable. Do not publish experimental packages as accepted Xorder releases, merge changes, or alter production retention as part of this PoC.
- Use existing authorized credentials and execution access. Do not embed credentials in packages, context, locks or reports. Identify a genuinely missing account action precisely while continuing independent work.
- Preserve unrelated files, harness configuration and sessions. Track the files, services and temporary resources the PoC owns so cleanup is repeatable.
- Reuse established project policies and source provenance. Historical agent roles or recommendations do not become authority merely because code was reused.
- Interactive user-directed commits use the user's verified Git identity. Follow the repository's current attribution rules; do not substitute an automation identity for manual assisted work.
- Resolve routine implementation choices autonomously. Escalate substantive scope changes or unavailable access rather than asking the owner to make every extraction or test choice.

## Deliverables

1. A small isolated implementation with reusable adapters and one coherent operation model where supported by the experiments.
2. Checked-in fixture sources and stable, runnable end-to-end scenarios with independent expected results.
3. Exact setup, execution, rerun and cleanup commands, including dependencies and selected versions.
4. A machine-readable result manifest and a concise evidence report covering passes, failures, gaps and limitations.
5. A short design decision log: what was reused, what changed, what assumptions failed, and which abstractions proved necessary.
6. A recommendation: continue with the proposed boundary, revise it, adopt an existing mechanism, or stop a particular path. Keep unfinished parts of the owner's objective visible.

The PoC has succeeded as an experiment when it provides reproducible answers to its questions and leaves useful contract tests. A positive product recommendation additionally needs demonstrated interchangeability, real capability use, and an honest account of agent-delivery coverage.
