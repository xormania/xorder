# Local test attempts and evidence

`examples/uxor/run.sh test` writes a separate run receipt for every launched
Playwright command. It does not reuse a previous test result. The host path is
printed after the command and is under
`$XDG_CACHE_HOME/xorder/test-attempts/<run-id>/receipt.json` (the cache defaults
to `$HOME/.cache`). Each attempt has a new identifier; existing receipts are
never replaced. The receipt is made read-only after it is written.

```sh
bash examples/uxor/run.sh test --wait tests/e2e/example.spec.ts
bash examples/uxor/run.sh test --wait=120 --measure tests/e2e/example.spec.ts
bash examples/uxor/run.sh test --attest-server tests/e2e/example.spec.ts
```

`--wait` allows up to 600 seconds for the shared run budget by default; supply
a nonnegative number to choose the limit. `--measure` requests the quiet-host
measurement lease. These options are removed before Playwright sees its
arguments. `XORDER_TEST_WAIT_SECONDS` and `XORDER_TEST_MEASURE=1` provide the
same settings for session wrappers. An explicit Playwright worker setting is
retained. The quiet-host threshold is advisory about observed load; unrelated
processes can still affect timing while a test runs.

The receipt separates requested filters from observed execution. A companion
reporter records test identifiers, titles, source locations, projects, retry
numbers, result status and duration from Playwright events. Selected or listed
tests are not invented as executed tests. Skipped results retain their skipped
status. An interrupted attempt retains its observed beginnings and marks
unfinished results as unknown.

Interrupted execution stops the in-container test process group before a plant
can restore source. If that stop cannot be confirmed, cancellation retains exit
130 and signals the plant workflow to leave its recovery journal and defer
restoration. Receipt or log storage failures also retain the original test exit.

The reporter records each resolved project's `use.baseURL` and the actual
container's `DEMO_URL` separately. These establish the selected configuration;
they do not prove every browser request used that URL. A test-level fixture
override or an absolute navigation URL can differ. Actual navigation URLs are
therefore unknown unless readable trace attachments establish them. The runner
reads actual request URLs and frame snapshot URLs from existing trace attachments
without changing normal tracing settings. It does not treat a requested
`page.goto` argument as proof of a completed navigation.

`--attest-server` (or `XORDER_TEST_ATTEST_SERVER=1`) explicitly adds the documented
Playwright `--trace=on` option to capture traces for passing attempts too. An
explicit conflicting CLI trace mode is rejected. Tracing adds runtime and disk
cost; trace artifacts can contain page contents, network bodies and credentials.
The receipt records the trace hash and source path and extracted URLs; it does
not duplicate the whole archive. Unavailable or oversized trace files are marked
unknown. The parser follows the [1.58.2 trace recorder](https://github.com/microsoft/playwright/blob/v1.58.2/packages/playwright-core/src/server/trace/recorder/tracing.ts)
and [trace types](https://github.com/microsoft/playwright/blob/v1.58.2/packages/trace/src/trace.ts).
Missing reporter events and incomplete
runs are reported visibly and in the receipt; the original test exit is retained.

The companion uses Playwright's additive `PW_TEST_REPORTER` extension, verified
in the [1.58.2 runner source](https://github.com/microsoft/playwright/blob/v1.58.2/packages/playwright/src/runner/reporters.ts).
It leaves the consuming project's config file, reporters, output destinations,
tests and hooks intact. If the container already has a `PW_TEST_REPORTER`, that
extension is preserved and companion evidence is reported unavailable. A future
Playwright version that stops supplying these events likewise yields unknown
evidence, never synthetic success.

Start/end UTC times, elapsed time, exit code and host resource observations
accompany effective arguments and application/browser identities. The input
fingerprint includes current project source bytes, including TypeScript specs,
the workspace/profile fingerprint, effective stack configuration, arguments,
images and observed environment. The effective Compose configuration is hashed;
its raw environment, which can contain proxy credentials, is not saved. This
fingerprint is evidence for later analysis, not a test-result reuse decision.

Full combined test stdout/stderr and the app/browser logs between the attempt's
start and end are stored beside the receipt. `diagnostic_context` includes the
last 64 KiB of each for a failure adapter. A missing log observation is explicit.
An optional `XORDER_TEST_FAILURE_HOOK` runs after a failed receipt is finalized;
its advisory outcome is stored separately and cannot turn a failed test green.
The receipt files are local execution artifacts and may contain application
output; treat them like the consuming project's test reports.

The internal `run_test(..., workers=...)` executor acquires no lease. Operations
that already hold the heavy-run lease, such as a fault-plant workflow, can use
the same receipt-backed execution without acquiring a second run slot.
