# Agent environment feedback — implementation

Claude's 2026-10-10 flowbite-xor report (now uxor) identified failures in clean Serena
sessions, repeated indexing/downloads, disk use, and concurrent browser tests.
The following changes implement the requested operations. Browser image size
and real language-server behavior are measured by image acceptance, rather
than inferred from recipe changes. New image capabilities become selectable
only after publication and accepted release evidence.

| Feedback | Implementation | Validation |
| --- | --- | --- |
| A1: clean read-only PHPactor crash | Disable automatic configuration prompts in launch and initialization; generated state stays outside source | First acceptance session is read-only with no `.phpactor.json`; symbol and reference queries followed by another successful query |
| A2: shell access | One-shot queries and a private Unix socket daemon over the existing stdio MCP service | Protocol unit tests and real shell editing acceptance |
| A3: repeated cold indexing | Optional per-worktree/per-image cache with complete source/dependency/backend/settings fingerprint and exclusive lifetime lease | Image acceptance restarts against one cache; source changes invalidate completeness |
| A4: JavaScript and Twig | Locked TypeScript 5.9.3 / language-server 5.1.3; explicit mixed-language selection; coverage table | Offline JavaScript symbols, references, and source editing; Twig remains documented text navigation |
| A5: timeout/session/dead server | Configurable LSP timeout, structured session ID, immediate stopped-server error and explicit recovery | Protocol tests and actual structured MCP response acceptance |
| B1: downloads and prepared dependencies | Checkout-isolated Composer downloads and vendor/importmap snapshots, authenticated portable export/import | Metadata/mode/symlink preservation, poisoned-bundle rejection and input invalidation tests; Symfony/Composer still verify restored installations |
| B2: disk and cleanup | Disk status and dry-run garbage collection of stopped xorder containers, unreferenced xorder images and orphaned runner state | Cleanup preserves running containers, referenced images and source repositories |
| C1: sync | Profile-declared `sync` action runs the complete project sync command | Runner command regression test and consumer acceptance |
| C2: recovery and trust | Daemon/relay status, idempotent service and relay recovery, unique additional CA roots | Existing relay acceptance plus failure/status tests and real PEM parsing |
| D1: browser footprint | Node/Trixie Playwright image with exactly the locked Chromium, Firefox and WebKit engines, no PHP or compiler toolchain | Offline launch, DOM interaction and screenshots in all engines; normal size measurements |
| D2: competing tests | Host-wide heavy-run leases, automatic worker budget and per-service CPU/memory caps | Another worktree's process is refused while a lease is held; loaded host reduces workers |

## Runner operations

Use `WORKSPACE=... examples/uxor/run.sh ACTION`. The legacy
`examples/flowbite-xor/run.sh` entry point remains valid. The optional adapter
is `python3 scripts/xr.py WORKSPACE ACTION`:

```sh
export IMAGE=ghcr.io/xormania/flowbite-xor-dev@sha256:YOUR_ACCEPTED_DIGEST
python3 scripts/xr.py /path/to/worktree up
python3 scripts/xr.py /path/to/worktree sync
python3 scripts/xr.py /path/to/worktree status
python3 scripts/xr.py /path/to/worktree test tests/e2e/example.spec.ts
python3 scripts/xr.py /path/to/worktree gc
python3 scripts/xr.py /path/to/worktree gc --apply
python3 scripts/xr.py /path/to/worktree gc --keep ghcr.io/xormania/php-toolkit:8.5-trixie-v1.0.1
```

Sync runs `php tools/sync-demo` from the checkout root and preserves command
output so copied files are visible. A failed or missing script returns nonzero.
Status needs no image or package lock and reports host disk/load, Docker,
container health, application readiness and required loopback proxy relay state.
Disk output leads with free space and warns below 3 GiB regardless of filesystem
capacity. `XORDER_DISK_WARN_GIB` changes that threshold. Filesystem accounting
may not expose a sandbox's quota; consult its quota display too. Image pages
give cold-pull space estimates derived from measured unpacked sizes. Check the
Docker data filesystem as well as the checkout; their available space can differ.
`up` first tries an existing local Docker service when the daemon is unavailable;
`XORDER_DOCKER_START_COMMAND` supplies an explicit executable and arguments where
the service manager differs. The runner does not launch a keepalive daemon.

The PHP and browser service defaults are two CPUs and 2 GiB each. Override
`PHP_CPUS`, `PHP_MEMORY`, `BROWSER_CPUS`, and `BROWSER_MEMORY` as needed. Heavy
test runs share the host's xorder state directory: one run by default, with up
to four workers selected from CPU load and available memory. Override
`XORDER_TEST_MAX_RUNS` and `XORDER_TEST_MAX_WORKERS` deliberately. An explicit
Playwright `--workers` argument is retained; the concurrent-run lease still
applies. Separate hosts or distinct `XDG_CACHE_HOME` roots have separate budgets.

[Startup budgets and shared host runs](runtime.md) describe pre-pull image size
observations, queued leases, quiet measurement admission and idle activity signals.

## Shared dependencies and CI artifacts

Caches are grouped by canonical Git repository and isolated by checkout path.
Each container mounts only its checkout's snapshots and Composer downloads; a
linked worktree cannot write another checkout's dependency inputs. Old writable
repository-wide snapshots are not reused automatically. `XORDER_SHARED_CACHE_DIR`
selects an alternate host root while retaining checkout isolation;
`XORDER_SHARED_CACHE=0` disables the automatic cache binds. The existing explicit
`COMPOSER_CACHE_DIR` option also retains its workspace isolation.
Cache binds stay outside HOME and the entrypoint does not change their ownership.

