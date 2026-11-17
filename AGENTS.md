# Working on this repository

Read [README.md](README.md), [the release contract](docs/versioning.md), and
[contributing](docs/contributing.md). [Architecture](docs/architecture.md) defines
the image supply boundary and the compatibility surfaces awaiting transfer.
[Responsibility boundaries](docs/responsibility-boundary.md) assigns ownership
and describes the migration. No installed skill or helper is required for
discovery from the public repository URL.

Xorder builds, verifies, publishes and maintains images. Consumers own their
application dependencies, services, tests and native environment preparation.
Use Xorder-owned disposable fixtures to prove advertised image capabilities;
consumer application suites must move to the consumer's own validation.
Tools and prepared dependencies may be packaged in images at pinned versions.
Packaging a tool does not transfer its project's lifecycle or policy to Xorder.

Image intent belongs in `images/*/definition.json`; measured facts belong in
verified `release-records/`. Generate `catalog.json`, the README availability
table, and `docs/images/` with `python3 scripts/library.py generate`.
Never add an unverified image to the available catalog or reassign an exact tag.
Explicit image recommendation retirement belongs in `retired-records/`: bind
each removed record's exact byte hash and original source commit to accepted
git history. The catalog gate verifies those deletions; historical publication
facts stay unchanged in that history and the original public Release assets.
Existing non-image resources, application helpers and project runners remain
compatibility surfaces pending explicit transfer. Do not add new non-image
products, expand resource kinds or add project lifecycle responsibilities.
Preserve their accepted records, interfaces and owned state until a reviewed
migration supplies the receiving integration. Keep generated compatibility views
consistent; do not maintain a second independent catalog. Optional context
payloads activate only when selected. Image support checks and published
retirement commitments remain in force during transfer.

Use feature branches and PRs against master. Run `python3 scripts/library.py check`
and `python3 -m unittest discover -s tests`. Container behavior is checked by
`scripts/verify-image.sh`, also used by the public usage instructions.

For interactive, user-directed work, including AI-assisted development, use the
requesting person's established Git identity for both author and committer.
Preserve that identity; running Git through an agent does not make the work an
automation job. Resolve the identity from the user's instructions or verified
user-specific Git configuration/account-linked history. If it is unavailable,
ask rather than inventing an identity or substituting a bot. Before committing,
check `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT`.

Reserve `xorder automation`, `image-library automation`, and Dependabot identities
for unattended repository jobs such as dependency refreshes and release/catalog
workflows. They are not the default for interactive development.

Do not add Claude, Codex, Grok, Anthropic, OpenAI, or xAI as an
author, committer, co-author, or other commit/PR attribution. Omit
generated-with footers, model session links, and equivalent signatures from
these tools. Technical prose about them and factual dependency or compatibility
records remain valid.
