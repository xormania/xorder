# Capability guide: general bases to specific tasks

Generated navigation from `discovery/organization.json` and the shared verified release ledger. [Current JSON index](../discovery.json) has one newest available release per resource; [release history](../catalog-v2.json) retains every exact revision. A new current release never changes an existing profile or project pin.

Choose the least specialized environment that satisfies the project's requirements. These layers describe applicability, not automatic inheritance. Images contain toolchains; application dependencies, services and locks belong to the project. Verified release evidence is linked from each resource's usage page.

## General bases and toolchains

### General bases and toolchains

CLI development; unit and integration tests; project-owned lockfiles.

[Usage](../docs/usage.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-dev/8.4-trixie](../docs/images/php-dev-8.4-trixie.md) | 1.2.3 | linux/amd64 |
| [image/php-dev/8.5-trixie](../docs/images/php-dev-8.5-trixie.md) | 1.2.3 | linux/amd64 |
| [image/python-dev/3.14-trixie](../docs/images/python-dev-3.14-trixie.md) | 1.1.4 | linux/amd64 |
| [image/rust-dev/1.99-trixie](../docs/images/rust-dev-1.99-trixie.md) | 1.1.4 | linux/amd64 |

Pinned selections: [profile/php-base](../profiles/php-base.json), [profile/python-base](../profiles/python-base.json), [profile/rust-base](../profiles/rust-base.json).

## Framework environments

### PHP/Symfony HTTP and native environments

Symfony applications; FrankenPHP HTTP and workers; native devenv setup.

[Usage](../docs/usage.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-frankenphp/8.4-trixie](../docs/images/php-frankenphp-8.4-trixie.md) | 1.1.4 | linux/amd64 |
| [image/php-frankenphp/8.5-trixie](../docs/images/php-frankenphp-8.5-trixie.md) | 1.1.4 | linux/amd64 |
| [environment/php-symfony](../docs/resources/environment-php-symfony.md) | 1.0.0 | linux/amd64 |

Pinned selections: [profile/php-http](../profiles/php-http.json), [profile/php-project](../profiles/php-project.json).

## Focused tasks

### Browser test execution

Panther with Chromium; Playwright browser tasks matching the consuming project lock.

[Usage](../docs/usage.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-browser/8.4-trixie](../docs/images/php-browser-8.4-trixie.md) | 1.2.3 | linux/amd64 |
| [image/php-browser/8.5-trixie](../docs/images/php-browser-8.5-trixie.md) | 1.2.3 | linux/amd64 |
| [image/playwright-browser/1.58-trixie](../docs/images/playwright-browser-1.58-trixie.md) | 1.0.4 | linux/amd64 |

### PHP coverage and analysis

project-locked PHPUnit; per-process coverage; isolated prepared PHPStan.

[Usage](../docs/php-tests.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-dev/8.4-trixie](../docs/images/php-dev-8.4-trixie.md) | 1.2.3 | linux/amd64 |
| [image/php-dev/8.5-trixie](../docs/images/php-dev-8.5-trixie.md) | 1.2.3 | linux/amd64 |

Pinned selections: [profile/php-tests](../profiles/php-tests.json).

### PHP/Symfony code navigation with Serena

Serena v2 REPL; PHP language-server navigation.

[Usage](../docs/serena.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-serena/8.5-trixie](../docs/images/php-serena-8.5-trixie.md) | 1.1.3 | linux/amd64 |

### Isolated Symfony UX Toolkit validation

locked kit validation; fresh Symfony recipe installation.

[Usage](../docs/php-toolkit.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/php-toolkit/8.4-trixie](../docs/images/php-toolkit-8.4-trixie.md) | 1.0.3 | linux/amd64 |
| [image/php-toolkit/8.5-trixie](../docs/images/php-toolkit-8.5-trixie.md) | 1.0.3 | linux/amd64 |

Pinned selections: [profile/php-toolkit](../profiles/php-toolkit.json).

## Project-specific environments

### uxor development and tests

xormania/uxor; parallel worktrees; FrankenPHP and project-locked Playwright.

[Usage](../docs/uxor.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [image/uxor-dev/8.4-trixie](../docs/images/uxor-dev-8.4-trixie.md) | 1.0.2 | linux/amd64 |
| [image/uxor-dev/8.5-trixie](../docs/images/uxor-dev-8.5-trixie.md) | 1.0.2 | linux/amd64 |

Pinned selections: [profile/uxor](../profiles/uxor.json).

## Independent supporting resources

### Independently selected supporting resources

standalone package management; owned formatting configuration; explicit Codex project guidance.

[Usage](../docs/resources/index.md).

| Available resource | Current revision | Targets |
| --- | --- | --- |
| [binary/composer](../docs/resources/binary-composer.md) | 1.0.0 | linux/amd64 |
| [configuration/editorconfig](../docs/resources/configuration-editorconfig.md) | 1.0.0 | any |
| [context/project-guidance](../docs/resources/context-project-guidance.md) | 1.0.0 | any |

Pinned selections: [profile/composer](../profiles/composer.json).

## Pinned profiles and prerequisites

`required_releases_available` means the ledger contains the required selections. It does not establish host compatibility, conditional assignments, package access or application readiness. Inspect the actual target, resolve the profile, then follow its readiness recipe.

| Profile | Required release status | Usage and readiness |
| --- | --- | --- |
| [profile/composer](../profiles/composer.json) | `required_releases_available` | [usage](../docs/resources/binary-composer.md) · [readiness](../docs/resources/binary-composer.md) |
| [profile/php-base](../profiles/php-base.json) | `required_releases_available` | [usage](../docs/usage.md) · [readiness](../docs/compatibility.md) · [runner](../scripts/run-image.sh) |
| [profile/php-http](../profiles/php-http.json) | `required_releases_available` | [usage](../docs/usage.md) · [readiness](../docs/compatibility.md) · [runner](../scripts/run-image.sh) |
| [profile/php-project](../profiles/php-project.json) | `required_releases_available` | [usage](../docs/profiles.md) · [readiness](../docs/resources/environment-php-symfony.md) |
| [profile/php-tests](../profiles/php-tests.json) | `required_releases_available` | [usage](../docs/php-tests.md) · [readiness](../docs/php-tests.md) · [runner](../scripts/run-image.sh) |
| [profile/php-toolkit](../profiles/php-toolkit.json) | `required_releases_available` | [usage](../docs/php-toolkit.md) · [readiness](../docs/php-toolkit.md) · [runner](../examples/php-toolkit/run.sh) |
| [profile/python-base](../profiles/python-base.json) | `required_releases_available` | [usage](../docs/usage.md) · [readiness](../docs/compatibility.md) · [runner](../scripts/run-image.sh) |
| [profile/rust-base](../profiles/rust-base.json) | `required_releases_available` | [usage](../docs/usage.md) · [readiness](../docs/compatibility.md) · [runner](../scripts/run-image.sh) |
| [profile/uxor](../profiles/uxor.json) | `required_releases_available` | [usage](../docs/uxor.md) · [readiness](../docs/claude-cloud.md) · [runner](../examples/uxor/run.sh) |

