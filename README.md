# xorder

xorder distributes prepared software, development environments, configuration,
and agent context for computers and containers. **Give an agent
https://github.com/xormania/xorder together with its project task.** This README,
the catalog, and the linked usage pages provide discovery without an installed
CLI, skill, plugin, or discovery service.

Start here:

1. Inspect the project's runtime constraints, lockfiles, services, and test needs.
2. Inspect the execution environment and its prerequisites. Images need a working
   Docker engine and registry access; a Docker client alone is insufficient.
3. Read the compact [catalog](catalog-v2.json) for available resources matching
   those requirements; image inventories remain in the [image view](catalog.json).
4. Follow the entry's usage link, pin its exact `identity`, and run its readiness
   recipe before installing project dependencies from their own lockfiles.
5. Report any missing capability or prerequisite precisely. Keep an established
   compatible project pin unless an update is requested.

## Resource kinds

| Kind | Purpose |
| --- | --- |
| Images | Ready-to-pull PHP/Symfony, browser, Rust, and Python toolchains |
| Binaries | Downloadable software with exact hashes and explicit runtime/platform prerequisites |
| Environments | Reusable native definitions, starting with devenv and its locked inputs |
| Configuration | Independently versioned settings installed into explicit owned scopes |
| Context | Selected guidance or skills for an explicit task, role, or harness |

[Architecture](docs/architecture.md) describes the extension boundaries and
profiles that compose resources. Only verified releases in the generated tables
and catalog are selectable; authored definitions remain unavailable until accepted.
Reading the catalog does not activate context bundles.

## Available downloadable resources

<!-- resources:start -->
| Resource | Revision | Target | Prerequisites | Exact identity |
| --- | --- | --- | --- | --- |
| [binary/composer](docs/resources/binary-composer.md) | 1.0.0 | linux/amd64 | `php` | `sha256:7a2d379d5b8ffdaa028580ef26494c36d2feef4b178d3dd1473a4dbc5e17c8d6` |
| [configuration/editorconfig](docs/resources/configuration-editorconfig.md) | 1.0.0 | any | See usage | `sha256:5aa2360af22e47bb84708bd2262268527f7359e94f224f04213c0fc929dbddea` |
| [context/project-guidance](docs/resources/context-project-guidance.md) | 1.0.0 | any | See usage | `sha256:4a1c7ff451e8f835c1d921c9a212af8d129e3ed166789d3cd52c9c01aef442ff` |
| [environment/php-symfony](docs/resources/environment-php-symfony.md) | 1.0.0 | linux/amd64 | `nix`, `devenv` | `sha256:59ae1dd08d906bb3c897e7c4b26ad2dcfe0d9cd7bc76a3fe08132a1908be3c6f` |
<!-- resources:end -->

The generated [resource index](docs/resources/index.md) links verified usage,
prerequisites, release records, and evidence as new resources become available.

## Available images

<!-- catalog:start -->
| Line | Revision | Verified platform | Exact reference |
| --- | --- | --- | --- |
| [flowbite-xor-dev/8.4-trixie](docs/images/flowbite-xor-dev-8.4-trixie.md) | 1.1.1 | linux/amd64 | `ghcr.io/xormania/flowbite-xor-dev:8.4-trixie-v1.1.1` |
| [flowbite-xor-dev/8.5-trixie](docs/images/flowbite-xor-dev-8.5-trixie.md) | 1.2.1 | linux/amd64 | `ghcr.io/xormania/flowbite-xor-dev:8.5-trixie-v1.2.1` |
| [php-browser/8.4-trixie](docs/images/php-browser-8.4-trixie.md) | 1.2.1 | linux/amd64 | `ghcr.io/xormania/php-browser:8.4-trixie-v1.2.1` |
| [php-browser/8.5-trixie](docs/images/php-browser-8.5-trixie.md) | 1.2.1 | linux/amd64 | `ghcr.io/xormania/php-browser:8.5-trixie-v1.2.1` |
| [php-dev/8.4-trixie](docs/images/php-dev-8.4-trixie.md) | 1.2.1 | linux/amd64 | `ghcr.io/xormania/php-dev:8.4-trixie-v1.2.1` |
| [php-dev/8.5-trixie](docs/images/php-dev-8.5-trixie.md) | 1.2.1 | linux/amd64 | `ghcr.io/xormania/php-dev:8.5-trixie-v1.2.1` |
| [php-frankenphp/8.4-trixie](docs/images/php-frankenphp-8.4-trixie.md) | 1.1.1 | linux/amd64 | `ghcr.io/xormania/php-frankenphp:8.4-trixie-v1.1.1` |
| [php-frankenphp/8.5-trixie](docs/images/php-frankenphp-8.5-trixie.md) | 1.1.1 | linux/amd64 | `ghcr.io/xormania/php-frankenphp:8.5-trixie-v1.1.1` |
| [php-serena/8.5-trixie](docs/images/php-serena-8.5-trixie.md) | 1.1.0 | linux/amd64 | `ghcr.io/xormania/php-serena:8.5-trixie-v1.1.0` |
| [php-toolkit/8.4-trixie](docs/images/php-toolkit-8.4-trixie.md) | 1.0.1 | linux/amd64 | `ghcr.io/xormania/php-toolkit:8.4-trixie-v1.0.1` |
| [php-toolkit/8.5-trixie](docs/images/php-toolkit-8.5-trixie.md) | 1.0.1 | linux/amd64 | `ghcr.io/xormania/php-toolkit:8.5-trixie-v1.0.1` |
| [playwright-browser/1.58-trixie](docs/images/playwright-browser-1.58-trixie.md) | 1.0.2 | linux/amd64 | `ghcr.io/xormania/playwright-browser:1.58-trixie-v1.0.2` |
| [python-dev/3.14-trixie](docs/images/python-dev-3.14-trixie.md) | 1.1.2 | linux/amd64 | `ghcr.io/xormania/python-dev:3.14-trixie-v1.1.2` |
| [rust-dev/1.99-trixie](docs/images/rust-dev-1.99-trixie.md) | 1.1.2 | linux/amd64 | `ghcr.io/xormania/rust-dev:1.99-trixie-v1.1.2` |
<!-- catalog:end -->

