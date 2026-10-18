# Publication and recovery

## HTTP resources

The same publication workflow also handles binary, environment, configuration,
and context resources. Their authored intent lives under `artifacts/`; accepted
facts live under `release-records/artifacts/`. Image publication and existing
GHCR names keep their established behavior.

Source PR validation retrieves the pinned upstream binary or packages only the
declared bundle files, then exercises those exact staged bytes. Environment jobs
install a pinned Nix/devenv toolchain and execute the native locked environment.
These PR results are verification evidence, not public release availability.

After master accepts the source, each independently versioned resource uses its
`<kind>/<name>/v<revision>` source tag and GitHub Release:

1. Prepare exact payload bytes. Bundle archives contain the declared paths from
   `payload/`, with deterministic headers and no links or special files.
2. Create a draft Release at the original source commit and upload the payload
   without replacing any existing asset. A retry compares existing bytes.
3. Publish that Release so its assets can be retrieved without credentials.
4. Download its public asset anonymously, check its exact checksum and size,
   and execute the kind's trusted verifier against the downloaded payload.
5. Upload the durable passed `record.json` without `--clobber`, then stage the
   accepted record and generated discovery views through the existing PR flow.

GitHub draft assets cannot provide anonymous download verification. Therefore a
public Release can exist while verification or catalog acceptance is pending.
Only accepted verified records appear as available in the catalog. A failed
runtime or corrupted public download never produces an available recommendation.

On retry, a persisted record identifies the artifact and original source.
Without a record, publication verifies and reuses the existing candidate at its
original source commit; it never replaces payload bytes. A different input at an
existing revision requires a new revision. Authentication/API failures do not
mean that a release is absent. Catalog writeback rechecks the public asset and
source Release before accepting it. It advances no HTTP aliases.

Configuration/context-only changes avoid image build jobs. Native environment
checks run only for affected environments; common delivery changes exercise the
resource consumers. Existing image input guards and release concurrency remain.

## Image publication

Source PRs build and execute behavioral fixtures on Linux amd64. After a source
PR lands on master, `Publish verified images` follows this path:

1. Build each changed/unreleased line with locked base digests and version labels.
2. Exercise the public readiness recipe and collect actual inventory.
3. Reserve a durable candidate receipt with the original source and build inputs
   before building. Push a separate input-key/revision-qualified candidate tag. Pull that same
   artifact by digest without credentials, and execute its readiness recipe.
4. Scan the published digest, generate its SBOM, keylessly sign it with GitHub
   OIDC, and verify the public signatures and signed receipt anonymously. The
   [assurance contract](image-assurance.md) describes the explicit vulnerability
   policy and public evidence. Persist these assets, `record.json`, and the
   inventory on a draft namespaced GitHub Release before changing an exact tag.
5. Promote the candidate digest to the exact tag. Refuse any different existing
   digest, verify the public exact reference and publish the source Release.
6. Open a PR containing verified release records and generated catalog/docs.
   Partial successes may be cataloged independently; failed exact promotions
   are excluded by writeback.
7. After this PR lands, `Promote accepted aliases` fetches the latest master
   ledger and points compatible aliases to its newest available revisions.

The source tag identifies the build commit. The generated documentation commit
is later. The GitHub Release assets retain the definition and inventory needed
to understand the exact historical artifact. The root README describes accepted
available images. Image source changes and record-only writeback have distinct
workflow path filters, preventing a publication loop.

The release/alias workflows share a repository-wide concurrency group, preserve
up to 100 pending runs with `queue: max`, and do not cancel in-progress promotion.
Different line jobs within a release may run
in parallel. An older queued job reads the current accepted ledger before
advancing an alias; it cannot overwrite a newer accepted recommendation.
Promotion resolves all desired exact references before writing any aliases and
skips aliases already pointing to the accepted digest. Its job summary identifies
unchanged, updated, failed and still-pending aliases, including failure details
when preflight rejects an alias or a registry lookup fails. A registry failure during
writes can still leave a partial update; rerunning resumes by skipping matches.

## Catalog review checks

`Verify image release evidence` runs separately from image build validation.
For new image ledger records it verifies the public source Release and source
commit, downloads its durable `record.json` using GitHub's asset checksum, and
compares the immutable record fields. It then resolves the exact image tag and
checks the parent and recorded platform digests anonymously. Existing release
evidence cannot be edited or renamed in place; lifecycle, reason,
replacement and lifecycle date can change without depending on the withdrawn
artifact's availability.
An explicit retirement declaration under `retired-records/` can remove obsolete
recommendations from the live ledger without rewriting their publication facts.
It binds exact original record bytes and source commits to an accepted historical
commit. The gate verifies each deletion against those bytes and the PR base,
and keeps the retirement declaration immutable. History and original public
Release assets retain the evidence. Retirement does not create a replacement
release, reassign an exact tag, or delete a remote artifact; fresh canonical
definitions stay unavailable until normal verified publication succeeds.
Manual dispatch checks all accepted image records against public evidence.

Catalog proposal branches are keyed by the complete durable input records,
including source and verification facts, rather than the workflow run ID.
Unrelated master/doc merges therefore recover the same pending proposal.
Existing run-ID catalog branches are also recovered if their pending PR already
contains all the exact incoming records. Conflicting source, digest, or
verification observations cannot be treated as the same content.

The [repository gate audit](repository-gates.md) records the external ruleset
settings and a reviewable administrator update for stable `checks`,
`catalog-evidence`, and `attribution-policy` contexts. A green workflow alone
does not prove those contexts are required by the live ruleset.

