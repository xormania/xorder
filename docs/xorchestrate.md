# Xorchestrate validation preparation

The [native project runner](../examples/xorchestrate/runner.py) prepares an owned
Xorchestrate validation environment and verifies its scanner before reporting
success. It follows the UXor runner's preparation, input identity, readiness and
receipt pattern. Xorchestrate owns dependency versions and validation semantics;
Xorder supplies the explicit preparation and reuse path.

## Supported target and ownership

Use Linux or WSL2 with installed Python, uv, real tmux and Bash. The runner reads
the exact Python and uv baseline from the selected project's CI workflow and
requires matching installed executables. At the initial consumer revision those
versions are Python 3.12.16 and uv 0.13.7. It rejects an ambiguous or unsupported
workflow layout rather than substituting another baseline. It does not download
Python or select the newest package versions. Initial preparation also needs
access to the package/Git sources selected by the project's lock.

Choose one empty state directory outside the project checkout for each worktree.
The runner records its workspace ownership and creates its virtual environment,
managed profile/native configuration, bytecode-cache location, scanner-control
temporary files, run reports and preparation evidence there. It refuses a state
directory owned by another workspace or an existing nonempty unowned directory.
Concurrent preparation/check operations on the same state fail with a scoped
lock message.

This route prepares a native environment. It does not repair existing unrelated
virtual environments, refresh running containers, change image pins or install
native agent clients. Project source, dependency declarations, lockfiles and
authentication remain owned by the consumer. Running `prepare` or `check`
explicitly executes the selected checkout's project code; select a checkout you
intend to execute.

## Prepare, inspect and check

From the Xorder checkout, substituting your own absolute paths:

```sh
python3 examples/xorchestrate/runner.py prepare \
  --workspace /work/xorchestrate \
  --state-dir /work/validation/xorchestrate-main \
  --python /path/to/python3.12.16 --uv /path/to/uv --tmux /path/to/tmux

python3 examples/xorchestrate/runner.py status \
  --workspace /work/xorchestrate \
  --state-dir /work/validation/xorchestrate-main \
  --python /path/to/python3.12.16 --uv /path/to/uv --tmux /path/to/tmux

python3 examples/xorchestrate/runner.py check \
  --workspace /work/xorchestrate \
  --state-dir /work/validation/xorchestrate-main \
  --python /path/to/python3.12.16 --uv /path/to/uv --tmux /path/to/tmux
```

`--python` defaults to the Python executing the runner; `--uv` and `--tmux`
default to their names on PATH. Repeat the same selections when inspecting or
reusing a state directory. Add `--offline` after the locked packages and pinned
Git source have been cached; it enables uv's offline consistency and installation
mode. An uncached first preparation still requires source retrieval. This flag
does not itself create an operating-system network sandbox.
`--timeout` defaults to 600 seconds per preparation/static-run command, with a
maximum of 1800. `--check-timeout` defaults to 60 seconds for doctor, scanner
controls and individual static checks, with a maximum of 600. Child process groups
are stopped after completion, failure or timeout; retained command output is
bounded, with redaction for recognized credential patterns and secret environment values.

| Command | Behavior | Successful evidence |
| --- | --- | --- |
| `prepare` | Check project dependency consistency, install when needed, establish the managed profile, run project doctor, native prerequisites and real scanner controls | Current project readiness plus a clean workflow accepted and the existing deliberate-fault workflow detected |
| `status` | Inspect ownership, input identity, selected interpreter, installed distribution metadata and exact local scanner | Previous successful preparation still matches; no new project check executed |
| `check` | Require current preparation, check dependency consistency, run project doctor, native prerequisites and the project's static suite | Actual static check outcomes and reports for this invocation |

`status` uses fixed interpreter/uv/tmux/scanner probes; it does not run project hooks,
install dependencies or write preparation state. Its `readiness: previously_passed`
and `check: not_executed` fields distinguish retained evidence from a current
check. The catalog and Xorder's existing `xorder_cli.py doctor` retain their
read-only behavior.

