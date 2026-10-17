# php-toolkit/8.5-trixie

Isolated Symfony UX Toolkit kit validation and clean locked Symfony 7.4 recipe-install applications, prepared for restricted consumer networks.

Available revision: **1.0.3**. Pin:

```text
ghcr.io/xormania/php-toolkit@sha256:3c25724c04a3b854e6a4d90098fbc08ff9ca15306d1e07373fce42ae3d8b185c
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:28:11.920972Z.

## Measured inventory — linux/amd64

Runtime: 8.5.11; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| composer | Composer version 2.10.3 2026-08-27 13:34:23 |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| infection | Infection - PHP Mutation Testing Framework version 0.35.8 |
| jq | jq-1.7 |
| library-php-coverage | xorder PHP coverage runner 1.0.0 |
| library-php-tests | xorder PHP test runner 1.0.0 |
| php | PHP 8.5.11 (cli) (built: Oct  6 2026 01:22:31) (NTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |

Extensions: `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `lexbor`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `uri`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 968.0 MiB (1,014,993,227 bytes) |
| Build, cache export and image load | 13.12s |
| Public-artifact behavior and inventory verification | 32.11s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:38.798809Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/php-toolkit@sha256:37c5fbacc336a888a327a5aaf9bb68b33cc0662dbab992a373b8efa0b7ce7e79`; 966.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:57:57.620489Z.

[Release notes](../releases/php-toolkit-8.5-trixie-v1.0.3.md).

Capabilities: `composer`, `mutation-testing`, `native-build`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `postgresql-client`, `prepared-composer-dependencies`, `symfony`, `symfony-toolkit-baseline`, `ux-toolkit-validation`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Toolkit validation and fresh-app recipe](../php-toolkit.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Prepared projects do not select PHPUnit or PHPStan versions for the consuming project. Fresh baselines contain no generated kit recipes or application cache.
- Prepared validator and baseline dependencies belong to their committed xorder lockfiles, not the consuming application's lockfile.
- Project PHP dependencies come from Composer lockfiles.
- The clean baseline is Symfony 7.4 with Symfony UX Toolkit 3.5.1; a different baseline requires an explicitly updated lock and image revision.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
