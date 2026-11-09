# php-chrome-dev/8.4-trixie

PHP 8.4 Mago/Serena development plus Node 22, Chrome for Testing and Chrome DevTools MCP.

**Not available:** no verified public release. The following capabilities describe the intended profile.

Capabilities: `browser`, `chrome-devtools-mcp`, `chrome-for-testing`, `chromium`, `composer`, `mago`, `mago-lsp-extensions`, `mago-sdk-compatible`, `mutation-testing`, `native-build`, `node`, `npm`, `panther`, `pcov`, `php`, `php-testing`, `phpstan-isolated`, `postgresql-client`, `python-3.12`, `serena-mago-adapter`, `serena-v2-repl`, `symfony`, `uv`, `xdebug`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Mago, Serena and Chrome development recipe](../mago-chrome.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Browser built-in AI APIs require an eligible device and model download; this headless container does not establish their availability.
- Chrome DevTools MCP usage statistics and update checks are disabled by default; CI also sets CI=1.
- Chrome for Testing is installed alongside Debian Chromium; Panther continues to use the inherited Debian browser.
- Chrome may require --no-sandbox where user namespaces are unavailable. Use shm_size: 1gb or --disable-dev-shm-usage.
- Chromium may need --no-sandbox where the host prohibits sandbox namespaces. Use only for trusted development content.
- Linux amd64 only. Rebuild binary hashes are recorded; byte equality across builders is not required.
- Mago 1.58.2 and SDK revision 46df50c96d93d0ac3655c116c375574277cf0b30 use MANA 2.1; Mago 1.59 and MANA 2.2 are incompatible with this pin.
- No PHP-FPM, web server daemon, or Node toolchain is supplied.
- PCOV is disabled by default. library-php-coverage pcov isolates Xdebug for each CLI process; library-php-tests uses project-locked PHPUnit and PHPStan, not global test packages.
- Project PHP dependencies come from Composer lockfiles.
- Python 3.12 is supplied in /usr/local for Serena; Debian Python remains in /usr/bin.
- Serena uses the Mago SolidLSP adapter; the separate php-serena line uses PHPactor.
- The Chrome for Testing index publishes no checksum. xorder verifies its locally acquired archive SHA-256 before extraction and records the installed executable hash.
- The Mago LSP extension is a repository patch, not an upstream API. The PoC recorded an external-edit span defect with a restart workaround.
- The consumer owns Composer dependencies, project configuration and mounted workspaces. No daemons, Docker socket or credentials are installed.
- The php-browser parent itself does not include Node; derived image lines may add it.
- Use trusted checkouts: starting patched Mago or Serena can execute mago.toml extension-host commands as the mapped user, with the container's mounts, environment and network access. Image identity verifies the toolchain, not project worker code.
- Xdebug is off by default; enable with XDEBUG_MODE=coverage or debug.
- mago-baseline is the upstream release binary, not a local unpatched build.
