# php-browser/8.5-trixie

PHP and Symfony development plus real Chromium and Panther browser tests.

Available revision: **1.2.7**. Pin:

```text
ghcr.io/xormania/php-browser@sha256:7d563a60793d5022473f5ca1a54dfb7660a2cb63cdff56d754637c90f99e69d1
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:25:29.662553Z.

## Measured inventory — linux/amd64

Runtime: 8.5.12; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| chromedriver | ChromeDriver 156.0.8078.79 (a21ce95c24ce3964416f09ae1862f53f319eb4d0-refs/branch-heads/8078@{#1704}) |
| chromium | Chromium 156.0.8078.79 built on Debian GNU/Linux 13 (trixie) |
| composer | Composer version 2.11.1 2026-10-30 14:52:10 |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| infection | Infection - PHP Mutation Testing Framework version 0.35.9 |
| jq | jq-1.7 |
| library-php-coverage | xorder PHP coverage runner 1.0.0 |
| library-php-tests | xorder PHP test runner 1.0.0 |
| php | PHP 8.5.12 (cli) (built: Nov  5 2026 07:20:51) (NTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |

Extensions: `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `lexbor`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `uri`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,651.0 MiB (1,731,161,144 bytes) |
| Build, cache export and image load | 64.20s |
| Public-artifact behavior and inventory verification | 31.28s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:24:50.850042Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.4, `ghcr.io/xormania/php-browser@sha256:86e074a244a0d283d9ca2180703846a90e864ca06183054e88f72954c37da427`; 1,651.5 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:22:25.459883Z.

[Release notes](../releases/php-browser-8.5-trixie-v1.2.7.md).

Capabilities: `browser`, `composer`, `mutation-testing`, `native-build`, `panther`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `postgresql-client`, `symfony`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Chromium may need --no-sandbox where the host prohibits sandbox namespaces. Use only for trusted development content.
- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Project PHP dependencies come from Composer lockfiles.
- The php-browser parent itself does not include Node; derived image lines may add it.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
