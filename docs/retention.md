# Registry retention planning

`scripts/retention.py` proposes retention decisions without changing GHCR,
GitHub Releases, source records, tags, or local Docker state. There is no apply
command. A proposed removal is a reviewable eligibility result, not deletion
authorization. Historical release records and public evidence remain durable.

The planner reads an explicitly scoped registry snapshot, the validated
`lifecycle/release-groups.json` policy, and exact image release records. Support
dates belong to accepted release groups; `lifecycle/bootstrap-group.json` is a
plan and grants no support or retirement deadline. Initially, ungrouped legacy
records remain protected until a migration deadline is explicitly announced.

```sh
python3 scripts/retention.py registry-inventory.json --format json
python3 scripts/retention.py registry-inventory.json --format markdown
```

A checked-in example demonstrates refusal to remove anything without registry
facts:

```sh
python3 scripts/retention.py tests/fixtures/retention-example.json \
  --now 2026-11-26T08:00:00Z --format markdown
```

The fixture is a dated projection of the 14 latest accepted image records on
2026-10-14. Its exact digests, exact tags, creation timestamps and parent edges
come from those records. It asserts no live registry existence, package-version
IDs, aliases, publication state, referrers, downstream pins, or storage sizes.
`observed_at` preserves the latest recorded anonymous public-pull verification
time; it is not a new registry observation. All completeness flags are false.
The explicit future planning date also makes that evidence stale, and is after
the initial legacy migration deadline and grace. The report can show expired
releases, but its removal set must stay empty. Refresh actual registry evidence
before considering a real cleanup proposal.

`--now` accepts a timezone-qualified timestamp for reproducible inspection.
`--cache-days` defaults to 14 days since observed last usage;
`--closed-branch-days` defaults to two days after observed closure. These bounded
cache settings accept integers from 1 to 365. The earlier cache deadline applies.
A cache with an unknown branch state remains unresolved.

## Decisions and deadlines

| Object | Proposed decision |
| --- | --- |
| Member of any supported accepted group | Keep the exact artifact and its dependencies |
| Member of expired groups | Expire; removal requires every containing group's grace window to finish |
| Same digest selected in a fresh supported group | Keep existing bytes without allocating another image |
| Active publication attempt | Keep, including candidates awaiting verification or catalog acceptance |
| Proven abandoned publication | Seven-day recovery window after the recorded abandonment time |
| Ungrouped legacy release | Keep until the announced migration deadline, followed by policy removal grace |
| Cache | Bounded inactivity/closed-branch window, unless another retained artifact requires it |
| Signature, SBOM, attestation, or related evidence | Follow all observed exact owners; preserve while any owner is retained |
| Unknown owner, deadline, candidate state, or incomplete reference graph | Cannot be proven removable |

The standard policy's removal grace is 14 days. Downstream pins produce warning
or migration notices; they do not extend a published support/removal deadline.
The downstream support gate is responsible for enforcing failure at support
expiry, including locally cached images. Registry removal has a separate grace
window and cannot enforce local-cache use.

Every retained manifest protects its transitively referenced manifests, parents,
and assurance objects. The release ledger and validated accepted group members
supply exact parent and platform edges even if the snapshot adapter omitted
them. Group members preserve these edges for checksum-bound historical retired
records as well. Referrer relationships must
also be recorded: an owner depends on its evidence for retention purposes.
Evidence `owners` supplies that relationship and permits evidence to expire with
its owners. Evidence without proven owners remains protected as an unknown.

## Inventory snapshot contract

Acquisition and planning are separate. A connected read adapter or a local
read-only `gh api`/OCI registry adapter can prepare the input. This first rollout
accepts JSON snapshots; it does not implement credentials, network reads, or a
registry writer. Package-version API listings alone cannot prove manifests,
referrers, publication states, branch state, or shared-blob references complete.
API rate limits, failed pages, missing credentials, or an adapter limited to tags
must be represented as incomplete facts rather than empty successful results.

