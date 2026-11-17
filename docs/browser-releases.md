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

The consumer lock is a version demand signal. Preparing or accepting a browser
image does not require an application image or an application test suite.
Xorder verifies the browser image's capabilities with its own small subjects;
the consuming project tests its application and screenshot baselines against
the selected image digest.

Each runtime minor line has its own npm lock, copied and fingerprinted separately.
Changing one line does not change another line's package inputs. A patch bump
within a runtime line receives a fresh packaging revision; a new runtime minor
starts at 1.0.0. The old exact releases and pins remain usable.

The npm closure and all three downloaded engine payloads are retained in an
independent build component for that runtime line. The component records its own
exact Node donor. The final browser image copies those bytes and installs only
the engine OS dependencies, user handling, and RGB font configuration. A runtime
base or Debian package refresh therefore reuses the completed payload without
fetching the browser archives again. Updating the consumer's Playwright pin
refreshes that line's payload component; another minor line keeps its existing
component and lock. This component reuse does not replace the final image's
owned offline all-engine rendering and interaction checks.

Every candidate keeps RGB subpixel rendering and launches Chromium, Firefox and
WebKit without network access. The owned fixture checks DOM interaction, layout,
font availability and rendered screenshot pixels. Verification runs against the
public candidate digest on an anonymous runner with no registry login or
publication token. Finalization requires evidence bound to that digest, image
inputs and every owned fixture file; a failing check prevents acceptance.
Historical published releases retain their original verification records.

The previous UXor application parity fixture remains available for explicit
compatibility investigation during migration. It is separate from image
readiness and publication. Its consumer commit, accepted application image,
application configuration and screenshot baselines belong to the consuming
project's compatibility check. Existing legacy fixtures retain their complete
application pins. New files under `tests/fixtures/playwright/consumers/` are
version-demand provenance only; they deliberately contain no application image
and cannot serve as legacy parity inputs.

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
