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

`--wait` without a number allows 600 seconds. Waiting is bounded and does not
promise FIFO scheduling. `XORDER_TEST_WAIT_SECONDS` supplies the same default
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
for test receipts. Explicit Playwright worker arguments remain project choices.

## Idle activity

`status` reports active runner commands and warns when no runner workload has
been recorded for an hour. `XORDER_IDLE_SECONDS` changes the threshold. Activity
is separate per workspace/project. A live command holds an activity lease,
so a long-running command is reported active; unlocked files left by killed
processes are ignored. Status, logs and garbage collection do not refresh the
clock. Application traffic and direct commands outside xorder are unobserved;
the idle signal does not establish that the application is unused. No stack is
stopped or deleted by this signal.
