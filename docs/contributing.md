# Maintaining and expanding xorder

Use feature branches and PRs against master. The canonical source layout is:

| Path | Responsibility |
| --- | --- |
| `images/*/definition.json` | Authored intent, runtime/OS lines, revisions, capabilities, limitations and changes |
| `images/*/Dockerfile` | Build recipe |
| `images/shared/` | Shared tools and workspace/user handling |
| `images/tools.json` | Resolved Composer/uv digests, PECL versions and verified Symfony CLI artifact |
| `release-records/<family>/<line>/<revision>.json` | Published, behavior-tested release facts; created by publication |
| `retired-records/*.json` | Explicit removal declarations bound to exact historical record bytes and original source commits |
| `artifacts/<kind>/<name>/definition.json` | Authored binary, environment, configuration, or context contract |
| `artifacts/<kind>/<name>/payload/` | Explicit bundle inputs and upstream notices |
| `release-records/artifacts/<kind>/<name>/<revision>.json` | Verified downloadable artifact facts; created by publication |
| `profiles/` | Explicit role choices and exact resource revisions |
| `schemas/` | Definition/release/catalog structure; cross-field invariants live in the validator |
| `discovery/organization.json` | Authored applicability, layers and direct profile navigation; no artifact facts |
| `catalog.json`, `catalog-v2.json`, `discovery.json`, README tables, `docs/capabilities.md`, `docs/images/`, `docs/resources/index.md`, `docs/releases/` | Generated outputs |
| `scripts/` | Small build, inventory, release, generation and refresh helpers |
| `scripts/xorder/` | Shared typed model, resolution, transport, application, and artifact release helpers |
| `tests/fixtures/`, `tests/requirements/` | Locked real consumer fixtures and independent mock requirements |

The image paths remain stable. [Architecture](architecture.md) describes the
extension boundaries for binaries, environments, configuration, context, and
profiles. Add a new path with its first meaningful definition or implementation;
do not create empty category directories or list an unverified resource as
available. Keep one normalized resource model and generate any compatibility
views from it. Existing image selection inputs and outputs are compatibility
contracts while generic discovery is introduced.

Local metadata validation:

```sh
python3 -m pip install -r requirements-ci.txt
python3 scripts/library.py generate
python3 scripts/library.py check
python3 -m unittest discover -s tests -v
```

## Commit and pull request attribution

