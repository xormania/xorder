# Applying a selected setup

The public README, compact catalog, and resource pages are enough to discover
and use xorder. The optional helper automates verified download and target file
management using the same release identities. It requires Python 3, the
dependencies in `requirements-ci.txt`, and a POSIX host. Initial runtime
verification is on Linux amd64. Direct usage remains documented per resource.

## Resolve, inspect, and apply

Inspect the project's existing pins and prerequisites first. Record observed
target facts as described in [architecture](architecture.md); the helper checks command
availability and the actual platform again before applying. Descriptive runtime
requirements still need their resource's readiness check.

```sh
python3 scripts/xorder_cli.py resolve profiles/composer.json \
  --target target.json --output xorder.lock.json
python3 scripts/xorder_cli.py plan xorder.lock.json --root /path/to/project
python3 scripts/xorder_cli.py apply xorder.lock.json --root /path/to/project
python3 scripts/xorder_cli.py verify --root /path/to/project
```

For this Composer example, `target.json` records `platform: linux/amd64` and
`commands: [php]`, after inspecting the target. It supplies a PHAR rather than
a PHP runtime. Other [profiles](../profiles/) use the same operations.

Resolution fails if a required resource has no verified accepted release.
Applying validates the lock against the accepted catalog; editing its payload
URL, destinations, or identity cannot substitute different content. Retain a
prior lock with `resolve --pins xorder.lock.json` to preserve compatible pins.
Pins bind the resource ID, revision, and exact content identity, including when a
profile renames or adds a role for that resource. A conflicting explicit revision,
an unavailable pinned release, or changed prerequisites produces a reported gap;
resolution does not silently replace that pin with a newer release or another
resource. Remove or replace the affected pin deliberately to change its selection.
Platform-specific resources require an observed platform during resolution and
check it again before application. Resources declaring `targets: [any]` may omit
that fact; any platform explicitly recorded in a lock is still checked for change.
An explicit local `--overlay` selects private assignments without publishing
them; the lock records the overlay's content hash.

The helper downloads exact bytes, checks their SHA256, and stages them before
changing target files. Bundles extract inside a fresh staging directory with
unsafe archive members rejected. It applies only selected destinations and
preserves unowned files, local content edits, and local permission changes.
Resolve those specific conflicts before applying again.

The receipt describes materialized files. For a native environment, activate
the installed files with its documented backend command such as `devenv shell`.
For an image, the helper reports its exact reference and usage page as an
external action; it does not claim to have pulled or started that image. Run
the corresponding readiness checks after activation. Native backends own
their services and process lifecycle.

## State, updates, and recovery

State defaults to the normal per-user XDG state directory under `xorder/`,
separated by canonical target root. Immutable cached content lives in the XDG
cache directory under `xorder/sha256/`. Use `--state-dir` and `--cache-dir` for
explicit alternatives, including project-local state when desired. Keep the
same state/cache locations when recovering or rolling back. A per-target lock
prevents overlapping helper applications.

Repeated application of unchanged content leaves files untouched. An upgrade
retains previous owned bytes and permissions. Removing a role from a profile
does not silently delete previously installed files; removal is explicit.

```sh
python3 scripts/xorder_cli.py recover --root /path/to/project
python3 scripts/xorder_cli.py rollback --root /path/to/project
python3 scripts/xorder_cli.py remove binary/composer --root /path/to/project
```

`recover` restores the before-state of an interrupted application. If a file
was edited after the interruption, recovery preserves it and reports the
conflict. `rollback` undoes the latest retained completed application, including
an explicit removal, using verified retained local bytes. It does not rewrite
release history. Removal only affects unchanged files owned by the selected
installation.

A setup spanning files and native backends is not globally atomic. Application
results report completed actions and any recovery failures. File verification
checks receipt hashes and permissions; resource readiness checks establish
runtime behavior. Delivering context checks its placement and identity, not
whether a model followed its instructions.