Generated catalog PRs summarize every proposed record on the branch, including
records retained during recovery. The table shows previous and proposed
revisions, new families, measured image sizes and baseline changes, and the
compatible alias target after acceptance. Source commits, associated merged
PRs when GitHub's lookup is available, public Releases and verification runs
provide links to the evidence. HTTP resource sizes appear as payload bytes.

## First publication setup

The repository uses GitHub-hosted runners. Master has an active PR ruleset,
allows merge commits, and has automatic merge disabled as inspected on
8 October 2026. Automation stages protected-branch changes in PRs; it does not
bypass those controls or invent an automatic merge entitlement.

Required settings:

- Permit Actions and the pinned official actions used by these workflows.
- Permit the workflow token to create/write repository-associated GHCR packages
  and GitHub Releases. Source PR validation uses read-only repository permissions.
- Permit automation to create PRs. `LIBRARY_BOT_TOKEN` is an optional repository
  secret for a suitably scoped bot token, so bot-created PRs trigger normal CI.
  PRs created or updated with `GITHUB_TOKEN` require **Approve workflows to run**
  in the PR's merge box. Use the bot token for automatic validation.
  For this public, personally owned repository, `xor-machine` can use a classic
  PAT with `public_repo` after accepting a collaborator invitation. Fine-grained
  PATs do not currently support cross-account repository collaborators.
  Store the token as `LIBRARY_BOT_TOKEN`; PR writeback uses REST and does not
  require `read:org`. Renew the token before its chosen expiration.
  Never commit the token. See GitHub's [token limitations](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
  and [workflow trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
- After the first candidate push, set each GHCR package (`php-dev`,
  `php-browser`, `uxor-dev`, `rust-dev`, `python-dev`) to **public** using its package settings.
  GHCR creates packages private by default and provides no container-visibility
  mutation in this workflow. Rerun the failed publication job; it will reuse the
  candidate, not rebuild. Browser packages are created after their PHP parent
  passes, so first publication can need a second visibility/setup pass.
- Merge generated catalog/input-refresh PRs using the permitted merge method.
  Fully unattended default-branch writeback needs an explicitly authorized
  merge mechanism consistent with the current ruleset; it is not configured
  merely by adding these workflows.

Actual package permissions and anonymous pulling are checked by publication,
not assumed because a repository is public. There are no stable published
references until that succeeds and the records are accepted.

## Retry and failure boundaries

GitHub, git and the registry do not form an atomic transaction.

| Failure point | Recovery |
| --- | --- |
| Build/test before candidate push | Fix the failure and retry; no stable recommendation changed |
| Candidate pushed, public pull blocked | Make package public/fix network, rerun; existing candidate is pulled and tested |
| Record persisted, exact promotion failed | Rerun; download durable record and promote the same digest |
| Exact/GitHub Release succeeded, docs PR failed | Rerun; use release asset and restage docs; old aliases remain |
| Docs merged, alias job failed | Rerun `Promote accepted aliases`; fetch current ledger and verify exact references |
| Exact tag exists with a different digest | Stop; workflow refuses overwrite; allocate a fresh revision or recover the intended record |
| Existing record cannot be fetched | Stop; do not interpret an API failure as an absent release |
| Last available revision withdrawn/deprecated with an existing alias | Stop before any alias updates; restore a verified available replacement or retire the alias tag while retaining exact artifacts, then rerun |
| Refresh branch pushed, PR creation failed | Rerun; fetch/reuse the branch, merge current master, and recover the PR even when the generated files are unchanged |

Refresh writeback prepares its branch before resolving upstream inputs. Reruns
allocate the proposed revision from current master, preserving a pending
refresh's revision instead of incrementing it again, and use ordinary pushes.
`python3 scripts/writeback.py --refresh` performs that complete refresh flow.

If another catalog PR has landed since an automation branch was created,
writeback merges the authored inputs and release ledger first, then regenerates
conflicting catalog/documentation outputs. README prose is merged with its two
generated tables removed, and those tables are rebuilt from the combined ledger.
Conflicting release identities, authored files or README prose stop for manual
recovery. The branch keeps its existing history and uses an ordinary push.

The candidate tag includes the stable build-input key and revision. The draft
Release's candidate receipt freezes the original source, definition, tools and
historical input fingerprint before the first build. Metadata-only source
changes resume that candidate without generating another image. A different-input retry
of a persisted revision fails, requiring a new revision. An exact tag without
its durable record is ambiguous and requires recovery, not a silent rebuild.
No failed candidate advances the catalog or alias. GitHub Release publication
alone does not complete catalog writeback and alias promotion; workflow status
and the default-branch catalog show those separate steps.

Ordinary image publication batches changed inputs on Sunday 06:00 UTC. The refresh
proposal runs Saturday 06:23 UTC, and Monday 06:00 UTC proposes a release group
from accepted records. Each proposal still needs its normal PR acceptance;
unfinished image evidence never enters a group. Off-schedule publication and
recovery require an explicit workflow-dispatch reason.

[Release groups](release-groups.md) announce support deadlines. The
[retention planner](retention.md) protects supported groups and their complete
digest graph, then proposes eligible removal after the grace period. It does
not delete registry packages. Known project pins produce migration notices and
do not silently extend support. Docker Hub mirroring is a later optional step and would
need its own anonymous-pull verification before entering the catalog.
