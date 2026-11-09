# php-mago-serena/8.4-trixie

Composable PHP Symfony development with latest selected native Mago, current Serena REPL, matched patched Mago LSP/SDK, and reusable Symfony/AI Mate project preparation.

Available revision: **1.0.0**. Pin:

```text
ghcr.io/xormania/php-mago-serena@sha256:7ec4859f1844a109f014730f2de306dbaf49073fbd92092c40ae0f586227316c
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:27:48.444118Z.

## Measured inventory — linux/amd64

Runtime: 8.4.27; OS: Debian GNU/Linux 13 (trixie).

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
| library-symfony-mago | library-symfony-mago 1.0.0 |
| mago | mago 1.58.2 |
| mago-baseline | mago 1.58.2 |
| mago-native | mago 1.59.0 |
| php | PHP 8.4.27 (cli) (built: Nov  5 2026 07:23:05) (NTS) |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| python | Python 3.12.12 |
| rg | ripgrep 14.1.1 |
| serena | Serena 2.1.1.dev0 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |
| uv | uv 0.12.8 (x86_64-unknown-linux-musl) |

Extensions: `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,870.2 MiB (1,961,098,170 bytes) |
| Build, cache export and image load | 33.24s |
| Public-artifact behavior and inventory verification | 54.03s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:27:09.798648Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

[Release notes](../releases/php-mago-serena-8.4-trixie-v1.0.0.md).

Capabilities: `ai-mate-project-config`, `browser`, `chromium`, `composer`, `mago`, `mago-lsp-extensions`, `mago-native`, `mago-sdk-compatible`, `mutation-testing`, `native-build`, `panther`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `postgresql-client`, `python-3.12`, `serena-mago-adapter`, `serena-v2-repl`, `symfony`, `symfony-mago-project`, `uv`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Mago, Serena and Chrome development recipe](../mago-chrome.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Chromium may need --no-sandbox where the host prohibits sandbox namespaces. Use only for trusted development content.
- Linux amd64 only. Rebuild binary hashes are recorded; byte equality across builders is not required.
- Native quality commands select Mago1.59.0. Patched Mago1.58.2/SDK46df50c remains the LSP/Symfony extension backend: latest upstream removes its language-server source tree. Both identities are explicit; the backend port must pass semantic/runtime checks before promotion.
- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Project PHP dependencies come from Composer lockfiles.
- Python 3.12 is supplied in /usr/local for Serena; Debian Python remains in /usr/bin.
- Serena uses the Mago SolidLSP adapter; the separate php-serena line uses PHPactor.
- The Mago LSP extension is a repository patch, not an upstream API. The PoC recorded an external-edit span defect with a restart workaround.
- The consumer owns Composer dependencies, project configuration and mounted workspaces. No daemons, Docker socket or credentials are installed.
- The php-browser parent itself does not include Node; derived image lines may add it.
- The selected Symfony8.2.0-BETA1 and AI Mate1.0.0-BETA1 project template uses prerelease-latest policy resolved to exact versions. New images are unavailable until publication verifies the full integration.
- Use trusted checkouts: starting patched Mago or Serena can execute mago.toml extension-host commands as the mapped user, with the container's mounts, environment and network access. Image identity verifies the toolchain, not project worker code.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
- mago-baseline is the upstream release binary, not a local unpatched build.
