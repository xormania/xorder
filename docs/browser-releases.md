# Browser releases matched to the consuming lock

The uxor runner selects an accepted browser image whose measured
Playwright version equals the application's exact lock. An authored proposal
does not change availability or existing digest pins.

`Match consumer Playwright` checks uxor main hourly and opens a PR
when its exact Playwright pin changes. For a coordinated bump before merging
the consumer, manually run that workflow with the consumer branch or commit,
or send its `playwright-bump` repository dispatch with `consumer_ref` in the
payload. The workflow resolves that ref to an immutable commit and requires
the manifest and lock to agree. It never upgrades to an unrelated latest version.

Each runtime minor line has its own npm lock, copied and fingerprinted separately.
Changing one line does not change another line's package inputs. A patch bump
within a runtime line receives a fresh packaging revision; a new runtime minor
starts at 1.0.0. The old exact releases and pins remain usable.

Every candidate keeps RGB subpixel rendering, launches Chromium/Firefox/WebKit
offline, and compares Chromium screenshots with committed baselines at its
own pinned consumer commit and accepted application-image digest. The watcher
records that digest when preparing the proposal; later catalog updates do not
change an existing fixture or retry. Baseline updates and test retries are disabled for
that parity run. A mismatch stops acceptance and retains the report/diff files.

Merge the passing source PR, then review the normal publication/catalog PR.
After catalog acceptance, the runner discovers the matching verified digest
from the consuming Playwright pin; it needs no separate browser-version edit.
Hourly detection supports preparing a release the same day, but publication
still depends on successful CI and timely review/merge. `LIBRARY_BOT_TOKEN`
allows validation of bot-created PRs to start automatically.

To prepare the same proposal locally without pushing:

```sh
python3 scripts/refresh_browser.py --consumer-ref CONSUMER_COMMIT
```

New rendering or packaging fixes belong in a normal feature PR with a fresh
revision. The watcher proposes changed consumer versions, not repeated releases
for every consumer source commit.
