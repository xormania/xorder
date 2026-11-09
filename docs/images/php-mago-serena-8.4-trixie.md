# php-mago-serena/8.4-trixie

Composable PHP Symfony development with latest selected native Mago, current Serena REPL, matched patched Mago LSP/SDK, and reusable Symfony/AI Mate project preparation.

**Not available:** no verified public release. The following capabilities describe the intended profile.

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
