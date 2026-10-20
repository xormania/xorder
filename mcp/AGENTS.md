# Working on xorder MCP

Follow the root `AGENTS.md`. Read [scope](docs/scope.md), the
[session index](docs/plans/README.md), and the specific plan assigned to the
session. The [design reference](docs/plans/design-reference.md) is supporting
material, not a requirement to implement every proposed tool before a PoC.

The maintainer selected `mcp/` as the development root,
`mcp/docs/scope.md` for scope, `mcp/docs/plans/` for specific planning documents,
and `mcp/poc/<poc>/` for every proof of concept.

Use the assigned PoC directory and a separate branch/worktree for concurrent
sessions. Integrate their PRs into `feat/xorder-mcp`; promotion to `master`
is a later integration decision. Coordinate changes to shared files rather
than overwriting another session's work.

Local and cloud delivery are both goals. Reuse the existing xorder resource
model. Distinguish documented support, isolated simulation, and native observed
behavior. Record actual-session registration and useful model delivery separately
from server startup. A missing target capability is a finding to investigate,
not permission to redefine the whole project as local-only.

Prioritize the plan's first decisive experiment. Report an exact blocker or a
negative result promptly; do not spend the session building unrelated framework
pieces to avoid testing the uncertain capability. Reuse legacy mechanisms with
current project wording.
