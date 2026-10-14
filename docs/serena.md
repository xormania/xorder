# Prepared Serena for PHP and Symfony

`php-serena/8.5-trixie` adds Serena v2 REPL, PHPactor and JavaScript/TypeScript tooling to xorder's PHP 8.5
development image. It is an independent stdio MCP service for source discovery
and editing. The [catalog](../catalog-v2.json) is the availability authority:
the authored image is not available until publication and verification produce
an accepted release record. No image is pulled automatically during MCP startup.

The prepared source remains Serena commit `b79e2a55f9d4072084977dd35bd07d31146d88b9`.
The dependency-only [security patch](../images/php-serena/security.patch) and
[effective uv lock](../images/php-serena/security-uv.lock) pin AnyIO 4.14.2 and
PyJWT 2.14.0, the fixes identified by the publication scan. The build checks the
original upstream lock hash before applying the patch, then installs the effective
closure with `uv sync --locked`. Inventories identify the upstream and effective
lock hashes separately. Source edits, lock changes, and installed dependency
versions must pass the normal image behavior and publication assurance gates.

## Use with uxor

Select an available `image/php-serena/8.5-trixie` entry from the catalog, pull its
exact digest, and retain it in the MCP client's configuration. Configure the
client to launch this command, supplying absolute paths and the selected digest:

```sh
python3 /path/to/xorder/examples/serena/run.py /path/to/uxor \
  --project . --image "$SERENA_IMAGE"
```

Use one project selection per worktree. For uxor, use `--project .` to
activate the checkout root and include original recipes, controllers and demo
source. Paths below are relative to that root. `--project demo` remains useful
for demo-only PHP inspection, with paths relative to `demo`, but switching
between `.` and `demo` creates separate index caches and pays for two cold indexes.
The runner mounts the whole checkout at `/workspace` in either case.
Install dependencies from the consuming application's own Composer lock with its
normal development runner before using Serena. This image does not supply a
substitute application `vendor/`. Existing uxor app/browser images and
their launch configuration remain useful independently.

The image defaults to the persistent `serena_repl` interface. Call
`initial_instructions` first, then pass its issued session ID as `session` on every
`serena_repl` call, with Python in `code`. For example, within one Serena session:

```python
s.info('lsp.find_symbol', 'lsp.find_referencing_symbols')
s.lsp.find_symbol('CspNonce', relative_path='demo/src/Security/CspNonce.php')
s.lsp.find_referencing_symbols('CspNonce', 'demo/src/Security/CspNonce.php')
```

Use upstream API discovery for the selected revision. The REPL retains variables
between cells. A failed cell may already have edited source: inspect its textual
error and the resulting files before retrying. Reconnecting starts a new REPL;
variables and temporary memories are lost, while source edits remain. Optional matching indexes survive.
There is no automatic replay of a failed or interrupted cell.


## Shell queries and persistent editing

These additions require the new 1.1 image after publication and acceptance; an older digest does not gain new binaries or launcher options. Shell access uses the same MCP service and needs no harness MCP registration:

```sh
python3 examples/serena/client.py query find_symbol LabController \
  --workspace /path/to/uxor --project . --image "$SERENA_IMAGE" \
  --path demo/src/Controller/LabController.php --cache-dir /path/to/serena-cache
```

For repeated work, launch one daemon per worktree. Its socket directory must be owned by the current user with mode 0700. Calls are serialized against one REPL; errors return JSON and exit nonzero. Nothing automatically replays a failed edit.

```sh
mkdir -p /path/to/private-serena
chmod 700 /path/to/private-serena
python3 examples/serena/client.py serve --workspace /path/to/uxor \
  --project . --image "$SERENA_IMAGE" --write \
  --languages php_phpactor,typescript --request-timeout 180 \
  --cache-dir /path/to/serena-cache --socket /path/to/private-serena/session.sock
# From another shell:
python3 examples/serena/client.py call --socket /path/to/private-serena/session.sock \
  --code "s.edit.replace_content('demo/src/Example.php', 'old', 'new', 'literal')"
python3 examples/serena/client.py status --socket /path/to/private-serena/session.sock
python3 examples/serena/client.py stop --socket /path/to/private-serena/session.sock
```

