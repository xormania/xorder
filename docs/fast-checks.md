# Fast static checks

`Validate` calls `Fast static checks / fast-checks` on every PR and includes its
result in the existing required `checks` aggregate. No ruleset update is needed
to prevent merging when a fast check fails. It also runs on pushes to master,
weekly, and manually. It replaces the separate Bandit workflow and requires no
Codacy account, project token or paid scanner Action. Its job has read-only
repository access and does not retain checkout credentials.

The initial target is **90 seconds for tool setup, scanner canaries and checks**.
The timer starts before Python setup. Runner queues/provisioning, checkout and
artifact upload are outside this target. An overrun is reported, not hidden or
treated as a clean scan failure; the job has a five-minute infrastructure timeout.
Behavioral/container tests keep their separate existing requirements and timing.

## Scope and gates

| Check | Inputs | Blocking result |
| --- | --- | --- |
| ShellCheck | Maintained `.sh` files and shell shebangs | Unreviewed warning/error |
| Hadolint | Every maintained `Dockerfile`, including shell in RUN | Unreviewed warning/error |
| Ruff | Every maintained Python file | Explicit `F` and `E9` correctness rules |
| actionlint | GitHub workflow YAML, including inline shell via ShellCheck | Any unreviewed diagnostic |
| zizmor | Workflow, action and Dependabot configuration under `.github` | Regular-persona findings; malformed input fails |
| Bandit | Every maintained Python file | Unreviewed medium/high severity **and** medium/high confidence |
| Gitleaks | All fetched Git history and the working directory | Any secret finding |

Source enumeration includes tracked files and nonignored new files, so local
checks cover work before staging. No generated-directory exclusion disables
secret detection. All scanner reports and timings are retained in
`out/fast-checks/`; CI uploads them for fourteen days, including after check
failure. Gitleaks reports redact secret values completely. Bandit advisory
findings remain in `bandit.json`. Missing tools, timeouts, malformed reports,
Bandit parse/plugin errors and stale exceptions fail the check.

zizmor uses offline analysis with strict input collection. This keeps PR scans
deterministic and fast; online vulnerable-action/stale-reference audits are not
included. actionlint 1.7.12 lacks GitHub's supported `concurrency.queue` field;
two path-specific diagnostic exceptions preserve existing release queue behavior.
The workflow-local reusable call retains the same-commit `./` syntax while this
actionlint version lacks GitHub's newer `$/` syntax; its zizmor exception is
limited to that call.

## Local use

The currently verified binary installer targets Linux/amd64 with Python 3.12.
Use an isolated environment outside the repository so dependencies are not scan
inputs:

```sh
python3 -m venv "$HOME/.cache/xorder-checks"
"$HOME/.cache/xorder-checks/bin/python" -m pip install -r requirements-checks.txt
python3 scripts/setup_checks.py --bin-dir "$HOME/.cache/xorder-checks/bin"
PATH="$HOME/.cache/xorder-checks/bin:$PATH" python3 -m unittest discover -s tests -p test_fast_checks.py -q
PATH="$HOME/.cache/xorder-checks/bin:$PATH" python3 scripts/checks.py --budget-seconds 90
```

Python tools and their dependencies are pinned in `requirements-checks.txt`.
Standalone tools use exact release URLs and SHA-256 checksums in
`checks/tools.json`. The installer verifies archives before reading the one
declared regular binary member; it does not extract archive paths. No image
installation or rebuild is needed to use these checks.

## Reviewed exceptions

`checks/*-exceptions.json` records the specific finding, rationale and source
identity. ShellCheck/Hadolint bind path, rule, line and line hash. Bandit binds
path, rule and normalized scanner snippet hash. All three also bind the complete
source file hash. Each exception accepts at most one finding. Changed source,
duplicate findings or removed findings require review and an explicit exception
update; do not regenerate exception lists automatically to make CI green.

Current exceptions cover deliberate fixture behavior, empty CDPATH assignments,
container-only paths/listeners, and Dockerfile policies already exercised by
behavioral checks. Low-level Hadolint package pinning advice does not override
the documented Debian package-feed refresh policy. Production URL calls use
individual B310 annotations after verifying HTTPS construction or explicit
HTTP/HTTPS scheme checks. Bandit permits assertions only in `tests/test_*.py`
unit modules; executable fixtures and production scripts retain assertion checks.

Gitleaks extends its default rules. Its single added exception requires both a
generated catalog/release-record path and the exact `build_key` SHA-256 JSON
field shape. Adjacent credential fields remain scanned. A real-tool canary
verifies this using synthetic data, alongside tests that scanner failures and
changed/duplicate exceptions cannot produce a passing result.

## Maintenance and reuse

Dependabot tracks pinned Actions and Python requirements. Standalone binary
updates require a PR updating the release version, URL and checksum together,
followed by the canaries and full checks. Tool pin/config changes do not change
released image bytes. Existing conservative runtime-test selection still applies
when shared runtime helpers or validation workflows change.

The local commands are the initial reusable interface. A distributed Actions
library can package verified behavior after downstream testing; this change does
not advertise an unverified new catalog resource or reusable workflow contract.

Upstream references:

- [ShellCheck](https://github.com/koalaman/shellcheck)
- [actionlint checks](https://github.com/rhysd/actionlint/blob/main/docs/checks.md)
- [Ruff](https://docs.astral.sh/ruff/)
- [Hadolint](https://github.com/hadolint/hadolint)
- [zizmor audit rules](https://docs.zizmor.sh/audits/)
- [Bandit command reference](https://bandit.readthedocs.io/en/latest/man/bandit.html)
- [Gitleaks CLI and configuration](https://github.com/gitleaks/gitleaks)
