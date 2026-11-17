# Xorder responsibility boundary

Xorder builds, verifies, publishes, describes and maintains container images.
The consuming project selects an image and operates its project with it.
This boundary guides new work and the staged separation of responsibilities
already implemented in this repository.

The repository currently includes project runners, native environment preparation
and independently published non-image resources. They remain working
compatibility surfaces until their reviewed migrations are complete. Declaring
the boundary does not remove those interfaces or establish that a transfer has
happened.

## Ownership

| Responsibility | Xorder owns | Consumer or separately selected owner owns |
| --- | --- | --- |
| Image contents | Recipes, runtime/tool pins, extensions, packaged dependencies and templates | Application dependency declarations and locks |
| Build and distribution | Component reuse, verified download caches, build caches, registry publication and exact identities | Selection of compatible image pins |
| Container operation | Startup, UID/GID, workspace/HOME mounts, trust, proxy handling and image-owned cache interfaces | Application preparation, service topology, data and application caches |
| Verification | Small disposable subjects proving advertised image capabilities | Application tests, snapshots, project scanners and validation policy |
| Lifecycle | Inventories, provenance, assurance, support groups, retirement policy and reusable identity/support checking | Integrating the required checks and adopting supported image releases |
| Native environments | Requirements for any supplied image | Native Python/uv, Nix/devenv and host service preparation |
| Non-image delivery | Tools or prepared payloads packaged as image contents | Independent binaries, configuration/context bundles and target-file installation |

Consumer lockfiles can inform capability requests, image version demand and
compatibility diagnostics. An automated consumer version notification is a valid
input. Consumer internal scripts, expected application test counts and current
application behavior should not define Xorder's image acceptance contract.

A project-specific image such as `uxor-dev` remains an image product. Mago,
Serena, Symfony tools, harnesses and prepared dependencies can remain image
contents. Size or implementation complexity alone does not make a payload
outside scope. When a separately owned tool is packaged, Xorder owns the pinned
packaging and image compatibility; its project policy and lifecycle stay with
the owning project.

## Image acceptance

Image checks must exercise real advertised behavior. A version command alone
does not prove a compiler, browser, database client, terminal or language server
works. Appropriate owned subjects include:

- A small locked PHP or Python project that uses the supplied tooling.
- HTTP requests, including repeated requests when worker behavior is advertised.
- A fixed page with browser interaction, rendering, fonts and screenshots across
  each advertised engine.
- Native compilation, SQLite/WAL operations and terminal communication using
  private tmux sockets, PTYs or Unix sockets when advertised.
- Valid and deliberately invalid inputs to packaged validators, plus offline
  reuse and integrity checks for prepared payloads.

The same image contract applies to PR validation, public readiness and
publication. Replace an imported application suite with the relevant owned
capability checks before removing it. Updating only one gate leaves the
responsibility entangled elsewhere.

The consumer qualifies its application revision and snapshots against its
chosen digest in its own validation. A downstream compatibility result can be
useful evidence without becoming an Xorder image release requirement.

## Existing responsibilities to separate

These paths identify current implementations, not completed moves or newly
assigned external repositories:

| Current area | Xorder responsibility to retain | Responsibility to transfer |
| --- | --- | --- |
| `tests/fixtures/uxor/`, browser parity and publication | PHP/Node/Tailwind/server behavior; browser engines, rendering and font behavior | UXor application regression tests and snapshot qualification |
| `examples/uxor/`, `scripts/xr.py` and project testing helpers | Concise image launch examples and generic container interfaces | Dependency preparation, project services, mutations, test receipts and project cleanup |
| `examples/xorchestrate/` and native acceptance | Any separately specified image capabilities and image-bound evidence | Consumer lock installation, managed profiles, doctor/scanner policy and native readiness |
| Python matrix and harness fixtures | Interpreter/venv/pip/SQLite and terminal capabilities; packaged harness operation and provenance | Xordination contract census, doctor imports and consumer terminal helpers |
| Toolkit fixture | Packaged payload integrity, clean extraction and valid/invalid validator inputs | UXor kit and recipe correctness |
| `artifacts/`, general profiles and target-file application | Shared downloads, transport or model code actually used by images | Independent non-image products, general composition, installation, recovery and rollback |
| Packaged project helpers | Transparent tool invocation and image adaptations | Application scaffolding, preparation and project validation policy |

The native Xorchestrate runner prepares a host environment; it does not currently
select or verify an Xorder image. Its results must be described as native
readiness. Any future image claim needs evidence tied to the actual digest,
platform, installed interpreter and linked SQLite, mounts and runtime UID.

Image support policy, identity checks and published deadlines remain in force.
Transferring a runner also transfers its application-specific invocation of
the existing required support checks. This work does not make enforcement
optional or reset support history.

## Migration sequence

1. Establish ownership in the README, architecture and contributor instructions.
   Keep current compatibility behavior visible and stop adding non-image product
   lines or project lifecycle responsibilities.
2. Replace consumer application gates with owned image capability subjects.
   Review PR selection, public readiness and publication together, retaining
   exact artifact binding and credential isolation.
3. Transfer project runners and native preparation to their receiving project
   or an owner selected for that capability. Supply the receiving integration,
   documentation and entry-point migration before removing existing paths.
   Preserve project state, receipts and recovery behavior during handoff.
4. Separate non-image products and target-file application from image discovery,
   validation and publication. First untangle shared model and generation
   dependencies; preserve existing catalog output compatibility until a reviewed
   transition supplies its replacement.
5. Remove transferred code and redundant workflow wiring after callers have
   migrated. Review remaining project-aware helpers individually. Dependency
   grouping or polling frequency can be optimized separately from ownership.

Each change should state what has moved, what still runs and how it was
verified. Dedicated draft PRs can land independently when their changed
interfaces and compatibility behavior are explicit; this document does not
choose a new repository for each capability.

## Compatibility during transfer

Keep exact published tags, digests, original source identities, inventories and
release evidence intact. Existing release and retention procedures still govern
withdrawal or removal. A new ownership boundary does not rewrite historical
publication facts.

Changes to packaged bytes or image interfaces follow the existing
[versioning contract](versioning.md). Breaking advertised capabilities,
executable paths or startup behavior requires the appropriate major revision
and migration guidance; compatible changes follow normal minor/patch rules.
Fixture-only verification changes do not justify allocating duplicate image
bytes.

Do not delete directories by label. In particular, `scripts/xorder/` contains
download, transport and support helpers that image builds use or copy into
components. Preserve those dependencies while separating general resource
application. The generated image and broader compatibility views must continue
to derive from their validated ledger until their separation is implemented.

The existing [architecture](architecture.md), [release contract](versioning.md),
[release groups](release-groups.md) and [downstream support
check](downstream-support.md) describe the interfaces and lifecycle obligations
that remain applicable throughout this migration.
