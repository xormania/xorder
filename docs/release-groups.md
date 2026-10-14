# Scheduled release groups and bounded support

A release group selects exact, already accepted image artifacts. Its membership
and support dates are separate from image recipes, image revisions and immutable
publication facts. An unchanged image digest can join the next supported group
without building an image or allocating another revision. Release-group files
must not enter an image input fingerprint.

The initial policy in `lifecycle/release-groups.json` proposes:

| Event | Announced rule |
| --- | --- |
| Ordinary group | Monday 06:00 UTC, weekly |
| Support expiry | 28 days after the announced group slot |
| Migration warning | Seven days before support expiry |
| Removal eligibility | Fourteen days after support expiry |
| Current-policy receipt | Fetched within the preceding 24 hours |
| Migration of existing consumers | Adopt a supported group by 2026-11-11 08:00 UTC |

The initial accepted policy includes the migration cohort `bootstrap-2026-10-14`,
announced at 2026-10-14 08:00 UTC. `lifecycle/bootstrap-group.json` retains its
**planned formation proposal**; support authority belongs to its accepted entry
in the policy, rather than that source proposal. Exact image revisions and their
matching parent digests were already accepted before group formation. No artifact
has been deleted and no existing image publication record has been rewritten.
The migration deadline becomes authoritative when the policy is accepted on master;
consumers must install the downstream support check to enforce it. A cached image cannot enforce policy merely by existing on a Docker host.

## Formation and acceptance

The planner reads verified image release records, chooses the latest available
revision per line, and closes the cohort over exact Xorder parent digests. A
parent and its derived images must agree on the same artifact; incompatible
latest revisions fail instead of inventing a compatible image. Explicit line
choices can form a smaller cohort. Parent artifacts join that cohort when missing.
An external upstream image is an input, not an Xorder cohort member.

```sh
python3 scripts/release_groups.py plan --at 2026-10-19T06:00:00Z
python3 scripts/release_groups.py plan --at 2026-10-19T06:00:00Z \
  --selections selected-lines.json
```

`selected-lines.json` is an exact `line_id` to SemVer revision map. Output is a
planned group JSON document. Ordinary dates must fall on the weekly slot. An
immediate security group or the announced migration group uses explicit
`--reason security` or `--reason migration`; this does not bypass image acceptance.

After the member image records have passed publication verification and entered
master, acceptance creates the immutable dates:

```sh
python3 scripts/release_groups.py accept lifecycle/bootstrap-group.json \
  --accepted-at 2026-10-14T08:00:00Z
```

This emits accepted group metadata to stdout and writes nothing. Include that
document in the policy's `groups` list, increment the policy `revision`, and submit
it through the normal PR validation/review process. The merged policy is the
support authority. Acceptance timestamps are announced metadata, not image build or PR merge
timestamps. The scheduled workflow uses the exact Monday 06:00 UTC slot; security
and migration dispatches supply their explicit announced slot. Dates do not move
when a PR merges later or a workflow is rerun. A group is not supported before that
timestamp, and is authoritative only after its policy PR merges.

Validate both the current exact release evidence and historical immutability:

```sh
python3 scripts/release_groups.py validate --group lifecycle/bootstrap-group.json
python3 scripts/release_groups.py validate --previous previous-policy.json
```

Existing accepted groups cannot be removed, extended, retargeted or rewritten.
Adding a new group preserves the old record. The announced legacy migration deadline cannot move or disappear once published.
A schema change is required to change support-period rules after acceptance;
existing dates remain immutable. Fresh group
membership can extend an **artifact's** useful life, but does not rescue a consumer
that remains locked to an expired **group**. Known consumer pins inform migration;
they never extend a group's deadline.

## Checks at the point of consumption

A consumer lock selects a subset of one accepted cohort:

```json
{
  "schema_version": 1,
  "group": "bootstrap-2026-10-14",
  "resources": [
    {
      "line_id": "uxor-dev/8.5-trixie",
      "version": "1.0.1",
      "identity": "ghcr.io/xormania/uxor-dev@sha256:<accepted-digest>",
      "platform": "linux/amd64",
      "service": "php"
    }
  ]
}
```

