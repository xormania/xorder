# xorder architecture and discovery

xorder builds, verifies, publishes and maintains prepared container images.
The public repository URL is the discovery entry point:
[README](../README.md) → image catalog or usage page → direct usage and
readiness instructions. GitHub rendering and raw files carry the same information.
An installed CLI, skill, plugin, or separate discovery service is unnecessary.

## Image supply and consumer ownership

Xorder owns image recipes, packaged tools, component reuse, download/build
caches, container startup and advertised capabilities. It publishes exact
identities with measured inventories, verification, provenance, assurance and
support information. Consumers select those identities and own their application
dependencies, service configuration, state, native environments and tests.

Small Xorder-owned subjects prove image behavior: compiling source, performing a
database round trip, serving HTTP, interacting with a browser or exchanging data
through tmux. Consumer application suites and snapshots belong in the consumer's
validation. A named project image can still be an Xorder product; its name does
not make Xorder responsible for operating that project.

Tools can include substantial prepared dependencies or templates. A tool owned
elsewhere may be packaged at an exact version; Xorder then owns its image
packaging and advertised operation. Application policy and lifecycle remain
with the tool or consumer owner. Image support policy and its authorized
enforcement remain in force as integration ownership changes.

[Responsibility boundaries](responsibility-boundary.md) maps the existing code
to this scope and describes the transfer sequence. The sections below document
the current implementation, including compatibility surfaces awaiting transfer.

## Existing discovery and compatibility surfaces

The compact [current index](../discovery.json) and
[capability guide](capabilities.md) list the newest available verified releases.
The typed [catalog](../catalog-v2.json) retains every accepted release. The
detailed [image view](../catalog.json), existing image definitions, records,
commands, GHCR references, and usage remain available. The earlier broader
resource implementation also exposes the following kinds:

| Kind | Current implementation |
| --- | --- |
| Image | OCI identity, platform inventory, toolchain and container behavior |
| Binary | Downloaded bytes, upstream version, checksum, dependencies and invocation |
| Environment | Native backend files, locked inputs, tools/services and activation |
| Configuration | Application/version scope, destination files and update behavior |
| Context | Audience, task/harness scope, source and selected guidance payload |

A profile composes resources for an explicit target; it is not another software
payload. Existing products include Composer, whose PHAR requires PHP, and a
devenv PHP/Symfony environment. Devenv retains responsibility for native package
resolution and process lifecycle. Their definitions alone never establish
availability; verified release evidence does.

Independent binary, native environment, configuration and context products,
general resource composition and target-file application are outside Xorder's
image scope. Their current code, releases and interfaces remain during transfer.
Do not add new non-image products or treat the existing kind model as an
expansion plan. No removal or completed transfer is implied by this boundary.

## Separate intent, evidence, selection, and target state

| Concept | Responsibility |
| --- | --- |
| Definition | Authored identity, purpose, capabilities, prerequisites and recipe |
| Release record | Exact content, source identity, measured facts and verification evidence |
| Catalog | Compact generated view of eligible releases with direct usage links |
| Profile | Resource selection, requirements, alternatives and target assignments |
| Resolution lock | Exact releases and target assumptions chosen before applying |
| Installation receipt | Owned target files, hashes and activation/recovery state |

The existing profile and application system assigns reusable material
selectively. Public profiles contain examples; private machine inventories and
user-specific values can be supplied separately. Catalog discovery never
activates every context bundle, and delivering an instruction file does not
establish that a model followed it. Current user direction remains authoritative.

The current common model validates kind-specific fields. An OCI digest,
HTTP checksum, native environment lock and installation receipt have different
roles. Preserve them rather than pretending all resources install alike.

## One model, generated compatibility views

Image definitions live in `images/`, with measured release evidence in
`release-records/`. Keep those paths and historical facts intact. Existing
non-image definitions live under `artifacts/<kind>/<name>/`; compositions live
in `profiles/`. These definitions are authored intent and need verified release
records before selection can offer them. They remain compatibility inputs
pending transfer rather than locations for new product lines.

The generator normalizes image data and existing resources into one shared
model. It produces the schema-1 `catalog.json` image view and the typed
[catalog-v2.json](../catalog-v2.json) compatibility view. The small
`discovery.json` and `docs/capabilities.md` are generated current-release views.
Their navigation belongs in `discovery/organization.json`, separate from released
input definitions; grouping cannot change artifact bytes, identity or availability.
All views share the validated release ledger and cannot be edited independently. Existing
`scripts/library.py` image commands retain their selection behavior and schema-1
outputs. Shared resource validation and resolution live in `scripts/xorder/`.
The generated [resource index](resources/index.md) contains current non-image
availability, prerequisites, and direct usage/evidence links.

