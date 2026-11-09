# uxor-dev/8.5-trixie

FrankenPHP/PHP 8.4 or 8.5 plus Node 22 and a pinned Tailwind CLI for uxor development and Playwright orchestration.

Available revision: **1.0.5**. Pin:

```text
ghcr.io/xormania/uxor-dev@sha256:64f1b5331de0cd52f958f4f233c4eaf7a0626f68e80fc48273d884de224fdc92
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/42597978081); 2026-11-09T11:03:22.756871Z.

## Measured inventory — linux/amd64

Runtime: 8.5.12; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| composer | Composer version 2.11.1 2026-10-30 14:52:10 |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| frankenphp | FrankenPHP v1.13.5 PHP 8.5.12 Caddy v2.11.9 h1:bhZtcRKQOq0fuLvEgCdPYvUxXyGn9kzjG4lh2332DTE= |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| infection | Infection - PHP Mutation Testing Framework version 0.35.9 |
| jq | jq-1.7 |
| library-php-coverage | xorder PHP coverage runner 1.0.0 |
| library-php-tests | xorder PHP test runner 1.0.0 |
| node | v22.23.4 |
| npm | 10.9.9 |
| php | PHP 8.5.12 (cli) (built: Nov  5 2026 07:15:06) (ZTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |
| tailwindcss | ≈ tailwindcss v4.3.3 |

Extensions: `apcu`, `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `lexbor`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `uri`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,231.2 MiB (1,291,049,162 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 415.17s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597978081); 2026-11-09T11:02:48.497262Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.3, `ghcr.io/xormania/uxor-dev@sha256:28af54394cf26d6ff6fcb6f54ce85cfd4784d6cf867cd77b5187c5e1ddf9214b`; 1,230.3 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:32:39.031886Z.

[Release notes](../releases/uxor-dev-8.5-trixie-v1.0.5.md).

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
