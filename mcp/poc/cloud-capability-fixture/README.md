# Cloud capability fixture

One small, repeatable fixture for Claude and OpenAI cloud investigations. It
provides a known MCP packet, diagnostic feedback, a native hook payload, and a
local persistence marker. Run it as an image or install the identical code into
an existing cloud environment. The fixture runtime needs no provider credentials.

**Status:** experimental image recipe; see [RESULTS.md](RESULTS.md) for executed
checks and remaining gaps. No published image tag or cloud compatibility is
claimed. This PoC stays outside the accepted catalog until normal promotion.

## What it measures

| Probe | Evidence | Does not establish |
| --- | --- | --- |
| MCP discovery and packet retrieval | Actual protocol, SDK, packet bytes and SHA-256 | Outer conversation registration |
| Fresh challenge and boot ID | A live response from an identified server process | Caller identity or authenticated deployment |
| Deliberate tool failure, retrieval, retry | Diagnostic reaches the client and the receipt works | Useful engineering behavior |
| Claude hook output | Event-specific `additionalContext` payload | Native hook execution or model delivery |
| Explicit marker create/read | The same bytes survive at a chosen path | Reuse by a later cloud session |

The smoke client's output labels itself `sdk-client`. Cloud agents must retain
their actual native tool call and result separately. An inner CLI is another
caller; record it as such. Use [result-template.json](result-template.json) for
comparable findings, leaving unexecuted checks `not_tested`.

## Install and run without Docker

From the repository root, with Python 3.12 or later:

```sh
PROBE=mcp/poc/cloud-capability-fixture
python3 -m venv "$PROBE/.venv"
"$PROBE/.venv/bin/python" -m pip install --require-hashes --only-binary=:all: -r "$PROBE/requirements.lock"
"$PROBE/.venv/bin/python" -m unittest discover -s "$PROBE" -p 'test_*.py'
"$PROBE/.venv/bin/python" "$PROBE/smoke.py" --output out/cloud-probe/native.json
```

The smoke check starts real stdio and loopback Streamable HTTP servers using
the pinned official SDK, then stops them. It exercises discovery, exact full
and section retrieval, unknown identities, input bounds, and diagnostic retry.
Successful observations remain in the report if a subsequent transport fails.
Loopback HTTP connects directly; remote HTTP honors normal proxy/CA settings.
Add `--protocol-mode legacy` to exercise the initialization-handshake route as
well; each observation records the actual negotiated protocol version.

For native stdio registration, use absolute paths to the venv's `python` as
the command, with `["/absolute/checkout/mcp/poc/cloud-capability-fixture/probe.py",
"serve"]` as arguments. The cloud session's native MCP configuration owns
registration; installing this command alone does not register it.

## Build and verify the image

The base is the accepted `python-dev/3.14-trixie` **1.1.4** digest recorded in
[manifest.json](manifest.json) and the repository's release record. Dependencies
are installed and hash-checked during the build, outside persisted HOME. The
base's user, CA and workspace entrypoint is preserved. The initial target is
`linux/amd64`, matching the accepted base.

```sh
PROBE=mcp/poc/cloud-capability-fixture
docker build --platform linux/amd64 \
  --build-arg SOURCE_COMMIT="$(git rev-parse HEAD)" \
  -t xorder-cloud-probe:poc "$PROBE"
PROBE_PYTHON="$PWD/$PROBE/.venv/bin/python" \
  bash "$PROBE/verify-image.sh" xorder-cloud-probe:poc out/cloud-probe-container
```

`xorder-cloud-probe:poc` is a local build tag, not a published release. Keep the
source commit, clean/dirty status and resulting image ID with results. Source
labels are declared metadata, not an independent provenance attestation.

The image verifier checks offline in-container operation, stdio from a host
client, HTTP through a published port, the default effective UID, and a retained
marker across two containers. It removes its own server and temporary state.
JSON evidence and image identity remain in the chosen output directory.

