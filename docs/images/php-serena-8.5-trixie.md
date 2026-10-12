# php-serena/8.5-trixie

Prepared Serena v2 REPL, PHPactor and JavaScript/TypeScript navigation with MCP, shell queries and trusted source editing.

**Not available:** no verified public release. The following capabilities describe the intended profile.

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
- Twig and YAML service identifiers use text search; PHP, JavaScript and TypeScript have semantic navigation.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
