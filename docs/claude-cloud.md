# Claude cloud sessions for uxor

Start each session from the current [xorder README](../README.md), select an
accepted image digest from the [catalog](../catalog.json), and read the
[uxor profile](uxor.md). The image provides the toolchain;
the checkout owns its application packages, Caddy configuration and tests.
The runner is mounted from your xorder clone, so runner fixes require updating
that clone, not rebuilding or replacing an unchanged image.

## Before starting a stack

1. Run `docker info`. A Docker CLI does not establish that an engine is usable.
2. Check free space with `df -h` on the checkout and Docker data filesystem.
   Read the selected image's cold-pull estimate; keep room for its browser,
   dependencies, caches and test output. Host-wide percentages can hide a
   smaller sandbox allowance. `run.sh status` reports free space first and
   warns below its configured threshold.
3. Pin the accepted image digest. Select the browser version from the project's
   exact Playwright lock; do not upgrade Playwright merely to fit an image.
4. Use a distinct checkout and Compose project/slot for concurrent work.
   Run only the profile's required dependency setup, once, or adopt a complete
   prepared installation as described below.

```sh
export IMAGE='<accepted flowbite-xor-dev digest_reference>'
export WORKSPACE='/absolute/path/to/uxor-worktree'
bash examples/uxor/run.sh --slot 2 up
bash examples/uxor/run.sh --slot 2 status
```

## When the proxy blocks package archives

Registry pulls, git transport and archive downloads are separate network paths.
Successful git access does not prove that GitHub zipball/codeload downloads
are allowed. Check the actual failed URL and status before changing package
configuration. Follow the profile's proxy/CA guidance; never substitute an
unreachable host loopback proxy into a container or disable certificate
verification for outbound dependency downloads.

Ordinary `up` installs Composer packages from dist only. It rejects
`COMPOSER_INSTALL_PREFERENCE=source`; source clones can consume several GiB.
The accepted PHP 8.5 image revision 1.2.1 records Composer 2.10.3, which already
disables source fallback by default. A wrapper explicitly requesting source
still selects clones. Inspect the actual runtime and the effective settings
with startup bypassed, from `/app/demo`:

```sh
composer --version
printf 'install preference: %s\n' "${COMPOSER_INSTALL_PREFERENCE:-dist}"
composer config --source preferred-install
composer config --source source-fallback
```

If dist downloads are denied, report the dependency URL and proxy response.
Prepare locked dependencies where those downloads work, import an authenticated
[dependency bundle](agent-feedback.md#shared-dependencies-and-ci-artifacts), or reuse a complete
installation from a trusted worktree. Do not silently switch to git clones.
No archive access is claimed for every Claude session: allowlists and quotas
must be checked in the actual environment.

## Reusing worktree dependencies

Seed absent dependency directories from an explicitly trusted prepared checkout:

```sh
python3 scripts/xr.py '/absolute/new-worktree' seed --from '/absolute/prepared-worktree'
```

The command compares Composer and npm manifests/lockfiles, `demo/symfony.lock`
when present, and the selected importmap file before copying. It preserves whole
dependency trees, including generated autoload/runtime metadata, npm's installed
lock and importmap `installed.php`. Existing destinations, checkout-escaping
symlinks and changed inputs fail without overwriting dependency directories.
The default uses independent reflinks when supported, otherwise private copies.
It needs no image or Docker engine and runs no installs or setup hooks. The next
`up` still runs the existing Composer/npm/importmap readiness checks.

For disks where private copies are too expensive, stop both checkouts' stacks,
then explicitly request hardlinks:

```sh
python3 scripts/xr.py '/absolute/new-worktree' seed --from '/absolute/prepared-worktree' --hardlink
```

This mode verifies that neither checkout is mounted by a running container and
writes `.xorder-shared-dependencies.json` in both. It also registers authoritative
sharing guards outside the mounted checkouts in the host's xorder state directory.
Future runner `up` calls use read-only reuse even if the flag is omitted; other
Compose actions retain the protected mounts. Deleting or changing a checkout's
marker cannot opt out: the host guard makes mutating runner commands fail closed.
`seed` adds the marker to Git's local `info/exclude`, including linked worktrees,
so commit-check hooks do not request machine-local state. Keep the local marker
with its checkout and retain the same host state directory across sessions.
Hardlinks share file contents: avoiding `install` alone does not prevent Composer
autoload generation, setup hooks, npm metadata writes or test tools from
changing another worktree. Do not change permissions on hardlinked files as
an isolation mechanism; permission changes are shared too.

For manually prepared dependencies without the sharing receipt, use:

```sh
bash examples/uxor/run.sh --slot 2 up --reuse-only
```

This mounts dependency trees read-only, verifies them before services start,
reports missing setup and runs no install, setup hooks or dependency repairs.
Local readiness markers are not invented. For seeded hardlinks, the receiver's
selected project sync command first creates its own demo recipe copies while
dependency mounts are read-only; donor demo copies are never transplanted.
Symfony/Tailwind output stays in the stack's own `demo/var` volume. A reported dependency gap requires a private
writable preparation step; do not rerun ordinary `up` against shared hardlinks.
Tests that deliberately modify dependency packages also require a private copy.
Host tools can still write hardlinked files, so use the runner's protected
containers. To return a receiver to private dependencies, stop its stack, remove
its seeded dependency directories, then explicitly clear its guard:

```sh
python3 scripts/xr.py '/absolute/new-worktree' seed --forget-sharing
python3 scripts/xr.py '/absolute/new-worktree' seed --from '/absolute/prepared-worktree'
```

The forget command requires every guarded dependency tree to be absent and
confirms no running container still mounts the checkout. Retain the donor's
guard while another shared tree exists. A marker from the earlier runner without
an authoritative host guard is refused; remove that checkout's shared trees and
use the same forget/reseed procedure to migrate it safely.

## During work and recovery

- Use the profile's `test`/`php-tests` commands and heavy-run budget rather than
  independently starting several unbounded test pools.
- Use one Serena project root (`.` for uxor) and the daemon for repeated
  queries; follow the [Serena coverage and REPL guidance](serena.md).
- Inspect `status` and scoped logs after a failure. Preserve a healthy sibling
  stack. `down` retains caches; `down --volumes` removes that stack's volumes.
- Keep intentional image pins with `gc --keep IMAGE`. Inspect a dry run before
  removal; xorder also protects container image ancestry.
- Report the selected digest, runner commit, failed command and actual error.
  Do not describe a stack as ready until its application page responds.

## Keeping guidance discoverable

The README, image usage links and this guide are the current entry points for
future sessions. A future image refresh can include a short
`/opt/xorder/SESSION.md` linking here and identifying its runner contract.
Keep proxy rules, worktree paths and incident-specific workarounds in current
repository guidance rather than freezing them into an image. Adding an
embedded file changes image inputs and needs its own fresh verified revision.
