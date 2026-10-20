# Session A: minimal shared core and MCP transports

**Work branch:** `poc/mcp-core-transports`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/core-transports/`.

**Handoff:** runnable server, fixture, typed contract, and `RESULTS.md`.

## Question and first result

Can one small xorder operation layer return an exact packet through both stdio
and Streamable HTTP using real MCP clients? Produce that result before building
the larger proposed tool set.

Read [scope](../scope.md), the [session index](README.md), root repository
guidance, and existing `scripts/xorder/` catalog/resolution code.

## Work

1. Check the currently available MCP SDK and supported protocol versions.
   Prefer reuse of xorder's Python operations if it is the shortest sound path;
   do not introduce another framework merely to run the fixture.
2. Create the experimental packet and marker described in the session index.
   Record exact UTF-8 bytes, version, and computed digest. Keep fixture lookup
   explicitly distinct from accepted catalog releases.
3. Implement the smallest typed `xorder_catalog_search` and
   `xorder_context_get` operations needed for navigation and retrieval.
   Search should also expose a bounded selection from the existing xorder
   catalog. Preserve its exact identities and lifecycle facts.
4. Bind those operations to stdio and Streamable HTTP through the SDK.
   Keep transport setup separate from catalog/packet logic.
5. Drive both transports with actual MCP client calls, including tool discovery.
   Compare returned packet identity and content.
6. Add configurable endpoint/catalog/cache locations, bounded output and request
   handling, and a documented remote authentication integration point.
   Exercise a suitable supported authentication mechanism before calling an
   externally exposed authenticated deployment ready.

## Acceptance

- Real discovery and retrieval work over both transports.
- The same selected bytes produce the same exact identity.
- An unknown packet/version or failed integrity check is an explicit error.
- Responses are bounded and do not silently truncate content.
- Catalog reads do not apply resources or mutate consumer files.
- Logs stay off stdio protocol output and do not contain credentials.
- A restart preserves the intended selected packet/configuration behavior.

Retain the client requests/results and exact SDK/protocol versions. HTTP working
on localhost is transport evidence, not hosted-session registration.

## Deliverables and coordination

Provide a README with install/run/cleanup commands, dependency pins, fixture
manifest, output schemas, and `RESULTS.md`. Publish the invocation and endpoint
contract in the PR so B–E can adopt it. Keep code in the assigned PoC initially;
propose promotion into main `mcp/` after the integration result.

B–E may use small disposable stubs meanwhile. Coordinate schema changes and
rerun successful host paths against this implementation after integration.

## Early decision

If dual transport works, make the server usable by other sessions immediately.
If the chosen SDK/version fails, retain a minimal reproduction and test one
supported version/transport alternative. Avoid implementing a transport protocol
from scratch before proving that the SDK route is unsuitable.

Run focused transport/operation checks and the root-required repository checks.
Return a PR to `feat/xorder-mcp`; do not merge it.
