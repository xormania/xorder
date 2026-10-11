# Source faults and generated-copy checks

`xr sync --check` checks the current generated copies without changing them.
For UXor it runs the checkout's own `php tools/sync-demo --dry-run` and fails
when that command reports a file it would copy. The output names missing or
differing files, including ignored demo copies that `git status` cannot show.
`xr sync` performs the same project's actual sync command.

The optional `.xorder/testing.json` in the consuming checkout owns its sync
commands and named source faults. xorder does not infer recipe layouts or
maintain a second list of copied files. Without this file, UXor uses the
profile's existing sync/dry-run commands and has no named faults.

The following is an example contract; select paths, commands and literals that
match the project being tested:

```json
{
  "schema_version": 1,
  "sync": {
    "command": ["php", "tools/sync-demo"],
    "check": {
      "command": ["php", "tools/sync-demo", "--dry-run"],
      "absent": "[dry-run]"
    }
  },
  "plants": {
    "disable-example": {
      "edits": [
        {
          "path": "example/assets/controllers/example_controller.js",
          "search": "this.enable()",
          "replace": "this.disable()",
          "count": 1
        }
      ],
      "confirm": {
        "command": ["curl", "--fail", "--silent", "--show-error", "--insecure", "--noproxy", "*", "--max-time", "15", "https://localhost/assets/controllers/example_controller.js"],
        "contains": "this.disable()"
      }
    }
  }
}
```

Commands are argument arrays executed from `/app` in the same PHP service as
the tests. A custom sync object replaces the whole default object; supply its
own read-only checker. Checkers can use their exit status and optional stdout
`contains`/`absent` literal assertions. Confirmation requires `contains` and
must observe the fault in an actual page, served asset, or container query of
the code the app executes. AssetMapper may use fingerprinted asset URLs; the
project can supply a small confirmation script that discovers and fetches the
actual page asset instead of guessing its URL. Confirmation is evidence from
the project command, rather than an assumption that writing a file changed
the running app.

```sh
python3 scripts/xr.py /path/to/uxor sync --check
python3 scripts/xr.py /path/to/uxor plant --list
python3 scripts/xr.py /path/to/uxor plant disable-example --wait=120 --attest-server -- tests/e2e/example.spec.ts --project=webkit
python3 scripts/xr.py /path/to/uxor plant --restore
```

The runner acquires its normal host test budget before changing source and
holds it until cleanup ends. Every selected source must be tracked and match
Git HEAD; the helper refuses to overwrite uncommitted source work. Literal
matches must have the declared count, defaulting to exactly one. It validates
all edits before changing any file, syncs the source changes, checks the
generated copies, and confirms served content before invoking Playwright.
The normal test helper records the tests executed, the effective stack and
resolved Playwright project configuration, including its `baseURL`. That
configuration alone does not prove where a test navigated: fixtures and
individual tests can override it. `--attest-server` requests `--trace=on`; the
receipt also extracts actual request and frame URLs from readable trace
attachments. Coverage is limited to what those traces retain, and unavailable
URL evidence is recorded as unknown. The plant name is included in the receipt.
The original test exit status is preserved, so a correctly detected fault
normally returns a test failure. A failed cleanup after an already failed test
is reported separately while preserving that original failure; cleanup failure
after a passing test makes the command fail.

Cleanup restores the original clean source bytes and resyncs generated copies,
then runs the copy checker. It runs after failed tests, failed confirmation,
exceptions, Ctrl-C, SIGTERM, and SIGHUP. Source writes replace their inode so
unexpected hardlinks do not spread a plant to another worktree. A newer source
edit made during the run is preserved and reported instead of overwritten.

The helper keeps a private recovery record under the host's xorder cache until
both source and generated-copy cleanup succeed. An interrupted session, killed
process, unavailable container, or cleanup conflict leaves that record for
`plant --restore`; another plant is refused until recovery completes. SIGKILL,
host shutdown, or a second interruption during cleanup cannot promise immediate
restoration. If the runner cannot confirm that an interrupted test process has
stopped inside the container, it deliberately leaves the plant and recovery
record in place to avoid racing that process. Stop the payload before recovery.
`plant --list` needs no image or running stack; `plant --restore` needs the stack
but does not read Playwright package locks. If a newer source edit blocks recovery, preserve or reconcile that
edit before retrying. Use the same checkout, profile and project settings for
recovery, with its stack running.
