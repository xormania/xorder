# Symfony development with Mago and Serena

The new-project composition supplies native Mago quality commands, Serena's Mago
language server, and reusable Symfony/AI Mate project preparation. Its image
definitions remain unavailable until the ordinary publication path records a
verified digest. Existing UXor and FrankenPHP compositions keep their own inputs.

## Selected tuple

`images/php-mago-serena/toolchain.lock.json` records exact inputs selected from
the latest observed releases, including prereleases. Moving names are resolved
before a build; a running project uses an exact image and Composer lock.

| Role | Selected input |
| --- | --- |
| Native analysis, lint, formatting, architectural guards | Mago 1.59.0, `mago-native` |
| Experimental language server and Symfony extension backend | Patched Mago 1.58.2, source `46df50c96d93d0ac3655c116c375574277cf0b30`, `mago` |
| PHP extension SDK | Same source revision as the experimental backend, MANA 2.1 |
| Symfony wiring extension | `28c3f54065b71fe046a7474ced401aeadc941b0f`, 1.3.0-RC1 |
| Serena | Current main `ede329aaf0c824bea75455a2926f01420d7aa620`, 2.1.1.dev0, with the PoC facade patch |
| New Symfony project | 8.2.0-BETA1 |
| AI Mate, Symfony and Monolog extensions | 1.0.0-BETA1 |

The original PoC validated Symfony 8.1.0 on PHP 8.5.12. The Symfony-Chrome donor
subsequently selected Symfony 8.1.11 on PHP 8.4.26. The new beta tuple requires
its own Composer, metadata, CLI and MCP acceptance; copying the PoC does not
establish that a newer tuple passed. The exact selected Serena manifest and
facade source are byte-identical to the donor's, so the facade patch applies
without a code change. Source and effective lock identities are retained.

The latest Mago source observed at `b14416abde9e07ebe6103fde791b9bb8ecbf67f8`
removes `crates/server` and `src/language_server`, which the PoC patch extends.
Its extension protocol also differs. Native commands therefore advance
independently while the experimental backend and SDK remain matched. This is a
documented port requirement, not a permanent version ceiling. Backend promotion
requires the compiled wiring graph, extension attestation, semantic lookup and
restart tests to pass against the new pair.

## Independently reusable build inputs

| Component | Invalidated by |
| --- | --- |
| `mago-native` | Upstream release URL/hash or extraction recipe |
| `mago-baseline` | The comparison release URL/hash or extraction recipe |
| `mago-lsp` | Rust/source/patch/build inputs |
| `serena-deps` | Python/uv pins, frozen dependency lock and package manifests |
| Final composition | Adapter source, facade patch, configuration seeds, project integration and selected component identities |

The internal components export payloads rather than another application image.
They are keyed and retained through the shared component publication/cache
path. A new builder can pull their exact prepared identities. Changing a Serena
config seed or adapter source does not reinstall its frozen dependencies;
changing browser pins does not recompile Mago. Compiler artifacts and dependency
download caches stay out of final runtime payloads.

## Create and prepare a project

Inside an accepted image, initialize an empty mounted directory:

```sh
library-symfony-mago --project /workspace init
composer install --working-dir=/workspace --no-interaction
library-symfony-mago --project /workspace prepare
library-symfony-mago --project /workspace check
```

Initialization writes a minimal Symfony project, explicit selected Composer
requirements, Mago configurations, a Serena project seed, and AI Mate's
`inspection-dev` context. It refuses an occupied directory. The image stores no
application container cache, service facts, profiles or logs. Composer resolves
the selected requirements once into the project's own lock.

Preparation runs Mate discovery and compiles the dev container, sanitizes the
private service exports into `.mago/container-reference.dev.json`, and records
the source, dependency, compiled metadata and image identities. Existing runtime
profiles and logs are retained before refresh. Changed source or metadata makes
compiled reads stale until preparation runs again; restart an existing language
server after refreshing its service reference.

```sh
library-symfony-mago native -- analyze --reporting-format json
library-symfony-mago native -- lint
library-symfony-mago native -- format --check src
library-symfony-mago native -- guard --structural
library-symfony-mago analyze --symbol 'App\Service\Greeting' --
library-symfony-mago analyze --extension-off --
php vendor/bin/mate tools:list --format=json
```

Native commands use `mago-native` with the explicit `.mago/native.toml`, which
omits server configuration removed from the latest native schema. The root
`mago.toml` configures the experimental backend's PHP worker for both enriched
CLI analysis and the Serena language server. The worker supplies compiled
Symfony wiring; Mago owns the analysis graph. The graph observer adds no edges.
An absent graph or incomplete attestation is a tool failure, while valid native
findings retain exit 1.

AI Mate reads compiled metadata from `var/cache/dev`, request profiles from
`var/cache/dev/profiler`, and logs from `var/log`, using `inspection-dev`.
These are project-owned observations. The source image does not contain them.

## Refresh the tuple

```sh
python3 scripts/refresh_symfony.py > out/symfony-refresh-proposal.json
```

The refresh command reads upstream releases and Serena main, recognizes BETA/RC
versions even when GitHub's prerelease flag is false, and emits a complete exact
candidate plus the previous tuple. It retains the independent tested LSP/SDK
fallback. It does not mutate pins or claim qualification. Apply its listed lock,
component and project changes together, then run the required real component,
Composer, AI Mate, native Mago, wiring and MCP acceptance checks before an image
becomes available. `--observations FILE` replays captured upstream JSON for a
review or an offline test. No scheduled network check is enabled by this change.
