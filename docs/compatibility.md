# Execution surfaces and evidence

Claude users of `uxor-dev`: follow the [session quick start](claude-cloud.md)
for network diagnostics, disk budgeting and protected dependency reuse.

| Surface | Documented prerequisite | This library's runtime evidence |
| --- | --- | --- |
| GitHub Actions Linux amd64 | Docker engine, Buildx and Compose on the runner | Each release's record links to its actual workflow and date |
| Local Linux Docker | Registry reachability, bind mounts, Compose for services | Run the public readiness recipe; do not infer compatibility from upstream architecture support |
| Claude cloud | Docker/Compose can run custom images alongside the managed base; network access must permit pulls and dependency downloads | No live Claude session is claimed; required tests use mock consumer requirements with real Docker execution |
| OpenAI execution surfaces | Check the particular surface for an accessible engine, mounts and network; capabilities differ between products and sessions | No runtime verification claimed |
| Grok execution surfaces | Check that particular environment's engine, mounts and network | No runtime verification claimed |
| Linux arm64 | Full profile and its complete browser/native behavior must pass before publication | Not advertised initially |

Claude's [cloud environment documentation](https://code.claude.com/docs/en/cloud-environments)
describes Docker/Compose and running custom images alongside its managed base.
Custom images do not replace that base. Setup caching can preserve pulled image
files; services still need to be started in each session. Checked during planning
on 7 October 2026; vendor documentation is a claim about their platform, not an
observation of these images there. Recheck it when configuring a session.

Image pulls need both `ghcr.io` and `pkg-containers.githubusercontent.com` in
the host/daemon network allowlist. See [network and private CA setup](usage.md#network-access);
registry access and in-container dependency access are separate prerequisites.

Setup: pre-pull selected digest references and download locked project
dependencies where the platform allows. Session startup: mount the current
project, start required service containers and run commands in the development
container. Run `docker info` in the actual session before assuming that a
preinstalled client can reach an engine.

This implementation workspace has no usable Docker engine. Container validation
runs on GitHub Actions; records are only written after those real tests pass.
A live Claude/cloud-agent observation is optional and never a release gate.
Do not describe deterministic selection tests as a model acceptance test.

When an actual cloud run occurs, add its date, image digest, surface, prerequisites,
commands, observed results and limitations in a source PR. One session's failure
does not establish a restriction across every product from the same vendor.
