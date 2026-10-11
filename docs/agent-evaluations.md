# Optional real-agent evaluations

The public URL is an interface used by agents. A deterministic resolver or
container fixture cannot establish that a fresh model discovered the right
resource, completed its first task, or recovered from a missing prerequisite.
This separate, opt-in evaluator runs an explicitly configured harness and checks
its resulting artifacts independently. It does not add vendor credentials,
model calls, or a live-agent requirement to ordinary CI or image publication.

## Scenarios from generic selection to a concrete task

| Scenario | Agent task | Independent evidence | Scope |
| --- | --- | --- | --- |
| `url-discovery` | Find the least specialized available PHP 8.5 CLI image from the public URL | Acquired README, catalog and usage bytes match the evaluated commit; resource revision, digest and readiness recipe match accepted release facts | URL content and selection; no image pull |
| `first-task` | Discover that image and execute a small PHP task | Inspect the real stopped container's exact image, command, entrypoint, platform and read-only fixture; verify its successful task output | Actual Docker execution, not a full Symfony application |
| `missing-prerequisite` | Check engine readiness and report the missing prerequisite before a pull | A controlled unavailable-Docker shim records the readiness call; no pull/run/create/build call; precise blocker and recovery command | Real agent behavior under a synthetic prerequisite failure |
| `warm-reuse` | Seed a second checkout from matching locks and prepared trees | Donor and receiver locks and dependency bytes match the supplied fixture; unrelated receiver state remains; donor runtime state is excluded | Prepared-tree seeding with tiny synthetic dependency bytes; not proof of a real Composer/npm install or warm app stack |

The last two scenarios make their controlled conditions explicit in the prompt
and observation. They supplement actual cloud-session feedback. They do not
assert that a provider's real proxy, disk quota, Docker daemon or project
dependency tree behaves like the fixture.

The missing-engine trace records argv as JSON with conventional credential
values redacted. Its postcheck parses supported Docker global options before
identifying the command, permits known read-only diagnostics, and rejects
ambiguous or unrecognized operations. A global option cannot conceal an
attempted pull, container run or build.

## Configure and run

Use Python 3.10+ on a POSIX host and install `requirements-ci.txt`. Configure a
non-interactive wrapper for the harness you actually use. The evaluator does
not assume vendor CLI flags or a particular authentication method. The wrapper
must read the supplied prompt file, invoke the configured model with the supplied
working directory, and wait for task completion. It must preserve the evaluator's
environment, especially `PATH` for the controlled missing-engine scenario.

An adapter JSON file, stored outside the repository, has this shape:

```json
{
  "name": "my-cloud-agent",
  "harness": "installed-harness-name",
  "model": "explicit-model-configuration",
  "command": ["/absolute/path/to/agent-wrapper", "{prompt}", "{workspace}", "{result}"],
  "version_command": ["/absolute/path/to/agent-wrapper", "--version"]
}
```

Commands are argv arrays, executed without a shell. `{prompt}`, `{workspace}`
and `{result}` are substituted as individual argument text. The same paths are
available as `XORDER_EVAL_PROMPT`, `XORDER_EVAL_WORKSPACE` and
`XORDER_EVAL_RESULT`. Credentials belong in the harness's normal credential
mechanism, never literal command arguments. The version command should report
the actual installed harness version; the configured model is recorded
separately from an observed model, which remains unknown unless independently
instrumented.

Select a **published repository commit** so the public URL is retrievable. No
local source checkout, catalog or expected digest is mounted into the agent's
working directory. The evaluator privately reads committed source bytes for its
postchecks. For example:

```sh
python3 scripts/agent_eval.py run tests/scenarios/url-discovery.json \
  --adapter /absolute/path/to/adapter.json \
  --source-commit PUBLISHED_COMMIT \
  --output /absolute/path/to/observations/discovery.json \
  --human-interventions 0
```

Use the same command with another scenario filename for later stages. The
`first-task` scenario needs a reachable Docker engine and permission to pull the
accepted image. It runs a network-disabled task container and removes that
container after inspection. The evaluator only removes a container bearing its
unique run label; an unavailable cleanup is explicitly recorded. `warm-reuse`
needs a source revision that contains the seed helper and uses default private
copies, so it does not need Docker for hardlink safety checks.

Each run creates a unique directory beside the observation file. The agent
starts there with its task prompt, task fixtures where needed, and empty
evidence destinations. This isolates checkout state; it is not an operating
system sandbox. Use a disposable evaluation environment for the live lane.

The harness deadline defaults to 10–20 minutes per scenario and can be overridden
with `--timeout`, up to one hour. Version and Docker observations have separate
short deadlines. On completion, timeout or an interrupt, the evaluator terminates
the adapter process group, including attached background children. Adapters
must not detach children into a new session. SIGTERM and Ctrl-C produce an
interrupted observation when the evaluator can finish cleanup.

## Read the observation precisely

- **Pass / exit 0:** the adapter completed successfully and every independent
  postcheck passed.
- **Fail / exit 1:** the task deadline elapsed, or a completed adapter produced
  missing, inconsistent or failed task evidence.
- **Indeterminate / exit 2:** the harness/prerequisite was unavailable, the
  adapter exited unsuccessfully before usable task evidence, or the operator
  interrupted the run. This does not diagnose a model failure.

The observation binds the scenario hash, repository commit, acquired catalog
hash, resource identity and existing public release-verification evidence.
It records harness version when the version probe succeeds, configured model,
elapsed evaluator time, filesystem free space, logical workspace file size and
host load before and after. Elapsed time includes preflight and postchecks;
filesystem free space is not a provider quota or Docker image-store measurement.

Human interventions are **operator-reported** through `--human-interventions`;
omit that option when the count is unknown. Total network download bytes are
currently **unmeasured**, recorded as `null`, rather than inferred from image
size, file size or a model's claim. Vendor-specific network/model instrumentation
can be added to an adapter when there is trustworthy evidence for it.

Raw harness stdout/stderr are drained with bounded memory, hashed and counted,
but not stored or printed. Adapter argv, credentials and environment contents
are not written to the observation. The short version line redacts known secret
environment values. Retained working directories may still contain files the
harness itself wrote; inspect those files before sharing evidence. Remove the
run directory after review when it is no longer needed. Already-existing
observation files are never overwritten.

```sh
python3 scripts/agent_eval.py validate /absolute/path/to/observations/discovery.json
```

Validation checks structure and internal consistency. It does **not** replay
the Docker/evidence postchecks, authenticate an imported report, or turn a
handwritten claim into observed success. A single run is an observation, not an
aggregate reliability or performance estimate. Compare repeated runs using the
same source, task, harness/model configuration and execution conditions.

The hermetic tests in `tests/test_agent_eval.py` use scripted doubles to exercise
postcheck rejection, unavailable harnesses, timeout cleanup and bounded output.
They are not vendor runs. No real vendor or Docker success is claimed by adding
this evaluator; collect those observations explicitly through the commands above.