The input fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `observed_at` | Timezone-qualified observation time; future observations fail |
| `scope.repository` | Exactly `xormania/xorder` |
| `scope.packages` | Explicit distinct `ghcr.io/xormania/...` package repositories; do not inventory unrelated packages implicitly |
| `versions_complete` | Every package-version page in the declared scope was read successfully |
| `references_complete` | Complete manifest/platform/parent/referrer relationships for scoped objects were observed |
| `publications_complete` | All publication attempts, including drafts and awaiting acceptance, were accounted for |
| `items` | One object per package and digest; consolidate aliases and duplicate package-version IDs under it |
| `publications` | Explicit active and abandoned attempt facts |
| `pins` | Optional known downstream consumers and their exact identities |
| `blobs` | Optional unique blob facts with independently complete cross-manifest references |

Each item requires `identity` (`ghcr.io/xormania/PACKAGE@sha256:...`), `kind`
(`image`, `candidate`, `cache`, `evidence`, or `unknown`), `created_at`, distinct
`tags`, distinct positive integer `version_ids`, exact `dependencies`, and
`references_complete`. A platform manifest can have an empty tag list or empty
package-version list while still being part of the reference graph. A cache also
requires `last_used_at` and `branch.state` (`open`, `closed`, `unknown`); closed
branches require `branch.closed_at`. An evidence item can declare exact `owners`
which must be observed image/candidate/cache roots, not chains of evidence.

An attempt requires a distinct `id`, `state` (`active` or `abandoned`), and a
nonempty `identities` list. An abandoned attempt requires its observed `ended_at`.
An old candidate tag alone is not evidence that publication was abandoned.
If an abandoned attempt shares an expired release digest, the later of its
seven-day recovery deadline and the release's removal deadline applies.

A pin is `{ "consumer": "xormania/uxor", "identity": "ghcr.io/...@sha256:..." }`.
A blob has `digest`, nonnegative `size_bytes`, exact nonempty `references`, and
`references_complete`. Blob references must account for all manifests that keep
those bytes, including relevant references beyond the scoped packages. Do not
claim completeness from one image's layer list.

For example, this deliberately incomplete snapshot describes one candidate:

```json
{
  "schema_version": 1,
  "observed_at": "2026-10-14T08:00:00Z",
  "scope": {
    "repository": "xormania/xorder",
    "packages": ["ghcr.io/xormania/php-dev"]
  },
  "versions_complete": false,
  "references_complete": false,
  "publications_complete": false,
  "items": [{
    "identity": "ghcr.io/xormania/php-dev@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "kind": "candidate",
    "created_at": "2026-10-01T00:00:00Z",
    "tags": ["example-candidate"],
    "version_ids": [123],
    "dependencies": [],
    "references_complete": false
  }],
  "publications": [],
  "pins": [],
  "blobs": []
}
```

The repeated `a` digest is an illustration, not a released artifact. The input
above cannot produce a removal proposal. Missing protected releases/parents in
the declared package scope produce explicit unresolved facts.

## Reports and storage estimates

JSON output contains `sets.keep`, `sets.expire`, and `sets.removal`, each with
exact identities, package-version IDs, tags, deadlines, and reasons. It also
contains consumer migration notices and unresolved facts. Markdown renders the
same decisions for review. Tags are reported as references, never counted as
separate images; object counts use distinct package/digest pairs.

Stale inventories, incomplete version/publication/reference facts, or missing
in-scope dependencies block all removal proposals. The observation age limit is
the policy's `max_policy_age_hours` (initially 24 hours). Unknown objects remain
protected with their missing ownership/deadline fact explained. This conservative
dry run makes missing evidence actionable without pretending it is a lifecycle
decision.

`reclaim.known_exclusive_blob_bytes` sums each known unique blob once, and only
when its complete observed reference set is wholly within the proposed removal
set. Shared layers stay out of that estimate. `total_reclaimable_bytes` remains
null: compressed image sizes do not prove incremental storage, and registry
garbage collection/billing reclamation is not observed. Image size measurements
are never summed as guaranteed savings.
