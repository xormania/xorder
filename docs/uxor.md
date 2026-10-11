# uxor development and tests

This optional profile targets the actual
[`xormania/uxor`](https://github.com/xormania/uxor) repository.
For Claude cloud sessions, read the [session quick start](claude-cloud.md)
before starting a stack or importing another worktree's dependencies.

The repository is now named **uxor**. Published `flowbite-xor-dev` image families,
registry packages, exact tags and digests remain usable under their existing
names. Requirement and acceptance fixture filenames retain those names too.
Use `examples/uxor/run.sh` for current commands; the legacy
`examples/flowbite-xor/run.sh` path and `FLOWBITE_PROJECT` variable remain
accepted. `UXOR_PROJECT` is the preferred explicit project setting and takes
precedence when both variables are set. For a given workspace, default Compose
names, relay ownership keys and local
state/cache identities remain unchanged, so both runner paths manage the
same stack. Retain an existing explicit project name when continuing it.

The acceptance fixture pins commit
[`c8878af`](https://github.com/xormania/uxor/tree/c8878af66897d8c10af694050a7a588166942117),
inspected on 8 October 2026: Symfony 8.1, UX 3.5.1, PHP 8.5/FrankenPHP workers,
Node 22, Playwright 1.58.2 and Tailwind v4.3.3. Both PHP 8.4 and 8.5 profiles
exercise this baseline, including the PHPUnit suite. Choose 8.4 for the
minimum-version checks and 8.5 for the browser CI runtime.

| Part | Supplied by |
| --- | --- |
| PHP extensions, Composer, Symfony CLI, FrankenPHP/Caddy, APCu | `php-frankenphp/8.4-trixie` or `8.5-trixie` |
| Node 22, npm and checksum-verified Tailwind v4.3.3 CLI | `flowbite-xor-dev/8.4-trixie` or `8.5-trixie`, derived from the exact FrankenPHP parent |
| Caddy/Mercure, worker mode, PHP ini, app entrypoint and source layout | The current uxor checkout's `demo/` configuration |
| Application and Playwright packages | `composer.lock` and `package-lock.json` using Composer install and npm ci |
| Browser binaries and fonts matching upstream screenshot baselines | Official `mcr.microsoft.com/playwright:v<locked-version>-noble` companion |

Definitions alone are not pullable releases. Select an available
`flowbite-xor-dev` digest from the [catalog](../catalog.json) after publication,
or build the root and derivative locally for validation:

```sh
python3 scripts/build.py php-frankenphp/8.5-trixie image-library-check:dev --children
```

Select the cached profile for either runtime from the verified catalog:

```sh
python3 scripts/library.py select tests/requirements/flowbite-xor.json
python3 scripts/library.py select tests/requirements/flowbite-xor-8.4.json
```

From a clone of this library, with an existing uxor checkout:

```sh
export IMAGE='<verified flowbite-xor-dev digest_reference>'
export WORKSPACE='/absolute/path/to/uxor'
bash examples/uxor/run.sh up
bash examples/uxor/run.sh status
bash examples/uxor/run.sh test tests/e2e/lab.calendar.spec.ts
bash examples/uxor/run.sh test --shard=2/3
bash examples/uxor/run.sh phpunit
bash examples/uxor/run.sh php-tests all
PHPUNIT_XDEBUG_MODE=coverage bash examples/uxor/run.sh phpunit --coverage-clover var/coverage.xml
bash examples/uxor/run.sh exec bash -c 'cd demo && bin/console tailwind:build'
bash examples/uxor/run.sh down
```

`up` syncs recipes before Composer setup, seeds the matching cached Tailwind
binary, compiles the project's Tailwind CSS before FrankenPHP starts, starts
the demo and browser, runs npm ci, warms Symfony's test cache and
checks a worker-served application page. The same application page is used by
the healthcheck; Caddy metrics alone do not establish app readiness. Set
`APP_READY_PATH=/your-public-page` if `/` is not the appropriate readiness route.
The profile preserves the repository's application entrypoint, database wait
and runtime behavior. Playwright's config builds stale Tailwind CSS before tests. There is no
host Node dependency. The runner needs Python 3, Docker/Compose and registry/dependency
access. Project names default to the workspace basename plus a stable path hash.
Each workspace also gets stable loopback HTTP/HTTPS ports in 20000–29999
(the HTTPS port is reused for HTTP3/UDP). A hash collision or occupied host port
is reported before startup; select an explicit slot to resolve it.

```sh
bash examples/uxor/run.sh --slot 2 up      # HTTP 20004, HTTPS/HTTP3 20005
bash examples/uxor/run.sh --slot 2 status
bash examples/uxor/run.sh --slot 2 down
```

Explicit slots 0–14999 select ports in 20000–49999; the smaller default range
avoids the usual Linux ephemeral port range. Use the same slot for every command. `UXOR_PROJECT`, `HTTP_PORT`,
`HTTPS_PORT` and `HTTP3_PORT` override derived values individually. The default
HTTP3 port follows the selected HTTPS port. Port probes apply to a local Docker
engine; Compose reports final binding conflicts, including races and remote
engine conflicts. An explicit project already attached to another checkout is
rejected. Existing unlabeled profiles are recognized by their `/app` workspace
bind mount. To retain the previous runner's fixed defaults, explicitly set
`UXOR_PROJECT=flowbite-xor-library HTTP_PORT=8084 HTTPS_PORT=8444 HTTP3_PORT=8444`. `up` always asks Compose to reconcile configuration and bring stopped services
back. It verifies retained Composer/npm metadata, then reuses expensive setup
only when source inputs, effective Compose configuration, installed dependency
state and container identities match a previous successful run. Source hashing
uses the checkout's Git ignore rules, so generated recipes/assets do not trigger
a recreation loop. Changes to source/configuration, CA bytes, image, mounts or
proxies cause setup to be reconsidered. Readiness is checked again each time.
The setup receipt is a local cache, not an authority over changed inputs.
`status` checks Docker, service state/health and a live application request without
starting containers, reading package locks or requiring `IMAGE`. It exits 0 only
when both app/browser services are running and healthy and the page responds;
otherwise it exits 1. Starting Docker itself remains a host responsibility.

`down` preserves caches; `down --volumes` deliberately removes
this profile's disposable Caddy/home/demo-var volumes.

Images with verified `php-testing` and `pcov` capabilities also offer
`php-tests coverage`, `php-tests phpstan`, and `php-tests all`. The aggregate
command runs the demo's lock-owned PHPUnit with PCOV, then the kit's PHPStan
configuration from the repository root. It explicitly selects the isolated,
image-prepared PHPStan tool lock, supplies the demo autoloader, and finds recipe
PHP directories from their manifests. Environment overrides described in
[PHP test tasks](php-tests.md) select other configurations, paths, or drivers.
Earlier exact image pins retain the `phpunit` command and require a deliberate
verified image upgrade before using these additional commands.

Xdebug is installed and stays off for the server and ordinary PHPUnit runs.
`PHPUNIT_XDEBUG_MODE=coverage` enables it only in the PHPUnit exec process,
including when the containers were started with Xdebug off. Reports live under
`demo/var` in the named cache volume; retrieve one with
`run.sh exec cat demo/var/coverage.xml`. PHPUnit comes from the demo lockfile.
The runner sets `APP_ENV=test`, `APP_DEBUG=1` and `CREATE_SNAPSHOTS=false` for
this process, independently of the development server's environment.

The image stores a checksum-verified Tailwind v4.3.3 binary at `/opt/tailwind`.
After Composer is ready, `up` reads the demo's resolved tailwind-bundle config
and copies the binary to `demo/var/tailwind/v4.3.3/tailwindcss-linux-x64`.
Fresh worktrees and cache volumes reuse those image bytes. A different pinned
version, explicit binary path or platform keeps the bundle's normal behavior.
The project configuration remains authoritative. Use the new 8.4 image or the
8.5 v1.1.0 image with this runner; the older 8.5 v1.0.0 image has no cache helper.

For a linked Git worktree, export `WORKTREE_GIT=1` before all runner commands:

```sh
export WORKSPACE='/absolute/path/to/uxor-worktree'
export WORKTREE_GIT=1
bash examples/uxor/run.sh up
bash examples/uxor/run.sh exec git status
```

This option requires host Git and mounts the common repository metadata,
including the selected worktree's private metadata, read-only at its host path.
It overlays `/app/.git` with an absolute pointer stored in the host user's
`$XDG_CACHE_HOME/xorder/worktrees` (default `$HOME/.cache`).
The checkout's `.git` file is unchanged, including relative pointers. The
cached pointer survives container restarts. Git reads work inside the container;
run Git writes such as add/commit on the host. Ordinary checkouts need no option.

The browser shares the app container's network namespace. Its localhost port
3000 is reachable by the existing Playwright configuration without publishing
that port on the host. The runner uses `DEMO_URL=https://localhost` and
`PHP_BINARY=php`, so PHP helpers execute directly in the same app container.
`PW_BROWSER_SERVER=/bin/false` tells Playwright to reuse the already healthy
server and fail if it disappears. Neither container has a mounted Docker socket.
The version is read from package-lock.json and checked against package.json;
the official companion and its server package use that same exact version.

The profile overlays the repository's existing Compose files and mounts its
Caddyfile plus `10-app.ini`/`20-app.dev.ini`. That preserves worker execution,
Mercure directives and the current upload limits (2M per file, 8M per request).
It supplies a prebuilt development image instead of rebuilding the demo's PHP
toolchain. Exact CI artifact parity requires using the same selected library
digest in project CI; matching a PHP minor alone is insufficient. Keep the
repository's production image build separate from this development profile.

The profile verifies installed Composer package names, versions, source/dist
references, package directories, generated runtime metadata and a usable autoloader
against `demo/composer.lock`, including dev requirements. Composer also validates
the lock against `composer.json`. A nonempty `vendor/` alone is insufficient.
An imported matching vendor tree regenerates autoloads and runs the project's
`post-install-cmd` hooks once; unchanged verified setup can be reused. A changed
lock or incomplete vendor tree goes through Composer install. Project hooks
remain authoritative and may still require network access (for example importmap
assets). This is metadata validation, not a checksum audit of every vendor file.

Importmap asset readiness is checked independently on every `up`, even when
Composer setup is reused. The profile uses Symfony's own importmap reader and
storage paths to check the requested versions, package files and additional
files such as CSS fonts. Complete installations need no importmap download;
incomplete ones run the project's `importmap:install` command before readiness.
The runner keeps the project's other Composer hooks enabled.

After a complete installation, the runner records the original `installed.php`
bytes and hashes of its required assets in `demo/var/xorder/importmap-state.json`
(the persistent demo-var volume). Before Composer hooks run, a missing manifest
can be restored from that receipt only when the importmap, locked AssetMapper
version/reference, and every captured asset still match. Dependency mappings,
package aliases and extra-file metadata are preserved exactly. Changed or
missing assets, changed inputs, and corrupt receipts use normal Symfony
installation; a filename-only seed cannot establish the missing metadata.
Preserve the whole `assets/vendor/` directory, including `installed.php`, when
bringing in a prepared installation. A first installation without that metadata
or a matching receipt requires network access through the configured proxy.

The defaults are `IMPORTMAP_FILE=importmap.php` and
`IMPORTMAP_VENDOR_DIR=assets/vendor`, relative to `/app/demo`. If the project
configures other paths in Symfony, set these variables to those same paths
before `up`. An application without the selected importmap file skips this
asset step. No package versions or generated dependency mappings are invented.

Composer installation is dist-only. `up` rejects a source preference before
starting Docker work, checks that source fallback is disabled in Composer 2.10+
and that locked packages have supported dist artifacts, and refuses to update
an incomplete source-installed tree. A blocked archive download stops setup;
it does not retry with git clones. Complete source-installed packages can still
be verified and reused without another install.

For a writable existing host Composer download cache:

```sh
export COMPOSER_CACHE_DIR='/absolute/path/to/composer-cache'
bash examples/uxor/run.sh up
```

### Reuse existing dependencies without rewriting them

```sh
bash examples/uxor/run.sh up --reuse-only
```

Alternatively set `XORDER_REUSE_ONLY=1` for a session wrapper. This mode ignores
an inherited source preference because it performs no installation. Before
starting or recreating services, a one-off container checks Composer manifest/
lock agreement, package metadata, generated autoloads, npm manifest/lock/package
agreement and Symfony importmap metadata/assets. Incomplete inputs fail with
the missing setup reported. No packages, autoloads, importmap files or readiness
markers are repaired; cache snapshots are neither restored nor stored, recipe
sync is skipped, and Composer setup hooks and npm ci do not run.

`demo/vendor`, `node_modules` and the configured importmap vendor directory
are mounted read-only in PHP. The dependency paths must already exist inside
the workspace; the importmap defaults are the paths below in this guide.
This protects hardlinked package files from application/bootstrap writes too.
Use the flag on every `up`; later `exec` commands use the retained container
and its read-only mounts. Changing back to ordinary `up` restores writable
mounts and normal setup behavior.

A missing or changed Composer/npm readiness marker is reported as an unrecorded
setup step. Complete dependency metadata can be adopted without pretending
that project hooks ran or creating a marker. Application health must still
pass before `Ready` is printed. Symfony runtime/test caches, compiled Tailwind
CSS and the host runner receipt remain writable and local to the stack; this
mode protects dependency trees rather than making the whole application read-only.
Prepare missing hooks, recipes or assets in a private writable tree before reuse.

The runner creates a separate `xorder/<workspace-hash>` cache under that existing
directory and mounts only that child. Writable dependency archives are not shared
between workspaces. The cache bind is outside HOME and its ownership is never
changed. Ensure the child is writable by `PUID:PGID`. Without a host cache, Composer uses the persistent named
home volume. Source preference uses Composer's normal source/dist fallback; it
requires source-repository access and does not promise success through every
restricted gateway.

`HTTP_PROXY`, `HTTPS_PROXY`, their lowercase forms and `ALL_PROXY`/`all_proxy`
are forwarded. In automatic mode, loopback endpoints (`localhost`, 127.0.0.0/8,
IPv6 `::1`, including mapped IPv4) get a TCP relay bound only to the local Docker
bridge gateway. Container proxy URLs use that numeric address, so reaching the
proxy needs no container DNS. The upstream proxy still handles authentication,
CONNECT and destination policy; TLS verification remains enabled. Host commands
retain their original proxy settings. Tools must honor proxy configuration;
this does not provide general DNS or transparently proxy every protocol.

Each workspace/project owns its relay. It survives `up`, is reused by later
commands, restores the same ports after an interrupted relay, and is stopped by
that project's successful `down`. Concurrent worktrees do not share relay
ownership. Changed upstream endpoints require `up`. Private state under the
host temporary directory contains endpoints/ports and an authenticated local
control token, never proxy credentials. Keep the checkout available while using
the runner. After host reboot, run `up` again before using retained containers.

Before opening an upstream connection, the relay checks the client's source IP
against Docker's live container addresses and the runner's
`dev.xorder.proxy-owner` label. Only this workspace/project's PHP container
(including the browser sharing its network namespace) can use its relay.
Unrelated containers and failed Docker lookups are rejected. Addresses are
checked on every connection so a removed container's IP is not kept authorized.
This requires continued host-side Docker access; host networking is unsupported.
Docker daemon administrators remain trusted, as they can create labeled
containers or join another container's network namespace.

Automatic forwarding requires a Docker bridge address bindable from the sandbox
where the upstream proxy listens. A remote daemon, Docker Desktop VM, rootless
engine, or isolated Docker socket may need a separately configured reachable
proxy; the runner reports an unavailable route instead of dropping the proxy.
Set `PROXY_PASSTHROUGH=0` to disable container proxies, or
`PROXY_PASSTHROUGH=1` to forward URLs unchanged deliberately. Upper/lowercase
`NO_PROXY` settings retain their entries and add localhost, loopback and the
profile's service names. Readiness requests explicitly bypass proxies. Proxy
values are not printed in diagnostics.

The app uses your UID/GID by default. `PUID=0 PGID=0` supports a root-owned
sandbox checkout. Only the named home, Caddy and demo-var cache volumes have
their ownership adjusted. The checkout supplies writable vendor/node_modules
directories for the chosen user. Set `CA_CERTIFICATE=/absolute/proxy-ca.pem`
for the shared [CA trust option](usage.md#network-access); the Node browser
companion gets the mounted certificate as an extra trusted CA as well.

The readiness recipe tests persistent workers and executed-line Xdebug coverage
plus the shared PHP/native/TLS/user contract. It then starts the pinned real
consuming repository as a linked Git worktree, checks Git access, builds Tailwind
from the seeded binary, runs PHPUnit with a nonempty Clover coverage report,
and runs calendar, dropzone, both data-table and both editor lab specs. It never updates screenshot baselines. A source update
to `tests/fixtures/flowbite-xor/consumer.json` deliberately updates that consumer
baseline; ordinary users run their current checkout.

References:

- [Inspected demo Dockerfile](https://github.com/xormania/uxor/blob/c8878af66897d8c10af694050a7a588166942117/demo/Dockerfile)
- [Inspected CI and PHP version coverage](https://github.com/xormania/uxor/blob/c8878af66897d8c10af694050a7a588166942117/.github/workflows/ci.yml)
- [Existing browser server and PHP helpers](https://github.com/xormania/uxor/blob/c8878af66897d8c10af694050a7a588166942117/playwright.config.ts)
- [FrankenPHP image and non-root guidance](https://frankenphp.dev/docs/docker/)
- [Playwright version matching](https://playwright.dev/docs/docker#image-tags)
