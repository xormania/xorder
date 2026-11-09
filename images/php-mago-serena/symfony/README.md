# Symfony project integration

The image owns executable tools. Each project owns its Composer dependencies,
source, cache, profiler data and logs. The installed helper creates a new project
from the image's selected tuple:

```sh
library-symfony-mago --project /workspace/new-project init
cd /workspace/new-project
composer install
library-symfony-mago prepare
library-symfony-mago check
library-symfony-mago native -- analyze
library-symfony-mago native -- lint
library-symfony-mago native -- format --check
library-symfony-mago native -- guard --structural
library-symfony-mago analyze --symbol 'App\Service\Greeting'
library-symfony-mago analyze --symbol 'App\Service\Greeting' --extension-off
php vendor/bin/mate tools:list --format=json
```

`init` accepts an empty directory. It reads exact Symfony and AI Mate versions
from `targets` and `mate` in `/opt/xorder/serena/toolchain.lock.json`, and uses
the selected Mago SDK and Symfony wiring source revisions from that same file.
It creates a fresh local development secret in `.env.local` with mode 0600;
application secrets and runtime data are never built into the image.

The root `mago.toml` enables the patched Mago backend's Symfony worker for CLI
analysis and Serena's Mago LSP. `prepare` exports the actual compiled dev
container through the wiring package's sanitizer. Raw Console exports remain
in a private temporary directory that is removed after export. The retained
reference is `.mago/container-reference.dev.json`.

Native checks use the current native Mago executable and a separate
`.mago/native.toml` generated from the same source settings. That configuration
excludes the older backend's LSP table because newer native releases removed
the language-server schema. Native checks disable external workers.

`prepare` preserves existing profiles and logs before rebuilding metadata. Its
receipt binds project source, Composer lock and installed package identities,
configuration, compiled XML, sanitized reference and image identity. Changed
inputs require another preparation. Restart Serena's language server after a
new export unless the client delivers the configured watched-file notification.

The enriched command retains native stdout, stderr, graph observations and its
result under `.mago/evidence/`. Native findings retain exit 1. Missing graph
output, incomplete extension attestation or stale metadata returns exit 3.
`--extension-off` supplies the comparison control using the same prepared state.

AI Mate uses the `inspection-dev` context for the project's dev container,
profiler storage and logs. Its CLI remains available as `php vendor/bin/mate`.
The generated project does not install PHPStan. Mago owns the static checks;
behavioral tests remain project dependencies.
