# php-serena/8.5-trixie

Prepared Serena v2 REPL, PHPactor and JavaScript/TypeScript navigation with MCP, shell queries and trusted source editing.

Available revision: **1.1.3**. Pin:

```text
ghcr.io/xormania/php-serena@sha256:a21a6d18ae9be3d528fb01f19446769904ca4898fdf19b6bd4176769de809e04
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:25:55.892206Z.

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
| library-serena | Serena 2.0.0.dev0 (b79e2a55, PHPactor 2025.12.21.1) |
| node | v22.23.3 |
| php | PHP 8.5.11 (cli) (built: Oct  6 2026 01:22:31) (NTS) |
| phpactor | Phpactor 2025.12.21.1 |
| phpstan-isolated | PHPStan - PHP Static Analysis Tool 2.3.0 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| symfony | Symfony CLI version 5.22.2 (c) 2021-2026 Fabien Potencier (2026-10-16T16:25:57Z - stable) |
| typescript-language-server | 5.1.3 |
| uv | uv 0.12.19 (x86_64-unknown-linux-musl) |

Extensions: `bcmath`, `core`, `ctype`, `curl`, `date`, `dom`, `fileinfo`, `filter`, `gd`, `hash`, `iconv`, `intl`, `json`, `lexbor`, `libxml`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `pcntl`, `pcov`, `pcre`, `pdo`, `pdo_mysql`, `pdo_pgsql`, `pdo_sqlite`, `pgsql`, `phar`, `posix`, `random`, `readline`, `redis`, `reflection`, `session`, `simplexml`, `sockets`, `sodium`, `spl`, `sqlite3`, `standard`, `tokenizer`, `uri`, `xdebug`, `xml`, `xmlreader`, `xmlwriter`, `zend opcache`, `zip`, `zlib`.

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,245.1 MiB (1,305,562,766 bytes) |
| Build, cache export and image load | 39.42s |
| Public-artifact behavior and inventory verification | 91.34s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:25:11.078823Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/php-serena@sha256:9aa4981b585e76a812cc3070381e55488ffb86a850effa600779919c48b2d132`; 1,243.7 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:55:34.549911Z.

[Release notes](../releases/php-serena-8.5-trixie-v1.1.3.md).

Capabilities: `composer`, `javascript-semantic-tools`, `mutation-testing`, `native-build`, `node`, `offline-php-semantic-tools`, `pcov`, `php`, `php-testing`, `phpactor`, `phpstan-isolated`, `postgresql-client`, `serena-shell`, `serena-v2-repl`, `symfony`, `typescript-semantic-tools`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Serena MCP and Symfony recipe](../serena.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- Optional per-worktree indexes are reused only for matching source, dependencies, configuration and image; REPL state persists only in a running session.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- PHP semantic operations are backed by PHPactor; Twig and Symfony container/service semantics are not established by PHP symbol tests.
- Project PHP dependencies come from Composer lockfiles.
- Serena is pinned to the tested v2 beta revision b79e2a55f9d4072084977dd35bd07d31146d88b9.
- The REPL can execute Python with container permissions. The standalone runner does not implement Agentscient role permissions or coordination.
- The consuming project owns its Composer dependencies. Prepared language-server startup needs no runtime downloads.
- The public runner mounts source read-only by default; pass --write explicitly for trusted editing sessions.
- The upstream source and original lock remain identified separately from the xorder dependency-only security patch and effective uv lock.
- Twig and YAML service identifiers use text search; PHP, JavaScript and TypeScript have semantic navigation.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
