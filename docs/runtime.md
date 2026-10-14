# Startup disk budgets and shared host runs

The project runner checks disk space before a one-off dependency inspection,
image pull, service start or dependency setup. `up` reserves 1 GiB for workspace
dependencies, caches and output by default. `XORDER_DISK_RESERVE_GIB` sets the
reserve for the actual project; it is an explicit allowance, not a measured
claim about every stack.

For missing images the runner reads registry manifests through
[`docker manifest inspect`](https://docs.docker.com/reference/cli/docker/manifest/inspect/).
An image index selects the service's declared platform, `DOCKER_DEFAULT_PLATFORM`,
or the daemon's observed OS/architecture. Ambiguous or unavailable platform
metadata produces an unknown-size warning. Layers compressed with gzip/zstd
report their advertised compressed bytes. Config and layer descriptors also
produce a full registry-blob total; shared descriptor digests are counted once
in the aggregate. These are
[OCI descriptor byte sizes](https://github.com/opencontainers/image-spec/blob/main/descriptor.md),
not measured bytes downloaded by this daemon. Locally cached layers can reduce
the transfer; local images need no cold-pull allowance.

For accepted xorder identities with release size evidence, the cold-pull
planning allowance remains twice the recorded unpacked image size. Other
missing images use three times their advertised blob bytes, explicitly labeled
as an estimate with unknown unpacked size. `XORDER_PULL_EXPANSION_FACTOR` changes
that factor; compression ratios and temporary storage vary, so no factor
guarantees adequate space. `XORDER_PULL_BUDGET_GIB` sets a minimum total
cold-pull allowance when there is a trusted size observation or known project
requirement. Unavailable metadata remains a warning and is never treated as
a verified zero-byte pull.

The checkout filesystem must cover its reserve. Docker's reported
`DockerRootDir` is informational: a local socket and an accessible path with that
name do not prove that the daemon shares the client's filesystem. For a verified
client-visible data directory, set `XORDER_DOCKER_DATA_DIR` to its absolute path
after confirming that it belongs to the selected Docker engine. Only then does
its filesystem free space govern image-budget refusal; the reserve is included
when both paths share a filesystem. An unconfirmed daemon root, VM or remote
engine produces a warning to inspect that engine's disk separately while still
reporting the pull estimate. Filesystem accounting may not expose sandbox quotas.
The runner also cannot reserve space against another concurrent pull.
Known shortfalls refuse startup. `XORDER_DISK_PREFLIGHT=warn` deliberately
changes that policy to a loud warning, preserving the observations.

## Heavy runs and measurement

Heavy tests cooperate through the existing host cache root. One normal run is
allowed by default, with automatic workers from effective CPUs, current load
and available memory. `XORDER_TEST_MAX_RUNS` and `XORDER_TEST_MAX_WORKERS` retain
their existing meanings. A refusal identifies the workspace, project, PID,
lease age and mode. Released or crashed processes cannot keep a kernel lease.

```sh
python3 scripts/xr.py /path/to/worktree test --wait 300 tests/e2e/example.spec.ts
python3 scripts/xr.py /path/to/worktree test --measure --wait 600 --workers=1 tests/performance.spec.ts
```

`--wait` without a number allows 600 seconds. Waiting uses a FIFO queue shared
by cooperating runner copies. Admission order follows registration under a host
lock; later requests cannot take a slot ahead of an earlier waiter. Kernel-held
tickets let the next request reclaim killed or cancelled waiters automatically.
`XORDER_TEST_MAX_WAITERS` bounds queued requests (default 64, maximum 1024).
Refusals report queue position, elapsed wait and the active holders. Older runner
copies do not participate in FIFO ordering, although their slots remain protected.
`XORDER_TEST_WAIT_SECONDS` supplies the same default
for wrappers; zero retains immediate refusal. `--measure` (or
`XORDER_TEST_MEASURE=1`) holds an exclusive gate against all cooperative heavy
runs regardless of their configured slot count. Before executing tests, it
also locks all 64 supported numbered slots, so older runner copies that do not
know the new gate cannot acquire a newly created slot during measurement. It
waits until one-minute host load is at most half the effective CPU count.
`XORDER_MEASURE_MAX_LOAD_PER_CPU` changes that ratio. With no wait allowance,
a busy host is refused with the measured load and CPU threshold shown.

Unrelated processes and commands outside the leased test path can still create
load after admission. The gate is coordination rather than CPU isolation; a
quiet admission observation alone does not certify fair performance results.
Shared resource snapshots include one-, five- and fifteen-minute load averages
for test receipts. Explicit Playwright `--workers=N`, `--workers N`, `-jN` and
`-j N` requests are capped at the acquired worker budget. Percentages are resolved
against the runner's observed effective CPU budget and then capped. Receipts keep
the original and effective arguments; lower explicit counts remain lower.
All queued test and plant commands use the same executor. Direct `exec npx
playwright test` remains an escape hatch outside cooperative leases and receipts;
use `test --wait` for normal concurrent work.

### Browser throttling

The UXor Compose profile defaults to `BROWSER_CPUS=2` and `BROWSER_MEMORY=4g`;
these apply to the separate browser-server container. To reproduce timing bugs
under a deliberately restricted browser CPU share:

```sh
BROWSER_CPUS=0.25 python3 scripts/xr.py /path/to/worktree up
python3 scripts/xr.py /path/to/worktree test --wait --workers=1 tests/e2e/example.spec.ts
```

Compose reconciles the changed resource limit on `up`. `PHP_CPUS` and
`PHP_MEMORY` control the application container independently. Running busy loops
on the host does not necessarily reproduce a restriction inside either container.
These knobs restrict CPU/memory; they do not simulate network latency.

## Idle activity

`status` reports active runner commands and warns when no runner workload has
been recorded for an hour. `XORDER_IDLE_SECONDS` changes the threshold. Activity
is separate per workspace/project. A live command holds an activity lease,
so a long-running command is reported active; unlocked files left by killed
processes are ignored. Status, logs and garbage collection do not refresh the
clock. Application traffic and direct commands outside xorder are unobserved;
the idle signal does not establish that the application is unused. No stack is
stopped or deleted by this signal.

`status --reclaimable` adds read-only observations for all xorder-labelled stacks
on the selected engine. It marks missing workspaces, stopped containers, idle
runner activity and branches whose HEAD is an ancestor of the locally observed
remote default branch. `XORDER_CLEANUP_BASE` explicitly selects a comparison ref;
no network fetch occurs, so remote freshness is unknown. Default/integration
branches do not receive the merged-branch hint. Active runner commands suppress
cleanup candidacy. Each suggestion includes the actual project name and workspace
in a scoped `down` command. Inspect the reasons and Git state first: ignored synced
copies, application traffic and external commands are not proven idle. The report
deletes nothing, and it never proposes deleting worktrees or volumes. Existing
`gc` remains dry-run by default and protects all referenced image ancestry; its
source filter recognizes both exact current and historical xorder repository URLs.

### Image retention during garbage collection

The UXor runner inspects every container on the selected Docker engine, including
created/stopped containers, Serena daemons and containers started by another
runner. Their immutable image IDs remain protected regardless of project labels.
Local base images are protected through Docker's `Parent` metadata and ordered
root filesystem layer identities. Matching layer prefixes prove a shared base
filesystem; they do not prove which configuration was used as `FROM`. Equal-layer
images are therefore retained conservatively. Docker can omit `Parent` for
BuildKit/containerd images, so an empty parent field alone does not establish
that an image is unused.

Idle tool images without containers can be retained explicitly:

```sh
python3 scripts/xr.py /path/to/worktree gc --keep php-serena:my-pin --keep php-toolkit:my-pin
```

Supply actual local tags, digests or IDs; these names are examples. Repeat
`--keep` for each image. The selected image and its local base images are
protected, and an unavailable keep reference stops cleanup. The JSON report
lists protected images, unresolved references and images retained because
ancestry could not be verified. When a referenced image or its layer metadata
is missing, all local images are retained; candidates with missing layers are
also retained while an image is referenced. Incomplete list/inspect observations
stop cleanup. Malformed or unsupported layer digest formats remain unknown
metadata rather than becoming ancestry evidence.

`--apply` refreshes the full container/image snapshot before each image removal.
It uses no forced removal, and it still selects only images bearing xorder's
exact source labels. Observations cannot lock out independent Docker commands
between inspection and removal. Docker remains responsible for protecting direct
container references and retaining shared filesystem layers.

The layer interpretation follows the
[Docker image specification](https://github.com/moby/docker-image-spec/blob/main/spec.md#image-json-description)
and [Engine image inspect fields](https://github.com/moby/moby/blob/master/api/types/image/image_inspect.go).

## Bounded observations and setup reconciliation

Docker status, inspect, context, registry and other captured observations have
deadlines. `XORDER_OBSERVE_TIMEOUT_SECONDS` controls runner observation deadlines
(30 seconds by default). A timeout reports the selected engine/disk recovery route
without dumping command arguments or proxy credentials. Startup recovery probes
are bounded too; use `up` to restore the configured local engine after a restart.
Interactive workload commands and test execution keep their own existing limits.

Service recreation uses mounted startup/server inputs and effective Compose
configuration. Project PHP, CSS and test source bytes remain in the setup and run
receipt fingerprints. Changed source refreshes recipe setup, compiled Tailwind
CSS and test cache on `up` without forcing Compose to recreate healthy services.
FrankenPHP remains under its normal `--watch` mode; Caddy/INI/startup changes still
invalidate the service fingerprint. These hashes select setup work, never reuse a
previous test result.

## Service memory and OOM observations

The browser service defaults to `BROWSER_MEMORY=4g`; PHP retains
`PHP_MEMORY=2g`. These are configurable limits, not reservations or proof that
every workload fits. An existing stack keeps its actual limits until `up`
reconciles it. Check host capacity when running several stacks.

`status` shows each service's exact container ID, Docker-configured memory
limit, observed cgroup limit/current/peak, Docker `OOMKilled` flag and kernel
`oom_kill` counter. It also names `BROWSER_MEMORY` or `PHP_MEMORY` and the value
the next `up` will use. The observation reads the selected daemon's containers,
including remote engines; it never substitutes the client's cgroup or a
potentially unrelated client PID for that container.

Failures in tests and runner workloads print the same observations while
preserving the failed command's exit code. A browser child can be OOM-killed
while its container's main process survives and Docker reports
`OOMKilled=false`. The runner therefore compares cgroup OOM counters before and
after a command. Counter deltas require the same container ID and `StartedAt`;
a restart, decreased counter or missing observation makes the delta unknown.
A new Docker `OOMKilled` flag is reported separately. Existing cumulative
counters remain historical evidence, and a positive delta establishes an OOM
event in the observed window rather than proving the cause of every test error.
Failed test receipts include `memory_start` and `memory_end` before advisory
classification, alongside their existing host load and test output.

Linux cgroup v2 supplies `memory.max`, `memory.current`, `memory.peak` and
`memory.events`; cgroup v1 supplies its limit, current/max usage and OOM-control
counter. The read-only probe resolves the container process's cgroup membership
and mount rather than assuming that the mounted root always belongs to it.
The profile's existing Node runtime runs this small probe. Older kernels may
have no peak file. The brief diagnostic process itself contributes a small amount
of memory to the observed current/peak values. Stopped/removed containers,
missing Node, unreadable cgroups,
or failed daemon calls leave metrics unavailable rather than inventing zeros.
Each complete observation uses the existing observation deadline; failed
diagnostics cannot replace the workload result.

Controller semantics: [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html),
[Linux memory controller v1](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v1/memory.html),
and [Docker runtime metrics](https://docs.docker.com/engine/containers/runmetrics/).