`--write` enables edits and a writable source mount. `--read-only` is available for inspection. The MCP `initial_instructions` response also exposes `structuredContent.session_id`. Request timeouts are configurable independently of the shell startup timeout; a stopped language server reports recovery through `s.lsp.restart_language_server()` or a session restart.

End a `call --code` cell with the expression whose value you want returned.
The current REPL returns the last expression, so a cell ending in `print(value)`
can return `None`; use `value` as the last expression instead. The shell client
passes through the MCP result and does not claim separate captured stdout.
For more than one query, use the daemon above: one-shot queries start and stop a
language server each time, and its shutdown can report a termination timeout
before the process is killed. The daemon avoids that cost between calls.

| Source | Navigation | Editing |
| --- | --- | --- |
| PHP | PHPactor symbols and references | Serena source/symbol editing in write mode |
| JavaScript / TypeScript | TypeScript language server symbols and references | Serena source/symbol editing in write mode |
| Twig / YAML service IDs | Text search; semantic coverage is not established | Text edits in write mode |
| Stimulus actions/lifecycle and PHP attribute-routed entry points | Text search for convention-based invocation; semantic references only cover explicit code references | Text or source edits in write mode |

Stimulus default-exported classes are named `default`. Qualify the member and
supply its original source file to disambiguate controllers:

```python
s.lsp.find_symbol('default/connect', relative_path='modal/assets/controllers/flowbite_modal_controller.js')
```

An empty references result does not prove that a Stimulus method or routed PHP
controller is unused. Inspect `data-action`, lifecycle method names and route
attributes with text search; these entry points are invoked by convention.

Navigation honors project ignore rules. Use `--project .` to work on the kit's
original recipes outside `demo`; generated demo controller copies may be
gitignored. JavaScript reference queries include eligible workspace sources even
when the application has no `jsconfig.json` or `tsconfig.json`, without writing
either configuration file into the checkout.

## Workspace and session behavior

The Linux/amd64 runner requires Python 3.9+ and a working Docker engine with the
chosen image already present. Each invocation creates a separate container and temporary REPL state. Optional index storage is scoped to the canonical checkout, project and exact image, preserving worktree separation. It runs as the
host UID/GID, keeps protocol stdout clean, disables runtime networking, and
exposes only the selected checkout. It mounts no host home or Docker socket.
The checkout is read-only by default, enforced by the mount as well as upstream
editing APIs. Pass `--write` explicitly to allow the REPL and PHP tooling to modify
a trusted checkout. `--read-only` explicitly selects the default behavior.

Startup completes PHPactor's initial project index before exposing MCP. Cold
startup therefore takes longer for large dependency trees, but the first reference
query sees a complete initial index. Indexing uses the private session cache by default. Pass `--cache-dir /absolute/cache/path` to persist it. A complete-index marker binds source bytes (including installed PHP dependencies and sibling kit source), settings and PHPactor bytes. Changed inputs complete an incremental build before serving; unchanged inputs reuse the completed index. One process holds a cache lease for its lifetime; reuse the daemon for concurrent clients. Startup needs no runtime networking and writes no generated configuration into the checkout.

Serena's Python REPL has the container user's capabilities. This runner does not
implement Agentscient's role policy, operation locks, process auditing or work
coordination. Give concurrent editing sessions separate worktrees, or coordinate
their writes through the owning application.

