# Working on this repository

Read [README.md](README.md), [the release contract](docs/versioning.md), and
[contributing](docs/contributing.md). [Architecture](docs/architecture.md) defines
the broader resource boundaries. No installed skill or helper is required for
discovery from the public repository URL.

Image intent belongs in `images/*/definition.json`; measured facts belong in
verified `release-records/`. Generate `catalog.json`, the README availability
table, and `docs/images/` with `python3 scripts/library.py generate`.
Never add an unverified image to the available catalog or reassign an exact tag.
Explicit image recommendation retirement belongs in `retired-records/`: bind
each removed record's exact byte hash and original source commit to accepted
git history. The catalog gate verifies those deletions; historical publication
facts stay unchanged in that history and the original public Release assets.
New resource kinds follow the same separation of authored intent and verified
release evidence. Profiles select resources rather than duplicate their facts.
Generate compatibility views from one shared model; do not maintain a second
independent catalog. Optional context payloads activate only when selected.

Use feature branches and PRs against master. Run `python3 scripts/library.py check`
and `python3 -m unittest discover -s tests`. Container behavior is checked by
`scripts/verify-image.sh`, also used by the public usage instructions.