Use catalog entries marked `available`, check their verified architecture and
capabilities, and pin the chosen `identity` (`digest_reference` in the image view).
Never pull a guessed tag
from a planned profile. Existing GHCR image names and exact references remain
valid after the repository rename.

## Using an image

Follow [selection](docs/selection.md) and use the selected exact digest in
[usage](docs/usage.md). An optional deterministic helper accepts an explicit
requirements JSON file after cloning this repository:

```sh
python3 scripts/library.py select requirements.json
```

The helper requires Python and the dependencies in `requirements-ci.txt`.
Reading the catalog and following its usage instructions does not require it.

The images supply toolchains. Your project's dependencies and database remain
explicit. `php-browser` adds Chromium and Panther prerequisites; it does not
assume Node is needed for Symfony UX or Tailwind. The
[uxor profile](docs/uxor.md) offers PHP 8.4/8.5, adds Node 22 and cached Tailwind to FrankenPHP, and uses
the project-locked official Playwright companion. New lines remain unavailable
until their verified public releases enter the catalog.

## Optional discovery helper

After cloning, Python 3 and `requirements-ci.txt` provide the same catalog through
read-only commands:

```sh
python3 scripts/xorder_cli.py list
python3 scripts/xorder_cli.py show image/php-dev/8.5-trixie
python3 scripts/xorder_cli.py resolve profile.json --target target.json
```

The last command reads an authored local profile and observed target facts; it
prints an exact resolution lock or precise requirement gaps and changes no files.
[Architecture](docs/architecture.md#read-only-profile-resolution) describes the
inputs, existing pins, and explicit private overlays. Discovery through the URL
and direct usage pages remains sufficient.

## Documentation

- [Architecture, resource boundaries, and discovery](docs/architecture.md)
- [Verified downloadable resources and prerequisites](docs/resources/index.md)
- [Applying locks, ownership, recovery, and rollback](docs/application.md)
- [URL discovery and host/container acceptance](docs/discovery.md)
- [Profiles and private assignment overlays](docs/profiles.md)
- [Selection and requirement gaps](docs/selection.md)
- [Shared CI and local registry build caches](docs/build-cache.md)
- [Workspace, caches, database, and browser recipes](docs/usage.md)
- [FrankenPHP and uxor development/testing](docs/uxor.md)
- [Claude cloud session quick start and dependency reuse](docs/claude-cloud.md)
- [Automatic UTC prompt context for Claude Code](docs/claude-hooks.md)
- [Reusable PHP test tasks and per-process coverage](docs/php-tests.md)
- [Named source faults, served confirmation, and generated-copy checks](docs/local-testing.md)
- [Test receipts and observed server URLs](docs/local-testing-receipts.md)
- [Startup disk budgets, run leases, and idle activity](docs/runtime.md)
- [Optional local failure triage](docs/failure-triage.md)
- [Prepared Serena v2 REPL, shell access and editing](docs/serena.md)
- [Agent feedback implementation and runner operations](docs/agent-feedback.md)
- [Browser releases matched to consumer Playwright pins](docs/browser-releases.md)
- [Isolated Toolkit validation and fresh Symfony applications](docs/php-toolkit.md)
- [Cloud prerequisites and verification evidence](docs/compatibility.md)
- [Versions, pins, upgrades, and rollback](docs/versioning.md)
- [Verified release measurements](docs/metrics.md)
- [Publication, retry, and repository setup](docs/releases.md)
- [Contributing resources and refreshing dependencies](docs/contributing.md)
- [Implementation status](docs/implementation.md)

Generated inventories describe measured released artifacts. Supported upstream
platforms and vendor claims do not establish that these images were tested there.