For a build intercepted by a private CA, add
`--secret id=xorder_ca,src=/absolute/session-ca.pem` to `docker build`. The
combined trust bundle exists only on a BuildKit tmpfs during installation;
it is not baked into the image. Registry access still belongs to the Docker
daemon. Runtime CA configuration uses the base's `LIBRARY_CA_FILE` contract.
See the existing [network guidance](../../../docs/usage.md#network-access).

## Use the image in a cloud session

For a stdio server managed by a Docker-capable caller:

```sh
docker run --rm -i --network none xorder-cloud-probe:poc xorder-cloud-probe serve
```

For HTTP on the current host:

```sh
docker run --rm --name xorder-probe-http \
  -p 127.0.0.1:8000:8000 xorder-cloud-probe:poc
```

The endpoint is `http://127.0.0.1:8000/mcp`. A hosted conversation cannot reach
another machine's loopback just because this command works. Use the actual
platform's supported endpoint/tunnel and registration mechanism when available.
For an explicit forwarded hostname, override the command:

```sh
xorder-cloud-probe serve --transport http --host 0.0.0.0 \
  --allow-host probe.example.test --allow-origin https://probe.example.test
```

These are example hostnames, not deployed endpoints. Host/Origin validation
stays enabled. This fixture serves synthetic data with no application auth;
authenticated remote registration is a separate untested capability. It exposes
no file access, execution, catalog mutation or arbitrary network request tools.
Keep it behind the platform's controlled ingress for remote experiments.

After native registration, have the **actual cloud agent** call
`xorder_probe_status` with a freshly chosen, non-secret `challenge`. Retain the
native call, echoed challenge, `boot_id`, packet digest and exact UI/environment
name. Then retrieve `context/poc-test-kit` at `0.0.0-poc.1`. This image's packet
hash identifies its bytes; another PoC may use the same ID with different bytes.

## Diagnostic delivery and fresh-session tests

`xorder_probe_check` deliberately returns an MCP tool error until the caller
uses the receipt described in the packet's usage section. Its diagnostic points
to the packet. A fresh task can ask the agent to run the fixture check and deal
with its result, without supplying the receipt. Retain the tool-result → packet
retrieval → retry sequence. This tests a recovery path, not a production test kit.

For native Claude command hooks, configure the native event to execute:

```sh
xorder-cloud-probe diagnostic --format claude-hook --challenge session-example
```

Use the equivalent absolute Python/`probe.py` command in a native install.
The command reads the native JSON event on stdin and derives its event name;
supported events are SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
and PostToolUseFailure. It returns advisory `additionalContext`, with no allow,
deny or blocking decision. Choose a fresh challenge and a narrow native matcher.
Do not install the same advisory on every tool event during ordinary work.

The generic `diagnostic --challenge ...` mode emits a bounded JSON diagnostic
for another surface's adapter. It does not invent an OpenAI event interface.
Calling either command manually proves serialization only. Native logs plus a
subsequent model response must establish delivery. The setup session has seen
the fixture; use a fresh session to evaluate discovery/behavior.

To investigate reuse, choose an explicitly owned path in the candidate persistent
location and run these commands in **different sessions**:

```sh
# Session A: retain the returned marker and hash externally.
xorder-cloud-probe state create --directory /chosen/probe-state --challenge reuse-01
# Session B: read before running any initializer or copying the marker back.
xorder-cloud-probe state read --directory /chosen/probe-state --challenge reuse-01
```

Creation refuses an existing marker; reading never creates one. Compare exact
hashes and check MCP configuration and tool visibility again. Record whether
Session B was a resumed conversation, a new task in the same environment, or a
new environment. Those have different reuse implications. For process restarts,
compare new `boot_id` values and stable packet identities as well.

Network availability belongs to each caller: setup host, agent runtime,
container, or remote orchestrator. Use existing xorder doctor/readiness tooling
for runtime inspection and record any targeted egress checks separately. This
fixture does not infer those capabilities from a successful loopback call.

## Cleanup, refresh and reuse

Stop a manually started HTTP container with `docker stop xorder-probe-http`.
Remove only the probe-state directory you created when its persistence trial
finishes. The native server exits when its MCP client closes stdin; the smoke
client cleans up its own processes. Neither mode edits harness configuration.

Refresh `requirements.lock` deliberately with
`uv pip compile requirements.in --universal --generate-hashes --no-annotate --no-header --output-file requirements.lock`
from this directory, and rerun transport and image checks. Packet changes require
a new computed digest and fixture revision. This fixture can be replaced with
the production xorder MCP while preserving the cloud observation procedure.
Jev integration belongs to that implementation; no recommendation-quality gate
is introduced here.

References checked on 2026-10-20:

- [MCP SDK 2.3.0](https://pypi.org/project/mcp/2.3.0/) and [transport documentation](https://py.sdk.modelcontextprotocol.io/run/).
- [Claude native hook output](https://code.claude.com/docs/en/hooks#add-context-for-claude).
- [Agentscient dev telemetry](https://github.com/uscient/agentscient/blob/91506128934b70a8967c626d6ece16d2c8a0815c/docs/runtime-telemetry.md): retain caller/process context and distinguish observed delivery from behavior.
- [Earlier Agentscient hooks](https://github.com/uscient/agentscient/tree/456457b9a0a9eb1ff285ee2d3e40535b6f722cdb/ops/devlane/hooks): native adapters and guidance history. Its MCP-only policy is not adopted here.