Detailed inventories remain linked evidence; discovery should not require
loading every OS package or context payload. Only tested, publicly retrievable
releases become available. Target checks distinguish unsupported variants,
missing prerequisites, unavailable downloads and untested execution surfaces.

## Read-only profile resolution

The optional `scripts/xorder_cli.py` helper requires Python 3 and the dependencies
in `requirements-ci.txt`. `list` and `show ID` expose accepted resource releases
with their existing output shape. `list --latest --summary` is bounded to one newest eligible release
per ID with exact pins and usage links; `show ID --version REVISION` selects one
explicit historical release. `doctor --workspace PATH --resource ID` inspects
command presence, disk space, lockfile presence and Docker availability with fixed
read-only probes. Each Docker probe has a three-second deadline by default,
configurable up to ten seconds, followed by at most one second of process cleanup.
POSIX probes run in a private process group; timeout and normal completion both
terminate remaining wrapper/plugin children and reap the direct process. Non-POSIX
Docker probes report `unsupported_platform` without starting commands. No packages
or services are installed or started. Engine platform and host platform remain distinct. Output does not establish
network access, scope, harness, or application readiness.
`resolve PROFILE --target TARGET` reads local JSON files and prints a lock; it
does not install resources or activate instructions. `generate` and `check` use
the same generated outputs as the existing image metadata commands.

A minimal profile for a currently available image is:

```json
{
  "schema_version": 2,
  "id": "profile/php-project",
  "revision": "1.0.0",
  "purpose": "PHP project using the verified image toolchain",
  "roles": [
    {
      "name": "runtime",
      "alternatives": [{"id": "image/php-dev/8.5-trixie", "version": "1.1.0"}]
    }
  ]
}
```

The target is explicit observed state, for example:

```json
{
  "platform": "linux/amd64",
  "commands": ["docker"],
  "scope": "project",
  "harness": "codex"
}
```

Check that the declared Docker command has a working engine; command presence
alone does not establish readiness. Resource usage checks establish runtime
behavior. Missing target facts are reported separately from known mismatches.
Only `available`, verified compatible records can resolve; multiple compatible
resource alternatives require an explicit choice. Dependencies, version conflicts,
cycles, and overlapping file destinations are checked before returning a lock.

For context, `details.audience` is one exact harness identifier or a nonempty
list of identifiers, such as `codex` or `["codex", "claude"]`. The explicit value
`any` permits every harness. Other descriptive labels do not imply universal
eligibility. A concrete audience requires the observed `target.harness` and must
match it, even in a custom profile or private overlay without a role condition.
Scope and audience are checked again when validating the lock before application.

`--pins previous-lock.json` retains exact existing identities. An upgrade requires
deliberately changing or omitting those pins. `--overlay private-overlay.json`
accepts local overrides keyed by existing role name and explicit target overrides:

```json
{
  "roles": {
    "runtime": {
      "alternatives": [{"id": "image/php-dev/8.4-trixie", "version": "1.1.0"}]
    }
  },
  "target": {"harness": "claude"}
}
```

The lock records profile and overlay source hashes, observed target facts, selected
roles, and exact artifact identities. It is a local decision record; it does not
replace native lockfiles, release evidence, or target installation receipts.
Private overlay files are not inputs to public catalog generation.

## Delivery and application

Keep current image package names in GHCR. The existing non-image implementation
uses GitHub Releases for downloadable artifacts and bundles; those published
identities and evidence remain intact during transfer.

The existing application helper resolves exact selected resources, stages and
verifies bytes, materializes selected scopes, tracks owned files, and preserves
locally edited or unrelated destinations. Native backends own their services.
This target-file lifecycle is a compatibility surface awaiting transfer.
The [application guide](application.md) describes the implemented helper's target
locks, receipts, repeated application, conflicts, recovery, rollback, and explicit
removal. Runtime readiness checks remain separate from file receipt verification.

## Repository rename and image provenance

The canonical URL is https://github.com/xormania/xorder. Current navigation uses
that identity; historical source/run links can retain their original provenance.
GHCR family names and exact references do not change with the repository name.

Fresh image revisions label this canonical source URL. Historical exact artifacts
retain their original source labels and release evidence. Label bytes participate
in image fingerprints, so changing provenance requires fresh affected revisions
and normal publication; see [versioning](versioning.md).
