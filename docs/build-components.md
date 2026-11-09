# Prepared build components

Internal components prepare expensive toolchains, compatible runtime foundations
and pinned tool payloads independently. Existing public image families remain the
supported consumer interface. `images/components/*/definition.json` supplies the
Dockerfile/target, platform, ABI, explicit arguments, pinned tool inputs and other
component dependencies. Image lines select donor arguments with `build_components`.

A component key binds its actual Dockerfile and COPY inputs, executable modes,
platform, ABI, target, resolved arguments and transitive component keys. Descriptive
purpose and current verification commands do not allocate another artifact.
Unknown arguments, mutable external image donors and dependency cycles fail
before building. Verification runs when an existing donor is loaded as well as
when a new donor is built.

Build-input inspection supports full-line comments and default backslash line
continuations with LF or CRLF physical lines. Other line separators are rejected;
an initial UTF-8 BOM is accepted without changing the hashed source bytes.
Here-document markers (`<<`, including quoted literal forms) and
nondefault `escape` directives are conservatively rejected before instruction
inspection. Copy an authored script into the build instead of embedding a heredoc;
this keeps script bytes in the component's tracked input closure.

The existing publication workflow calls a singleton prepared-input publisher on
real trusted master push events. Each completed target is verified and published
immediately by content key into the repository-derived GHCR cache package. Later
consumer failures retain those outputs. Independently scoped `mode=max` BuildKit
cache exports use the existing event/trust planner; PRs, schedules and local builds
import only. Every final image line also has its own platform-scoped registry cache,
including the independently maintained FrankenPHP and UXor lines.

Source PRs import an available exact donor or build it from their own authored
inputs. A changed unpublished component can build in more than one source matrix
job; cross-job sharing is established after its trusted publication. Within a
process it is prepared once. Completed per-component and per-image local exports
also live in the existing Actions directory cache. Generation keys with input and
line restore prefixes preserve partial completed trees without sealing an
incomplete immutable cache key forever.

Repository pull-request image jobs can read private prepared components without
making the cache package public. Only a PR whose head repository matches the
current repository logs in to GHCR with a job token restricted to `packages: read`.
The build step explicitly enables `XORDER_COMPONENTS_READ_AUTH=1`; component
resolution checks the real PR event and requests a pull-only registry token.
The resolver's `GH_TOKEN` binding is limited to that build step, and the login
action removes its Docker credentials during job cleanup. Publishers retain
their existing pull/push scope.

Local builds, fork PRs, and runs without the explicit read opt-in keep anonymous
resolution and authored-input fallback. They do not receive the read token or
registry export permission. An unavailable optional cache still permits a source
build. Prepared-input memoization distinguishes these authentication modes, so a
previous anonymous local result cannot hide an available private donor.

New final-image release records retain the exact component digest references.
Candidate image labels carry those facts so interrupted publication reads actual
candidate provenance. `resolved_base` retains the authored upstream/runtime-parent
input; `build_components` records direct prepared donors, including an actual
component used as `FROM`. Historical records remain unchanged. Component receipt
`request_source_commit` identifies the consumer request and makes no claim about
an earlier donor's original compilation source.

Prepared `component-*` tags are retained by the dry-run retention planner and
release records add dependency edges. Disposable scoped BuildKit cache tags keep
their existing inactivity/branch rules. No prepared-artifact deletion is introduced.

Run `python scripts/components.py check` to check the graph, or
`python scripts/components.py plan --base COMMIT` to inspect selected targets.
Publication requires the real repository master-push context; local invocations
cannot manufacture a writing trigger. Existing accepted-image reuse and final
behavioral verification remain required.

See [PHP component boundaries](php-build-components.md) and
[verified download reuse](build-downloads.md). UXor and its FrankenPHP parent
recipes and runtime pins retain their separate migration path.
