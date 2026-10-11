# Image versions and compatibility

Each family/runtime/OS line owns an independent SemVer image revision. PHP's
runtime patch is measured separately; an image revision is not a language version.
The first stable revision of each accepted line is 1.0.0.

The compatibility contract includes advertised capabilities and extensions,
executable paths, workspace `/workspace`, writable HOME `/home/dev`, default
effective UID/GID 1000 and PUID/PGID overrides, cache conventions and entrypoint
invocation. Removing any of these or changing behavior incompatibly requires a
major revision. Additive compatible capability changes use a minor revision.
Compatible dependency/base refreshes and fixes use a patch revision, after
checking upstream changes against this contract.

| Reference example (naming only) | Meaning |
| --- | --- |
| `ghcr.io/xormania/php-dev:8.5-trixie-v1.2.3` | Exact image revision; the release workflow refuses reassignment |
| `ghcr.io/xormania/php-dev:8.5-trixie-v1` | Latest accepted available compatible 1.x revision; moves only after catalog writeback lands |
| `ghcr.io/xormania/php-dev@sha256:<digest>` | Exact artifact content identity; preferred project pin |
| `php-dev/8.5-trixie/v1.2.3` | Namespaced git source tag and GitHub Release |

These are examples, not claims that those tags exist. Read the current catalog.
Tags are normally mutable registry references; the workflow's guard is not a
registry-wide immutable-tag guarantee. Administrator changes outside the workflow
are possible. Digest identity does not guarantee indefinite registry retention.

Every newly built published artifact receives a new revision, even if the
Dockerfile text did not change. A retry resumes a recorded artifact; it does not
rebuild and reuse an exact revision. The record retains the source commit,
resolved base/parent, tool inputs, verified platform inventory and image digest.
Initially there is one amd64 manifest; index and platform digests are retained
when the registry returns an index. Supporting additional platforms requires
extending the build and complete acceptance tests first.

Keep existing digest pins until deliberately upgrading. Verify a proposed
replacement against the project, then change its recorded digest in a PR.
Rollback uses an existing verified artifact, without overwriting an old exact
tag. To withdraw/deprecate a recommendation, change its release record's
`lifecycle`, add `reason`, `replacement`, and `lifecycle_date`, and regenerate
the docs through a PR. Withdrawing removes it from selection. Alias promotion
chooses the newest remaining available revision in that major line, permitting
an intentional rollback with an explicit ledger change.
If no available revision remains and an alias still exists, promotion fails
explicitly before changing any aliases. Restore a verified available replacement
or retire the alias tag while retaining exact tags and digests, then rerun.
Withdrawal changes recommendations; it does not itself remove registry artifacts.

New language minor/OS lines have separate names and independent revisions.
A php-dev artifact change must allocate a new revision for its derived browser
line. Unrelated Rust/Python lines need not change. Shared installed-tool changes
affect their actual consumers; weekly refreshes allocate fresh patches only when
resolved tool/base inputs or tracked Debian package-index contents change.

New image assurance is recorded separately from artifact content. Adding scanning,
SBOM generation, or signing to the release workflow does not allocate image
revisions or rewrite historical source, timestamps, verification, or inventories.
New publications include their exact digest's [assurance](image-assurance.md).
Existing unsigned releases retain their original contract and identity; a manual
assurance-only run can publish a fresh observation as separate evidence.