Use an accountable person's Git identity or the repository's existing neutral
automation identity. Do not attribute a commit or pull request to Claude,
Codex, Grok, Anthropic, OpenAI, or xAI: omit their author/committer identities,
attribution trailers, generated-with signatures, and model session links. This
is a metadata policy, not a ban on using or discussing development tools;
ordinary technical references to those tools and providers remain allowed.
Dependabot and the repository's `xorder automation` and `image-library
automation` identities are also allowed.

Validation checks the full history reachable from a proposed head plus the pull
request title and body. A branch based on superseded history must be rebased;
there is no grandfathered range for prohibited attribution.

The `Attribution Policy` workflow runs the default branch's trusted checker and
publishes an `attribution-policy` check on the proposed head. It queries each
proposed commit's author, committer, message, and parent metadata through
GitHub's authenticated Git commits API, stopping at the fully audited local
default-branch history. No proposed objects enter the local Git database, and
the workflow never downloads proposed trees or blobs or checks out or executes
proposed code.
Repository administrators must keep that context required by the master ruleset
after its first successful run, and explicitly allow this workflow's
`pull_request_target` event in the repository Actions execution policy.

The shared `.claude/settings.json` suppresses Claude Code's default commit and
pull-request footer for the normal project configuration. It is a convenience,
not an enforcement boundary: higher-precedence local, command-line, or managed
settings can override it. The history audit remains the repository policy gate.

For a downloadable resource, pin an exact upstream URL and SHA-256 or declare
every authored payload file. Set its prerequisites, owned destination paths,
limitations, usage page, and behavior verifier in the definition. Allocate a new
SemVer packaging revision for changed input bytes, executable modes, destination
paths, or verification behavior. Fingerprints normalize payload modes to `0644`
or `0755`; executable intent is part of the release input.

Run its actual packaging and readiness check before opening the PR:

```sh
PYTHONPATH=scripts python3 -m xorder.verify verify KIND/NAME
```

Publication checks the anonymous released bytes again before proposing a durable
release record. Review and merge that record through normal metadata checks;
only then does generation expose the resource as available. Definitions and
profile pins alone cannot make a release selectable. Update a native environment's
committed lock through its backend and verify that readiness leaves it unchanged.
Keep profile updates explicit: adding a newer accepted resource does not upgrade
an existing profile, resolution lock, or managed installation.

On a Docker-capable host, use `scripts/build.py LINE_ID LOCAL_TAG` and
`scripts/verify-image.sh LINE_ID IMAGE`. Derived build input must be the exact
matching parent artifact; PR tests reuse an available matching digest or use the
just-built local parent. Publication
uses its immutable registry digest. Image builds collect measured versions,
packages, runtime and extensions using `scripts/inventory.py`.

Before editing a released recipe/input, allocate the appropriate image revision
and write meaningful `changes` plus migration guidance in the line definition.
Do not hand-edit measured tool versions in generated docs. A global shared tool
refresh intentionally changes all consumers; image-specific changes stay scoped.
README/docs/record-only PRs do not rebuild images. The release jobs additionally
skip source-identical lines already in the accepted ledger.

Validation scopes container jobs to changed recipes and consuming fixtures;
release orchestration and unit-test changes still run metadata tests. Unknown
build/verification helpers conservatively select all images. Publication also
checks the accepted ledger before allocating runners, retaining incomplete PHP
parent/browser pairs and changed-input guards.

PR image selection keeps exact behavior targets within each shared parent build
tree. Recipe, copied-input, tool-pin, and definition changes test their consumers
and descendants. A change confined to one definition line tests only that line
and its descendants; a change to the family's common definition tests every line.
Fixture and runner changes test only the images that execute them. Ancestors
provide exact build inputs without repeating their own behavior checks, and
unaffected sibling branches are skipped. Matching available parent artifacts are
pulled by digest; missing or changed parents are built before the selected child.

Independent fixture changes also select their own checks on an unchanged,
accepted image:

| Changed input | Selected checks |
| --- | --- |
| `tests/fixtures/trust/` | CA trust checks on each family that runs them |
| `tests/fixtures/native-check.c` | Native compilation on the PHP, Python and Rust families that run it |
| Image recipe, copied input, tool pin, definition or unknown runtime helper | Full readiness for every affected image and descendant |

Multiple fixture changes combine their checks. Full readiness takes precedence
when another changed input requires it. A target without an exact matching
accepted artifact builds and runs full readiness even when the requested checks
were narrower. The public readiness command and publication retain full
verification by default. Partial checks record their actual suites in PR metrics
and do not establish full readiness or publication evidence.

Catalog and known schema-only changes run metadata validation. Shared image
orchestration changes, including `validate.yml`, and unknown runtime helpers
still exercise all images because their impact spans the validation path.
Catalog and policy validation run on every PR. Unit and syntax checks run for
every new source head. `checks` accepts intentionally skipped runtime jobs while
failing on failed or cancelled required jobs.

Inspect selection without building:

```sh
python3 scripts/library.py validation-matrix --base BASE_COMMIT
python3 scripts/library.py validation-matrix --all
```

The matrix records each parent tree, its `verify_lines`, and the requested
`verify_suites` for each target, also shown in the workflow summary. The existing
`affected` root-list interface remains available.
For a toolkit-only local check:

```sh
python3 scripts/build.py php-dev/8.5-trixie image-library-check:dev \
  --children --reuse-accepted --verify-lines '["php-toolkit/8.5-trixie"]'
