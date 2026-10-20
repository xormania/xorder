# xorder MCP

Development home for xorder's MCP server, context packets, Jev recommendations,
and diagnostic delivery. **Local and cloud use are both in scope.**

**Development branch:** `feat/xorder-mcp`.

**Status:** scope and work plans, plus a runnable
[cloud capability fixture](poc/cloud-capability-fixture/README.md). Its image
build and native cloud acceptance remain to be exercised; see its results.

## Start here

1. Read [scope](docs/scope.md).
2. Choose a session from the [parallel PoC plans](docs/plans/README.md).
3. Create its work branch from `feat/xorder-mcp` and work in its named PoC directory.
4. Return early feasibility evidence, then a PR to `feat/xorder-mcp`.

| Path | Purpose |
| --- | --- |
| `mcp/` | MCP implementation, packaging, configuration, and deployment |
| [docs/scope.md](docs/scope.md) | Purpose, capabilities, boundaries, and completion criteria |
| [docs/plans/](docs/plans/README.md) | Specific plans for independent implementation sessions |
| [docs/research/cloud-readiness.md](docs/research/cloud-readiness.md) | Research findings and cloud acceptance context |
| [poc/](poc/README.md) | Every experiment under `mcp/poc/<poc>/` |

The first objective is evidence that this saves repeated explanation and works
in actual cloud sessions. Prove retrieval and useful automatic guidance with a
small fixture before building the full proposed tool set.

Reuse the existing catalog and `scripts/xorder/` model/resolver. Context resource
definitions remain in `artifacts/context/`; a PoC fixture does not become an
accepted catalog release.

The root [contributor guidance](../docs/contributing.md),
[architecture](../docs/architecture.md), and [AGENTS.md](../AGENTS.md) apply.
Run the repository checks required there plus the selected plan's focused
behavior checks. Passing repository checks alone does not prove cloud readiness.
