# Agent software engineering enablement

xorder provides a short route from project requirements to a prepared, verified
capability and a reproducible task. Start with the [capability guide](capabilities.md),
then use [current exact releases](../discovery.json), the selected usage page and
its readiness check. Detailed inventories and release history stay linked for
questions that require them. No particular agent harness is required for discovery.

## Choose from general to specific

| Layer | Choose it when | Project remains responsible for |
| --- | --- | --- |
| General base/toolchain | Language CLI and build/test tools are enough | Dependency locks, application packages, data and services |
| Framework | HTTP/worker or native framework environment is required | Caddy/app configuration, service URLs, application lifecycle |
| Task | Browser, coverage, analysis, code navigation or recipe testing is needed | Task configuration, exact dependency versions and expected outcomes |
| Project | The repository has an accepted concrete layout and runner | Source checkout, project locks and intentional project settings |
| Independent support | A specific binary, configuration or context is selected | Destination ownership, activation scope and harness applicability |

Use the project's existing compatible pins. A newer available release is a
candidate to evaluate; it does not update a profile, installed resource or image
implicitly. Browser libraries and companions must match the consuming lock.
Authored groups can point to a planned resource, but generated available entries
come only from verified releases. Groups do not supply inheritance or merge
configuration behind the user's back.

## Observe, select, prepare, verify, recover

1. Inspect project lockfiles, runtime constraints, required services and test commands.
2. Inspect the execution environment. After cloning xorder, an optional bounded
   diagnostic is `python3 scripts/xorder_cli.py doctor --workspace /path/to/project`.
   Add `--resource ID --version REVISION` to inspect one release's prerequisites.
   It reports actual command presence, disk space, lockfile presence and fixed
   Docker engine/Compose probes. No downloads, installs or project hooks execute.
3. Select exact identities from the current index, or retain an accepted existing
   pin. Resolve a reusable profile against observed target facts when useful.
   The doctor output's `target` is a partial observation: add inspected harness
   and scope facts before resolving context assignments. Check network paths
   separately; a successful registry pull does not prove dependency archive access.
4. Follow the selected usage page. Prepare project dependencies using their own
   locks once, or import authenticated matching bytes. For shared worktrees,
   follow the [read-only dependency reuse recipe](claude-cloud.md).
5. Run the resource's readiness recipe and the project's checks. Report failed
   conditions and the scoped evidence needed to reproduce them.
6. Follow the runner's documented recovery command. Healthy sibling stacks,
   unrelated files and intentional retained image pins have separate ownership.

Doctor returns `facts_observed` after its observations succeed; that status is
not an application readiness result. Presence of a lockfile does not validate
its contents. Installed file receipts establish owned bytes, while running code
and services need their independent checks. Docker engine observations may
refer to a remote engine; host filesystem space does not measure that engine's
image storage. HTTP, proxy and certificate behavior must be checked on the
actual route in the current execution environment.

## Extend the catalog with a proven use case

Put reusable tools in the lowest suitable resource layer. Put project orchestration
in a profile/runner and link its applicability, prerequisites, usage, readiness and
recovery. Keep selection metadata in `discovery/organization.json`; changing a
navigation label does not alter released software. Keep measured runtime facts in
the verified release ledger and generate every discovery view from the shared model.

For a concrete task, prefer one reproducible successful example with its exact
inputs and expected observable result. Repeated failures should improve the
shared preparation or diagnostic route and one meaningful regression check.
Deterministic checks establish published behavior; observations of fresh agents
using it establish how effectively the guidance enables actual work. Follow the
[agent evaluation guide](agent-evaluations.md) to record setup/recovery observations
separately from deterministic artifact acceptance.