```

Manual `Validate` runs and the weekly Tuesday 06:23 UTC schedule exercise every
image, resource, environment, and application surface. Unchanged available
images are still reused for runtime checks; these runs do not publish images.

After a successful validation of the same PR and unchanged tested base, image,
resource and application selection reuse that validated coverage. Each run
retains a `validation-context` artifact binding its run, source head, actual
checkout parents and tree. The checked-out merge supplies the tested base;
historical API PR metadata and the event's base SHA are not proof of that base.
Incremental updates
compare source heads when the successful ancestral head already contains the
base. A source head behind the base can reuse an identical successful head;
later source updates conservatively check the full PR delta. Failed runs,
changed bases, unrelated force-pushes, unavailable history and missing or expired
context evidence also fall back to the full PR delta. An unrecognized checkout
runs every runtime check. This preserves changes introduced by the tested merge.

Title/body edits queue behind active validation instead of cancelling it. Once
the same source head, tested base and checkout tree have passed, the queued run
retains catalog/policy checks and reuses the completed unit, syntax and runtime
results. A changed
target branch still cancels obsolete work and requires selection against the
new base. A failed or cancelled run cannot supply reusable coverage.

New revisions use version-2 fingerprints of their Dockerfile, its local COPY
inputs, executable modes, `.dockerignore`, and consumed tool pins. PHP-only
shared files do not change Rust or Python fingerprints. Derived fingerprints
also bind the exact accepted parent digest. Historical release records retain
their original algorithm and evidence; migration belongs to fresh revisions.
Tool-file changes select only consumers of the keys that actually changed.
Validation pulls an unchanged available accepted digest and runs selected behavior
without building it. Missing or changed artifacts still build and verify normally. The optional
`--cache-probe` checks source-label layer reuse when explicitly requested.

Build caches use family-specific input fingerprints rather than commit SHAs.
Source labels are applied after install layers. Observed Debian package-index
checksums form `APT_REFRESH`, invalidating package-install layers only when
those actual upstream inputs change. PHP CI uses Docker's containerd image store so its exact local
parent remains visible while both parent and browser caches can be exported.
Build artifacts and job summaries retain image size and build/verification
times. A source-label-only rebuild checks that filesystem layers stay identical.

Fresh image revisions record `https://github.com/xormania/xorder` in their OCI
source labels; historical artifacts retain their original provenance. Changing a
label changes the input fingerprint even when filesystem layers are unchanged:
allocate new revisions for the affected lines and derived consumers and run
normal build/publication verification. Never rebuild an accepted exact revision
or rewrite historical release evidence to disguise a provenance change.

PR build metrics describe validation artifacts; they are not published release
facts. Measured release facts belong in verified `release-records/`, and their
documentation is generated from that ledger in the image/release pages and
[release measurements](metrics.md). Publication records local image size,
measurement method/store, timestamps, evidence, and public-artifact verification
time. Fresh builds also record build time and external cache input; resumed
artifacts have no invented build time.

Size comparisons use the preceding available accepted revision. Publication
reuses its recorded size when the method/store match, or anonymously pulls its
digest and measures it in the current store. This supports older records without
metrics without rewriting their durable release assets. A comparison appears
only when that accepted baseline is present; missing measurements stay absent.
Rebuild timings depend on cache state and runner/network conditions; compare
equivalent inputs rather than treating one run as a guaranteed duration.

`Refresh build inputs` runs weekly and manually. It resolves upstream digests,
PECL versions and the Symfony/Infection artifact checksums, then stages fresh
patch revisions only for changed consumers and their descendants. It tracks
Debian main amd64 package-index checksums for Trixie, updates and security;
changed package feeds trigger the apt consumers. Release dates and signatures
alone do not allocate rebuilds. Identical resolved inputs create no refresh PR.
These checksums observe repository changes; Debian packages remain measured
from the resulting artifact rather than claimed to come from a frozen snapshot.
Review upstream compatibility/security changes and adjust
the revision when a patch refresh would break the contract. Never reuse an exact
release for a fresh build. Dependabot proposes Actions/validation dependency
updates separately.

Fixtures have committed Composer, uv and Cargo locks. Updating a fixture lock
is a source change and reruns behavior, rather than substituting the fixture's
dependency versions for the consuming project's own lock. No global PHPUnit,
Panther, CUE or speculative Cargo tools are bundled.

Browser parity also pins the accepted application-image digest alongside its
consumer commit. Publication stages a candidate without executing consumer
code. A separate job with no repository permissions, persisted checkout
credentials, or registry login verifies that public digest. Its Compose
configuration belongs to xorder, ignores consumer Compose/dotenv files, and
rejects bind paths escaping the disposable checkout. The runner receives an
explicit minimal environment. Finalization requires successful evidence bound
to the exact digest, source, image inputs and parity fixture; it does not rerun
consumer code with publication credentials.

To add a family/line, inspect the target project's requirements, choose an
official upstream base and resolve its digest, define its intended profile,
extend the build/inventory/behavior recipes, add independent selection scenarios,
and keep it unavailable until the shared publication path produces a verified
record. Extend platform schema/build/tests together before adding arm64.
Keep discovery usable from the repository URL without a pipeline service, MCP
server, or installed discovery skill. A selected context resource may contain a
skill; that payload is independent of the discovery entry point. Reuse common
release evidence and orchestration, with kind-specific build/verification and
application behavior. Configuration/context changes must not rebuild unrelated
images.

Pins make build inputs traceable; apt repositories and project download
services still change. Byte-for-byte reproducible rebuilds are not claimed.
