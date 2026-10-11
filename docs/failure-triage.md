# Optional local failure triage

An optional project-owned advisory command can receive the immutable receipt for
a failed `xr test` attempt. It runs after the receipt is finalized and cannot
replace the test's exit code. Passing attempts do not invoke it. The runner
supplies the attempt's bounded test output and server logs under
`diagnostic_context.test_output` and `diagnostic_context.server_logs`; the server
log window uses the attempt's UTC start and end, rather than unrelated old logs.
Unavailable logs and truncated excerpts remain receipt evidence to inspect.

Set `XORDER_TEST_FAILURE_HOOK` to a JSON argument array. Arguments are passed
directly to a host process with no shell; the working directory is the consumer
workspace. The receipt JSON is stdin. An adapter returns advisory JSON or text
on stdout. Hook stderr is suppressed, and the recorded status reports command
failure, invalid configuration, unavailability or timeout without changing the
failed test's result. No hook is selected by default.

```sh
export XORDER_TEST_FAILURE_HOOK='["python3","/path/to/project/tools/failure-triage.py"]'
export XORDER_TEST_FAILURE_HOOK_TIMEOUT=30
```

The timeout defaults to 30 seconds and accepts 1 through 300. Input is limited to
1 MiB; advisory output retains at most its final 16 KiB in memory. The runner
stops the hook's process group on timeout and completion. A hook receives the
receipt's bounded excerpts, not a request to read entire spool files. The immutable
receipt and full local logs remain the evidence; a classification is a candidate
explanation for further investigation.

## Jev adapter

The supplied optional adapter selects a candidate category using TypeSafe's
documented HTTP Choice API. It reports the returned model, choice, confidence and
full probability distribution. It does not request generated prose or claim to
prove a root cause. The bundled candidates cover application behavior, test
synchronization, resource load, environment, dependencies and insufficient evidence.

```sh
export TYPESAFE_API_KEY='your-key'
export XORDER_TEST_FAILURE_HOOK='["python3","/path/to/xorder/examples/jev/failure_triage.py"]'
# Optional: an exact supported Jev version instead of the current provider alias.
export XORDER_JEV_MODEL=jev-latest
```

Opting into this adapter sends bounded receipt context to TypeSafe and uses its
API account. It redacts values from environment variables whose names contain
KEY, TOKEN, SECRET, PASSWORD, PASSWD or CREDENTIAL, plus common authorization,
password and URL-credential forms. This is a best-effort filter; use a
project-owned adapter when logs need additional redaction or data selection.
Keys stay in the host environment and are never included in the receipt or
printed by this adapter. The default xorder runtime makes no Jev request.

To reuse project-specific candidate categories, set `XORDER_JEV_QUESTIONS` to an
absolute path containing the question map in
[failure-questions.json](../examples/jev/failure-questions.json). Each question
uses `type: choice`, `instructions`, and 2–255 named `criteria`. These project
questions determine candidate selection independently of runner orchestration.
Missing credentials, request errors or malformed responses return an unavailable
advisory; the original test remains failed. The API call has a 15-second timeout,
a 256 KiB response limit and no cross-endpoint redirects.

A receipt can also be classified after a run:

```sh
python3 /path/to/xorder/examples/jev/failure_triage.py < /path/to/run-receipt.json
```

Provider contract: [TypeSafe API reference](https://docs.typesafe.ai/api) and
[Choice](https://docs.typesafe.ai/primitives/choice). The endpoint is
`POST https://api.typesafe.ai/v1/systemone`, authenticated with a Bearer key, with
`state`, `model` and `questions`. The adapter uses the standard library rather
than assuming a particular third-party Jev CLI or command-line flags.

Runner log-window contract: [Docker Compose logs](https://docs.docker.com/reference/cli/docker/compose/logs/)
supports `--since` and `--until` UTC timestamps.
