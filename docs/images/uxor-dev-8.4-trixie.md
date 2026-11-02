# uxor-dev/8.4-trixie

FrankenPHP/PHP 8.4 or 8.5 plus Node 22 and a pinned Tailwind CLI for uxor development and Playwright orchestration.

Available revision: **1.0.3**. Pin:

```text
ghcr.io/xormania/uxor-dev@sha256:dee7bad6852f2b22960535e3ddb3d64675719b42ea766e8151b008477c5d6143
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:30:04.754379Z.

## Measured inventory — linux/amd64

Runtime: 8.4.27; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| composer | Composer version 2.10.3 2026-08-27 13:34:23 |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| frankenphp | FrankenPHP v1.13.3 PHP 8.4.27 Caddy v2.11.7 h1:yj0Y4fYZGPkSvibBJ1sTWE33xC0fxztVyXEW5iIdUT4= |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| infection | Infection - PHP Mutation Testing Framework version 0.35.8 |
| jq | jq-1.7 |
| library-php-coverage | xorder PHP coverage runner 1.0.0 |
| library-php-tests | xorder PHP test runner 1.0.0 |
| node | v22.23.4 |
| npm | 10.9.9 |
| php | PHP 8.4.27 (cli) (built: Oct 21 2026 15:53:39) (ZTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |
| tailwindcss | ≈ tailwindcss v4.3.3 |

Extensions: `apcu`, `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,200.6 MiB (1,258,904,991 bytes) |
| Build, cache export and image load | 28.76s |
| Public-artifact behavior and inventory verification | 278.78s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:29:44.326282Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/uxor-dev@sha256:ad891975441273af65c3a9ea441aaebe310454c82abd186bc01994727ebdb8f8`; 1,201.6 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:29.248088Z.

[Release notes](../releases/uxor-dev-8.4-trixie-v1.0.3.md).

Capabilities: `composer`, `frankenphp`, `mutation-testing`, `native-build`, `node`, `npm`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `playwright-client`, `postgresql-client`, `symfony`, `tailwind-cli`, `worker-server`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Node and Playwright browsers are supplied by the uxor profile and its official companion, respectively.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Playwright and application packages come from project lockfiles; browsers run in the version-matched official Playwright companion.
- Project dependencies and Caddy/worker configuration belong to the consuming repository.
- The cached Tailwind binary is seeded only when its version and platform match the consuming project configuration.
- Use examples/uxor/run.sh to reuse repository-owned worker, Caddy, PHP and mount configuration without an in-container Docker socket.
- Xdebug is off by default; enable explicitly for debugging or coverage.