Snapshots have separate identities for Composer vendor and importmap assets.
Keys include the Composer manifest/lock, runtime, and image; importmap additionally
includes its source map. Importmap snapshots include Symfony's `installed.php`.
Archives preserve executable modes, relative symlinks and installation metadata;
all regular files are checked before atomically restoring an absent tree. Existing
trees are not overwritten. The consuming project's Composer verification,
autoload generation, setup hooks and Symfony importmap validation still run.
Those checks establish installation consistency, not producer trust: vendor and
importmap metadata can execute code. Cross-checkout imports therefore require an
expected SHA-256 supplied through a trusted producer or CI artifact channel.
The helper authenticates the entire bundle before reading its archives, and
extracts the same authenticated bytes even if the input path is replaced.

```sh
python3 scripts/xr.py /path/to/worktree cache export --output /app/dependencies.zip
# Export prints SHA-256. Transfer the bundle and record that digest through a
# trusted channel; DEPENDENCIES_SHA256 is the expected digest from that producer.
python3 scripts/xr.py /path/to/other-worktree cache import \
  --input /app/dependencies.zip --sha256 "$DEPENDENCIES_SHA256"
```

Both paths are container paths; `/app` is the checkout bind. Cache export/import
use a one-shot container with the selected image, checkout mounts and UID; they
bypass application startup and do not require a running PHP/browser service.
Import first runs the selected recipe sync command, then authenticates and
validates every selected snapshot before promoting a cache key. A mismatched
runtime/image/lock bundle fails instead of reporting an empty successful import.
The public cold-import acceptance starts an empty checkout, imports through this
command and checks that `up` reaches readiness without reinstalling Composer.
A CI preparation job
can run `python3 examples/flowbite-xor/cache.py export --project demo --cache CACHE
--output dependencies.zip --image EXACT_IMAGE` and upload that file. Consumers
with matching runtime/image/lock inputs import the same bytes using
`--sha256 EXPECTED_DIGEST`. Obtain the digest from the trusted preparation job,
not a manifest or checksum file supplied by an untrusted bundle producer.
Projects without the selected `importmap.php` export/import vendor only.
The helper is
stdlib Python and requires the project's PHP runtime for its compatibility key.
This xorder PR does not modify uxor's separate CI workflow.

Prepared snapshots avoid repeated downloads; restored vendor trees remain local
and writable. This implementation does not mount one mutable vendor tree into
all worktrees or claim that compressed snapshots remove all duplicated disk use.

Snapshot storage checks every archived member, including its checksum, before
reusing an existing ZIP. An intact manifest cannot conceal a corrupted payload.
A damaged archive is quarantined beside its key and replaced atomically from a
verified local tree. Snapshot usage records the most recent action/time; these
observations are cache history rather than proof that setup hooks ran.

Inspect and prune explicitly:

```sh
python3 scripts/xr.py /path/to/worktree cache usage
python3 scripts/xr.py /path/to/worktree cache prune --dry-run
python3 scripts/xr.py /path/to/worktree cache prune --apply
# Host-wide discovery of caches whose registered checkout no longer exists:
python3 scripts/xr.py /path/to/worktree cache usage --orphaned
python3 scripts/xr.py /path/to/worktree cache prune --orphaned --dry-run
python3 scripts/xr.py /path/to/worktree cache prune --orphaned --apply
```

The checkout prune removes only owned regular snapshot/quarantine files whose
keys differ from the current runtime/image/locks. It preserves current keys,
Composer download directories, unknown files and symlinks, and serializes against
snapshot restore/store/import. Orphan pruning includes only caches registered by
this runner whose checkout is absent. It checks every Docker container's binds
and labels, including stopped/unlabelled containers, then rechecks references
and the snapshot lease before removal. An unavailable Docker engine, active
transaction, changed registration or unknown cache entry blocks deletion.
Registered Composer downloads can be reclaimed with an orphaned cache; legacy
unregistered caches and source checkouts remain untouched. Reports include
logical cache/snapshot bytes and reclaimable bytes; filesystem quota and physical
allocation can differ. Each command is dry-run unless `--apply` is explicit.

## Browser selection and cleanup

An accepted `playwright-browser` entry is selected only when its measured
Playwright version matches the consuming lock. Until acceptance, or for another
version, the existing official Playwright companion remains the fallback.
`BROWSER_IMAGE` explicitly selects a local xorder candidate or accepted digest.
Candidates use the prepared `playwright run-server` executable and all engines
are installed during build. The runtime downloads no browser or Node packages.

Garbage collection is dry-run by default and preserves volumes and caches. It
lists stopped containers carrying xorder workspace labels and xorder images that
no container references. Every container is considered, including created,
stopped, unlabelled and Serena daemon containers. Parent images are protected
using Docker ancestry and filesystem layer prefixes, including local derivatives
whose BuildKit metadata has an empty `Parent`. Repeat `--keep IMAGE` for tools
needed between runs, such as Toolkit lint; each kept image also protects its
ancestors. Keep references must resolve locally. Apply rechecks running state
and image ancestry before each removal and never forces image removal.
Orphaned registered worktree pointers and runner receipts may be removed.
Use `gc --runner-copy /absolute/path/to/old-unpacked-xorder` to include an old
runner copy in the plan. Copies must be outside the source checkout and current
runner, contain xorder discovery/runner files, have no Git repository, and have
no container bind references. Apply rechecks those references. Source checkouts
and unselected runner directories are preserved.