The launcher reads existing `.serena/project.yml` and `project.local.yml`, applies
the prepared PHPactor default when no backend is selected, and keeps generated
configuration outside the source tree. Repository activation commands and
language-server-specific settings are discarded; global trusted project paths are
explicitly empty. A `phpactor_version` or `ls_path` override is rejected with an
actionable error, as is an incompatible backend selection. This profile keeps newly written Serena memories session-local. PHPactor automatic configuration prompts are disabled through its launch configuration and initialization options, including on a clean read-only checkout.

## What the Symfony profile establishes

The image provides PHP semantic tools, a PHP runtime and Composer. Acceptance
uses actual uxor Symfony source: class/method lookup, cross-file references,
an edit and semantic reread, persistent REPL variables, a partial edit followed by
an error, and a fresh read-only session. PHP attributes and constructor types are
present in this consumer. JavaScript/TypeScript uses the prepared TypeScript language server (`--languages php_phpactor,typescript`). This does not establish semantic Twig navigation,
resolution of service identifiers from YAML, or runtime container inspection.
Use the application's installed Symfony/Mate capabilities for runtime facts.

Dependency installation happens before acceptance starts the network-disabled
MCP runner. The test establishes offline language-server startup and operations;
it does not claim that an arbitrary application's dependencies are already cached.

## Build, verify and update

The parent is the exact PHP 8.5/Trixie artifact selected by xorder's normal build
and publication machinery. Existing accepted parents are reused. To build a
candidate with an explicitly chosen accepted parent:

```sh
python3 scripts/build.py php-serena/8.5-trixie image-library-serena:candidate \
  --parent "$PHP_DEV_DIGEST" --inventory out/php-serena.json
```

The shared verifier checks inherited PHP capabilities and runs
`tests/fixtures/serena/check.py` against its pinned uxor revision. The
fixture clones a disposable checkout, installs its Composer lock without scripts
or plugins, and drives the public runner through real stdio MCP. No model account
is required. Evidence is written to `out/serena/acceptance.json`; CI retains it
alongside image inventory and metrics. Publication repeats behavior checks before
catalog availability. A passing PR test is not a published artifact.

Serena source and its upstream `uv.lock` are pinned to
`b79e2a55f9d4072084977dd35bd07d31146d88b9` (v2 beta). The Dockerfile pins uv and
PHPactor; `requirements-build.txt` contains the hash-checked build-tool closure.
Installation uses `uv sync --locked --no-build-isolation` and checks that upstream
metadata remains unchanged. Source and upstream licenses remain in
`/opt/serena-source`. The inherited PHP image owns its OS package provenance;
this Trixie variant does not claim Agentscient's Bookworm snapshot configuration
or byte-identical rebuilds.

Update source/backend pins together when needed, regenerate the build-tool closure
against that source's lock, allocate a new image revision, and repeat real MCP
acceptance. A source-label check alone cannot prove that packaging changes landed;
select by the verified image digest and measured inventory.

## Reference lineage

This package applies the existing Agentscient work, inspected on `dev` on
2026-10-10, to a standalone xorder distribution:

- [PR 304](https://github.com/uscient/agentscient/pull/304): selected v2 beta REPL,
  persistent state, real PHP discovery/editing, partial failures and restart.
- [PR 316](https://github.com/uscient/agentscient/pull/316): separate container
  provider, prepared checksum-pinned PHPactor, offline execution and workspace
  binding. It superseded the initial Intelephense packaging for this route.
- [PR 373](https://github.com/uscient/agentscient/pull/373): upstream runtime lock
  plus a separately locked build-tool closure, exact source and artifact checks.
- [PR 380](https://github.com/uscient/agentscient/pull/380): observe-only process
  auditing and its limits. That Agentscient-owned observer is not included here.

The prior Serena readiness and session-handoff research supplied acceptance cases;
current source supplied implementation facts. Agentscient's coordination policies
are not imposed on independent projects. Upstream remains
[oraios/serena](https://github.com/oraios/serena/tree/b79e2a55f9d4072084977dd35bd07d31146d88b9).
