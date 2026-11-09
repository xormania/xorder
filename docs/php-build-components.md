# Prepared PHP CLI build components

`php-dev` composes internal prepared build components while keeping its public
PHP 8.4/8.5 image lines and runtime contract. `php-browser`, `php-toolkit`, and
`php-serena` continue to derive from the exact PHP development parent.
The component definitions are build inputs; they do not create selectable
public catalog images or claim publication evidence.

| Component | Scope | Inputs that require preparing it again |
| --- | --- | --- |
| `php-cli-foundation-84`, `php-cli-foundation-85` | Exact upstream PHP CLI ABI, Debian workstation packages, `dev` user and workspace directories | Matching upstream PHP base, shared workstation installer, observed Debian package feeds |
| `php-native-84`, `php-native-85` | PHP extensions compiled against the matching foundation | Exact foundation, extension recipe, Redis/Xdebug/PCOV pins, observed package feeds |
| `php-tool-downloads` | Verified Symfony CLI and Infection bytes, prepared with its own fixed Python downloader image | Download pins, download helper/recipe, deliberate downloader-image changes |
| `php-tools-portable` | Composer and locked isolated PHPStan dependencies | Composer pin, isolated tool Composer lock, preparation recipe, its PHP 8.4 build foundation |
| Final `php-dev` | Matching native component, portable PHP tools, retained downloads, runtime PHPStan selection, existing test helpers, configuration and entrypoint | Exact selected components and final image inputs |

Changing Symfony CLI, Infection, Composer or the isolated PHPStan lock does not
compile native PHP extensions again. Debian workstation feeds and PHP/Python
runtime-image refreshes do not change `php-tool-downloads`: its downloader has a
separate exact image pin. Fresh builders pull the already prepared download
component instead of depending on a previous builder’s cache mount. A PHP 8.5
composition can use the same portable payload prepared with the PHP 8.4 foundation. The portable payload
retains PHPStan's complete upstream Turbo bundle; only the final composition
runs `package-phpstan.py` against its actual PHP ABI. A read-only donor mount
copies and filters the bundle in one final-image RUN layer, so discarded ABI payloads never enter a committed image layer. Its existing
report records the retained binary and SHA-256. An unsupported or missing ABI
fails the build.
Copying a PHPStan bundle already pruned by the builder's PHP version would lose
that guarantee.

The portable PHP component prepares its Composer project without scripts or plugins,
checks platform requirements, and verifies that installation preserved the
manifest and lock bytes. Composer/PHPStan preparation currently remains qualified
by its PHP 8.4 foundation; refreshing that foundation may reprepare these Composer
dependencies. Symfony CLI and Infection have an independent prepared download
component using the shared SHA-256 helper. Its content cache is used only after
digest validation, and the component retains the payload for subsequent builds;
BuildKit download-cache presence alone does not establish that payload exists.
Final composition checks Composer platform requirements again and executes
Infection on the consuming runtime. Download payload modes are explicit: Symfony
CLI is executable and Infection remains readable by the mapped development user.

Toolkit validator and clean Symfony baseline lockfiles remain private to the
`php-toolkit` recipe. A validator lock change does not become a PHP foundation,
native-extension or portable-tool input. Its baseline remains a separate install
layer. Existing real PHP, PostgreSQL, Redis, browser, coverage, mutation and
Toolkit acceptance recipes still validate the final images.

FrankenPHP and UXor retain their current recipes, pins and build behavior. This
CLI decomposition does not change their shared installer files. A future move
would need its own explicit runtime and ZTS compatibility work.

## Existing Serena/PHPactor compatibility image

`php-serena/8.5-trixie` keeps its existing Serena revision, security-adjusted uv
lock, PHPactor pin, launcher, and JavaScript/TypeScript tooling. Its retained
`php-serena-python-85` component builds against the same `php-native-85` donor
used by the final PHP development parent. The venv therefore keeps Debian's
`/usr/bin/python3` path and matching shared-library ABI; no Python 3.12 runtime
or Mago backend is substituted.

The final image copies this prepared environment before the Node/npm overlay.
The independent `php-serena-javascript` component retains the existing Node/npm
and TypeScript payload. Node image and npm-lock changes do not change the Python
component key; Python security-lock changes do not reinstall npm dependencies. A
separate `phpactor-payload` component retains the original verified PHAR, so
Node or Python dependency refreshes do not download PHPactor again. Existing
full Serena acceptance continues to check MCP, PHPactor, JavaScript/TypeScript
navigation, editing and the security-adjusted dependencies.
