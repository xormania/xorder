# xorder MCP proofs of concept

Every PoC belongs in `mcp/poc/<poc>/`. Keep its implementation, fixtures,
instructions, and sanitized results together.

The [session plans](../docs/plans/README.md) assign separate directories and
branches so independent Sol sessions can investigate concurrently.

| Planned directory | Question |
| --- | --- |
| `core-transports/` | Can one small core serve exact context through stdio and HTTP? |
| `claude-cloud-diagnostics/` | Does a real hosted hook deliver useful guidance? |
| `work-retrieval/` | Can the actual Work conversation retrieve a packet? |
| `work-events/` | Can an external finding reach a subscribed Work conversation? |
| `codex-cloud-registration/` | Which configuration registers MCP with the actual Cloud session? |
| `jev-relevance/` | Does Jev improve context selection enough to be useful? |

Create each directory with its first implementation. Each README records status,
purpose, prerequisites, setup/run/cleanup commands, and where to inspect results.
Each `RESULTS.md` distinguishes observed native behavior from simulations and
states the next decision. An unexecuted test remains unexecuted.

PoC fixtures are experimental and do not enter the available catalog without
normal release acceptance. Promote reusable code into the main MCP implementation
after the relevant contract is proved.
