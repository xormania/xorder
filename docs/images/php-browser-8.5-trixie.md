# php-browser/8.5-trixie

PHP and Symfony development plus real Chromium and Panther browser tests.

Available revision: **1.2.2**. Pin:

```text
ghcr.io/xormania/php-browser@sha256:9f8e9d147578381199b3a916f9fc9d4792ce9b310aab499b08bee595cb9b7425
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:44.294698Z.

## Measured inventory — linux/amd64

Runtime: 8.5.11; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| chromedriver | ChromeDriver 155.0.8059.39 (3ff7ac5a9224be9156d7f8703a06e22890aafd34-refs/branch-heads/8059@{#935}) |
| chromium | Chromium 155.0.8059.39 built on Debian GNU/Linux 13 (trixie) |
| composer | Composer version 2.10.3 2026-08-27 13:34:23 |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| infection | Infection - PHP Mutation Testing Framework version 0.35.6 |
| jq | jq-1.7 |
| library-php-coverage | xorder PHP coverage runner 1.0.0 |
| library-php-tests | xorder PHP test runner 1.0.0 |
| php | PHP 8.5.11 (cli) (built: Oct  6 2026 01:22:31) (NTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.0 (c) 2021-2026 Fabien Potencier (2026-10-06T20:55:04Z - stable) |

Extensions: `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `lexbor`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `uri`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,648.6 MiB (1,728,723,524 bytes) |
| Build, cache export and image load | 55.10s |
| Public-artifact behavior and inventory verification | 24.09s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:13.012595Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.1, `ghcr.io/xormania/php-browser@sha256:3bd07aa66ea6af93ee3e690be1cb2e09352d3fa2e19f522f458e7020d664aded`; 1,645.3 MiB in the same image store. Change: **+0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:12:13.407279Z.

[Release notes](../releases/php-browser-8.5-trixie-v1.2.2.md).

Capabilities: `browser`, `composer`, `mutation-testing`, `native-build`, `panther`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `postgresql-client`, `symfony`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Chromium may need --no-sandbox where the host prohibits sandbox namespaces. Use only for trusted development content.
- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- Node is not included; request a separate capability when the project requires it.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Project PHP dependencies come from Composer lockfiles.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
