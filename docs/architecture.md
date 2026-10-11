# xorder architecture and discovery

xorder makes prepared tools, environments, configuration, and context available
to computers and containers. The public repository URL is the discovery entry
point: [README](../README.md) → catalog or resource page → direct usage and
readiness instructions. GitHub rendering and raw files carry the same information.
An installed CLI, skill, plugin, or separate discovery service is unnecessary.

## Current capability and extension boundaries

The compact [current index](../discovery.json) and
[capability guide](capabilities.md) list the newest available verified releases.
The typed [catalog](../catalog-v2.json) retains every accepted release. The
detailed [image view](../catalog.json), existing image definitions, records,
commands, GHCR references, and usage remain available. Additional kinds extend
that structure as verified releases enter the ledger:

| Kind | Owns |
| --- | --- |
| Image | OCI identity, platform inventory, toolchain and container behavior |
| Binary | Downloaded bytes, upstream version, checksum, dependencies and invocation |
| Environment | Native backend files, locked inputs, tools/services and activation |
| Configuration | Application/version scope, destination files and update behavior |
| Context | Audience, task/harness scope, source and selected guidance payload |

A profile composes resources for an explicit target; it is not another software
payload. The authored first examples include Composer, whose PHAR requires PHP,
and a devenv PHP/Symfony environment. Devenv retains responsibility for native
package resolution and process lifecycle. Neither is available merely because
its definition or usage instructions are present in the source tree.

## Separate intent, evidence, selection, and target state

| Concept | Responsibility |
| --- | --- |
| Definition | Authored identity, purpose, capabilities, prerequisites and recipe |
| Release record | Exact content, source identity, measured facts and verification evidence |
| Catalog | Compact generated view of eligible releases with direct usage links |
| Profile | Resource selection, requirements, alternatives and target assignments |
| Resolution lock | Exact releases and target assumptions chosen before applying |
| Installation receipt | Owned target files, hashes and activation/recovery state |

Maintain common material once and assign it selectively. This is the useful
fleet pattern: reusable defaults plus explicit assignments. Public profiles
contain reusable examples; private machine inventories and user-specific values
can be supplied separately. Catalog discovery never activates every context
bundle, and delivering an instruction file does not establish that a model
followed it. Current user direction remains authoritative.

Use a small common model with validated kind-specific fields. An OCI digest,
HTTP checksum, native environment lock and installation receipt have different
roles. Preserve them rather than pretending all resources install alike.

## One model, generated compatibility views

Existing image definitions live in `images/`, with measured release evidence in
`release-records/`. Keep those paths and historical facts intact. New resource
definitions belong under `artifacts/<kind>/<name>/`; reusable compositions belong
in `profiles/`. These definitions are authored intent and need verified release
records before selection can offer them.

Normalize image data and new resources into one shared model. Generate the
existing schema-1 `catalog.json` as the image compatibility view and a compact
typed [catalog-v2.json](../catalog-v2.json) for broader discovery. The small
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
configurable up to ten seconds; no packages or services are installed or started.
Engine platform and host platform remain distinct. Output does not establish
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

Keep current image package names in GHCR. Use GitHub Releases initially for
downloadable artifacts and bundles. Locations may gain CDN mirrors later;
content identity remains an exact digest or checksum. Reuse release orchestration
and evidence while each kind owns its build and behavior checks.

Resolve exact selected resources before applying them. Stage and verify bytes,
materialize only selected scopes, track owned files, and preserve locally edited
or unrelated destinations. Native backends own their services. Installing context
or changing configuration is independent of building a toolchain. Optional
helpers use these same operations; direct documented use remains available.
The [application guide](application.md) describes the implemented helper's target
locks, receipts, repeated application, conflicts, recovery, rollback, and explicit
removal. Runtime readiness checks remain separate from file receipt verification.

## Repository rename and image provenance

The canonical URL is https://github.com/xormania/xorder. Current navigation uses
that identity; historical source/run links can retain their original provenance.
GHCR family names and exact references do not change with the repository name.

Dockerfile source labels remain on the old URL until the next deliberate patch
refresh. Their bytes affect image fingerprints, so updating them requires fresh
affected revisions and normal publication. See [contributing](contributing.md)
for that explicit next-refresh item and [versioning](versioning.md) for the
existing exact-release contract.
