# Choosing an image from the repository URL

Start at [the public README](https://github.com/xormania/xorder).
Read [catalog.json](../catalog.json) for available artifacts and the linked image
inventory. These documents contain the information needed by a person or an
agent; there is no separate skill to install.

1. Inspect the project: `composer.json` and lock, `pyproject.toml` and lock,
   `Cargo.toml`, toolchain files, Docker/Compose/devcontainer configuration and
   its actual test instructions. Keep an established project digest selection.
2. Identify required runtime line, extensions, tools, native libraries, browser
   behavior, services, and host architecture. A minimum runtime constraint may
   allow several lines; check dependency compatibility before choosing a newer one.
3. Run `docker info`, `docker compose version`, and check registry/network access
   from this execution surface. The presence of a Docker client is insufficient.
4. Look for catalog releases with `lifecycle: available`. Check the per-platform
   measured inventory and limitations. Prefer the smallest complete profile.
5. Resolve the catalog entry to its `digest_reference`; run its readiness recipe.
6. Install the project's locked dependencies, then execute project commands
   inside the container. Report any outstanding requirement precisely.

For PHP with intl and PostgreSQL, use a compatible `php-dev` line and an explicit
PostgreSQL companion. Add Panther/browser requirements to select `php-browser`.
Symfony UX and Tailwind alone do not imply a Node requirement. When Node is
actually declared, the CLI/Panther profiles do not satisfy it. For a FrankenPHP
worker project, consider `php-frankenphp`; for uxor's Node/Playwright
workflow, use the [project profile](uxor.md) and
`tests/requirements/flowbite-xor.json` (PHP 8.5) or
`tests/requirements/flowbite-xor-8.4.json`. These require cached Tailwind so the
selected image supports the current runner. Definitions are candidates until their
verified available releases enter the catalog.

An optional deterministic helper accepts explicit requirements:

```sh
python3 scripts/library.py select tests/requirements/php.json
python3 scripts/library.py select tests/requirements/browser.json
```

The JSON format has `runtime_line`, optional `family`, `platform` (default
`linux/amd64`), `capabilities`, `extensions`, and optional `pinned_digest`.
It expects an already interpreted runtime line, rather than trying to evaluate
every language's dependency syntax. Read the manifest before preparing it.
The helper returns a complete catalog entry or a gap, and exits 2 for a gap.
Unknown existing pins are reported for review, never silently replaced.

| Condition | What to report |
| --- | --- |
| No entry satisfies every requirement | Missing runtime, extension, capability, or architecture; propose an image expansion |
| Catalog cannot be fetched | Discovery failed; do not infer an image exists |
| Registry pull fails | Registry access/authentication/network failure; keep the selected identity |
| Docker engine or mount capability absent | Host capability missing; installing a CLI does not solve it |
| Cloud surface has no recorded runtime evidence | Compatibility unknown on that surface; run readiness checks |
| Existing digest absent from catalog | Pin is unverified by this catalog; inspect the project's established selection |

The requirement fixtures define expected choices independently of the catalog.
Unit tests exercise this selection logic. Container acceptance executes real
commands against mock consuming projects and services. This does not measure
how a language model interprets prose.