## Dependency preparation and reuse

The runner first invokes Xorchestrate's dependency consistency check. That check
verifies `pyproject.toml`, the native `uv.lock` baseline and the generated
`.github/requirements-ci.txt` export without repairing them. Resolve inconsistent
inputs through the project's documented dependency workflow before retrying.

Fresh or stale preparation follows the project's documented locked uv route:
install the validation group first, then the locked application/test dependencies,
then install the editable project with `uv pip install --no-deps
--no-build-isolation`. Both sync stages use `--locked --no-install-project` and
the selected installed Python. The managed profile is established through
Xorchestrate's Python `setup(..., install=False)` interface; its CLI currently has
no equivalent no-install switch.

This avoids a current consumer-side mismatch: managed setup's default installer
uses pip, while the project's development `xcontracts` dependency is selected by a
uv-specific pinned Git source. Pip does not read that source selection. The
runner uses the existing uv preparation contract; it does not maintain another
dependency list or change Xorchestrate's installer.

Reuse binds preparation to dependency inputs, relevant setup/verification code,
the selected workspace/environment, interpreter, uv and platform. It also checks
installed distribution metadata and the scanner's exact version and bytes.
Unchanged compatible preparation skips dependency installation, then reruns
doctor and real scanner controls. A source edit unrelated to those preparation
inputs does not alone reinstall dependencies; `check` still runs the current
project's static suite.

Both `prepare` and `check` execute the selected Python's project-owned
`require_sqlite()` gate, which checks the SQLite version needed by the telemetry
collector. They also perform real tmux, PTY, Unix-socket and `/proc` operations.
The tmux probe uses a private socket and cleans up its own server; an executable
name or version string alone does not establish those native capabilities.

Missing or wrong Zizmor in the selected environment prevents reuse even if a
global executable exists. Actual preparation reinstalls the locked Zizmor package
to repair a missing executable even when its installed metadata remains.
Changed dependency inputs trigger preparation again
from the current lock. No latest-version upgrade or unrelated environment
refresh is implied.

## Failure and recovery

The JSON result separates preparation, project readiness and actual check
execution. `receipt.json` retains the latest successful evidence;
`attempt.json` records the selected operation before mutation. A failed or
interrupted attempt prevents an older receipt from authorizing reuse. Bounded
command evidence distinguishes installation/retrieval failures from a missing or
incompatible local scanner.

Correct the reported dependency, executable, permission or network failure and
rerun `prepare` with the same workspace, state directory, interpreter, uv and tmux.
The runner re-evaluates the owned environment and verifies it again. Recovery
does not remove sibling state directories or overwrite the project's locks.

## Native CI acceptance

The `Validate` workflow's `native-xorchestrate` job exercises the exact consumer
revision outside the Xorder checkout. It derives the Python/uv selections from
that consumer's CI configuration and provisions the exact uv-managed Python
before passing its executable to the runner. The initial hosted setup-python
3.12.16 build used SQLite 3.45.1 and failed the project's WAL gate; matching the
Python patch number alone did not establish the required SQLite capability.
The job runs fresh preparation and unchanged reuse,
then prepares a second environment from the warmed cache inside a separate
network namespace and runs the actual static suite offline. Project code in the
offline replay runs as the original user and group after namespace creation.

The `native-xorchestrate-acceptance` artifact retains the consumer revision,
dependency hashes, tool selections, user identity, namespace observations and
runner results. Runner/fixture/test changes select this job; documentation-only
changes do not repeat the native acceptance run. The required `checks` aggregate
requires success whenever the job is selected.

## Consumer handoff

The initial integration contract follows Xorder `09f1489c` and Xorchestrate
`7f226dc2`; current checkout inputs are recorded in the preparation receipt.
This is a source runner, not a new catalog resource or published image.

Consumers must route their actual worktree/session startup through `prepare`
and use `check` for current static validation. Existing entry paths and active
sessions do not adopt this route automatically. Successful scanner controls
establish the requested local scanner capability; native agent authentication,
application behavior and other test suites retain their independent checks.
