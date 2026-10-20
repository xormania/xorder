# Fixture results — 2026-10-20

**Decision: ready for native cloud experiments; image execution remains pending.**
The fixture works through real SDK clients on this session's Linux/x86_64
runtime. Docker, Podman, Buildah and BuildKit executables were unavailable, so
the image recipe and `verify-image.sh` have not been executed here. No registry
artifact has been published.

| Check | Observed result |
| --- | --- |
| Official SDK and hash lock | `mcp==2.3.0`; locked binary dependencies installed and synchronized on Python 3.12.14 |
| stdio and loopback Streamable HTTP, automatic negotiation | Passed; negotiated `2026-07-28` on both transports |
| stdio and loopback HTTP, legacy handshake | Passed; negotiated `2025-11-25` on both transports |
| Discovery, fresh challenge, packet and section hashes | Passed on all four client/transport combinations |
| Unknown identity, oversized argument, diagnostic error and receipt retry | Passed on all four combinations |
| Packet tampering, hook input handling, non-overwriting markers | Four focused tests passed |
| Marker across independent Python processes | Same marker bytes and hash observed after create then read |
| Claude hook payload serialization | Expected event name and diagnostic challenge emitted; unrelated input excluded |
| Shell syntax | Wrapper and image verifier passed syntax checks |
| Repository gates | Catalog check passed; 748 tests passed (11 skipped); attribution audit passed |
| Container build/runtime, offline operation, effective UID and published port | Not executed; no container runtime executable available |
| Actual outer-session MCP registration | Not executed |
| Native hook invocation and model delivery | Not executed |
| Fresh cloud session/environment reuse | Not executed |
| Authenticated remote ingress and registration | Not executed |

Retained evidence:

- [Automatic negotiation](results/native-sdk.json).
- [Legacy handshake](results/native-sdk-legacy.json).

Each report identifies the client as an SDK test client, records boot IDs and
fresh challenges, and includes hashes of the exact fixture files exercised.
The runtime was the current session's command environment; this is not a native
MCP call by its outer conversation. Native runs report UID 0 and an unrecorded
image source label; neither is evidence about the prepared image's UID or build.

Two implementation issues were found and resolved before retaining the passing
reports: SDK v2 requires an explicit `ToolError` to expose intended diagnostic
text, and ambient SOCKS proxy configuration must not intercept loopback probes.
Remote probes retain proxy support; credentials and arbitrary event bodies are
not included in the fixture reports.

## Next decisive checks

1. Build and run `verify-image.sh` on a Docker-capable cloud runner, retaining
   the source commit and image ID. The inherited base is accepted, but that does
   not verify this derivative's dependency installation or runtime behavior.
2. Use [HANDOFF.md](HANDOFF.md) in each actual cloud surface. Preserve native
   registration/tool-call evidence and report inaccessible host interfaces.
3. Exercise native diagnostic delivery, then repeat marker/configuration checks
   in a new session before any setup can recreate them.

These checks can proceed independently. Successful SDK transport is enough to
hand over the fixture; the cloud agents still own the uncertain platform tests.