The digest placeholder is explanatory; a lock must contain the exact accepted
identity from the group. `service` is optional and links a Docker observation to
a consumer service. Actual observations carry the same `line_id`, `identity`,
`platform` and optional `service`; a version claim cannot substitute for the
observed digest. Both the accepted manifest identity and its verified platform
manifest identity are recognized. Another platform, mutable alias, unknown image,
missing observation or resource outside the cohort fails.

The shared Python API is `check_selection(policy, lock, observed, now=None,
fetched_at=None, root=None)`. `now` and `fetched_at` are keyword arguments accepting
explicit UTC strings or aware UTC datetimes. `observed` is a resource list or
`{"resources": [...]}`. Production integrations acquire a fresh policy through
bounded HTTPS and supply the actual fetch receipt; an old project checkout or a
copy of policy inside its lock is not current authority. Offline runs require a
bounded, integrity-checked snapshot exported by that acquisition path.

The report contains `ok`, `status`, `code`, `errors`, `warnings`, and (when the group
is known) expiry and replacement fields. Each failure identifies the corrective
action. Warnings begin inclusively at `warning_starts_at`; expiry fails inclusively
at `support_ends_at`. A newer supported group is suggested, without updating the
consumer lock automatically. A successful warning still exits zero; failures exit
2. Policy acquisition and no-lock migration enforcement are described in
[downstream support](downstream-support.md).

For deterministic local diagnosis, the low-level CLI accepts explicit observation
and receipt files:

```sh
python3 scripts/release_groups.py check --lock selected-group.json \
  --actual observed-images.json --fetched-at 2026-10-20T08:00:00Z \
  --now 2026-10-20T08:00:00Z
```

Its `--fetched-at` and `--now` are operator assertions for testing, not proof of a
live fetch or an authoritative clock. CI/startup integrations use their acquisition
receipt and clock internally; copying the diagnostic command into CI would omit
that acquisition guarantee.

## Registry retention

Removal eligibility is a lower bound, not a deletion instruction. If one digest
belongs to multiple cohorts, its latest cohort deadline governs eligibility.
Required parent digests and associated assurance artifacts must remain together.
The registry planner inventories all references before suggesting deletion;
untagged platform manifests, SBOMs and signatures are not disposable merely
because they lack an image tag. Release evidence and group records remain available
permanently. Unadopted legacy images use the explicit migration deadline and grace
period; unknown pins cannot preserve them indefinitely.

## Weekly proposal workflow and retry recovery

The `.github/workflows/release-groups.yml` workflow runs every Monday at 06:00 UTC.
It proposes a cohort from the latest already accepted **master** image records.
`scripts/group_writeback.py` calculates the original run's scheduled slot from
GitHub's stable workflow-run `created_at`; a delayed invocation or later rerun does
not substitute its current wall clock for that slot. Normal image input refreshes
run Saturday at 06:23 UTC, and batch publication runs Sunday at 06:00 UTC. The
Monday cohort includes only publication records accepted into master by that time.
Ordinary master pushes do not publish another image batch; an applicable assurance
smoke run may still observe an existing digest.

Each proposal receives a content-derived `automation/group-*` branch. Recovery
finds an existing branch with the same group ID, including a branch whose push
succeeded before PR creation was interrupted. Its exact digest cohort and dates
remain unchanged even if master has since accepted additional images. Recovery
merges current master, regenerates only the owned policy file when two group
proposals conflict, preserves every newly accepted master group, and updates or
recreates the same PR through the repository REST API. A group already accepted
in master is a no-op. Unexpected authored-file conflicts fail for inspection;
there is no force push or automatic merge.

Manual dispatch can request an ordinary slot, security response or migration.
Security and migration require an explicit UTC slot and nonempty details explaining
the change. These reasons do not waive exact accepted publication evidence. Inputs
pass through environment variables as shell arguments, while PR bodies use the
existing structured request-file helper. Only repository contents and PR write
permissions are needed; no registry write permission is granted.

`LIBRARY_BOT_TOKEN` is used when configured, with `GITHUB_TOKEN` fallback. A PR
created through the fallback token may need workflow approval in GitHub. Cohort
acceptance still follows normal validation and review; this workflow creates no
new image, updates no consumer lock, deletes no registry version, and never merges
its own PR.
