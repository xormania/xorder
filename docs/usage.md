# Running project commands

For `uxor-dev` in Claude cloud, start with the
[session quick start](claude-cloud.md) and [uxor runner](uxor.md).
They cover blocked dist downloads, sandbox disk limits and read-only dependency
reuse across worktrees.

Choose an available digest from [the catalog](../catalog.json). The placeholders
below are instructions to substitute that value, not published image names.
The host needs Linux Docker container execution, Compose v2 for services, a
mountable project workspace and registry/dependency network access.

## Workspace and caches

From a clone of this repository:

```sh
export IMAGE='<catalog digest_reference>'
export WORKSPACE='/absolute/path/to/project'
export CACHE_VOLUME='my-project-dev-cache'
bash scripts/run-image.sh "$IMAGE" php --version
bash scripts/run-image.sh "$IMAGE" composer install --no-interaction --prefer-dist
bash scripts/run-image.sh "$IMAGE" php bin/phpunit
```

The wrapper mounts the workspace at `/workspace`, gives the container your UID
and GID using `PUID`/`PGID`, and persists `/home/dev`. The default image command
is Bash; the default effective user is dev (1000:1000). The entrypoint starts as
root to adjust home/cache ownership and then drops privileges. It never changes
the project's entire bind mount ownership. A cache belongs to one project/user;
avoid sharing it with concurrent processes that use different UIDs.

A root-owned checkout, including one in a Claude cloud session, can use
`PUID=0 PGID=0` explicitly. This keeps the
entrypoint's CA setup and home/cache handling while running the command as root;
there is no need to bypass the entrypoint or recursively change project ownership.
The wrapper honors these overrides:

```sh
PUID=0 PGID=0 bash scripts/run-image.sh "$IMAGE" composer install --no-interaction
```

For direct invocation:

```sh
docker run --rm --init \
  -e PUID="$(id -u)" -e PGID="$(id -g)" \
  --mount "type=bind,src=$WORKSPACE,dst=/workspace" \
  --mount type=volume,src=my-project-dev-cache,dst=/home/dev \
  "$IMAGE" bash -lc 'composer install --no-interaction && composer check-platform-reqs'
```

Use the project's commands and lockfiles. PHPUnit, Symfony framework libraries,
Panther and Python application packages are project dependencies. The image
does not prepopulate `vendor/`, `.venv/`, or a Rust target directory. Xdebug is
installed but off by default; add `-e XDEBUG_MODE=coverage` or `debug` as needed.

## PostgreSQL and Redis

The [Compose recipe](../examples/php/compose.yaml) defines named services,
health checks and volumes. Its disposable fixture credentials are for local
development. Adapt existing project Compose rather than changing its database.

```sh
export IMAGE='<catalog digest_reference>'
export WORKSPACE='/absolute/path/to/project'
export PUID="$(id -u)" PGID="$(id -g)"
docker compose -p my-project -f examples/php/compose.yaml run --rm dev composer install
docker compose -p my-project -f examples/php/compose.yaml run --rm dev php bin/phpunit
docker compose -p my-project -f examples/php/compose.yaml down
```

The container reaches PostgreSQL at `postgres:5432`, Redis at `redis:6379`.
`DATABASE_URL`, `DATABASE_DSN` and `REDIS_URL` are supplied by this recipe; the
project's configuration may use different variable names. No host port is
required for container-to-container access. `down` stops processes but preserves
data and cache volumes. Add `--volumes` only when deliberately discarding this
project's disposable data. Cache reuse does not keep service processes alive.

PostgreSQL is `postgres:17-trixie`; Redis is `redis:7.4`. These explicit service
lines may receive upstream patches. Release records measure the development
image; they do not claim those moving companion tags are immutable.
Mercure should use the consuming project's existing official
[`dunglas/mercure`](https://github.com/dunglas/mercure) image and configuration.
Keep its version, JWT keys, URL and allowed origins explicit. Mercure is not
bundled in the CLI profiles or needed by their acceptance fixture. FrankenPHP's
upstream Caddy binary includes Mercure; use the consuming repository's configuration.

## Browser workflow

Use `php-browser` for a project with Panther browser tests. It provides
`/usr/bin/chromium`, `/usr/bin/chromedriver`, matching Debian packages and fonts;
the `PANTHER_CHROME_BINARY` and `PANTHER_CHROME_DRIVER_BINARY` variables identify
them. Install Panther using the project's Composer lockfile.

The readiness fixture uses headless Chromium and clicks a JavaScript button
through a real Panther WebDriver session. It starts an actual PHP/Symfony
application inside the same container and writes a screenshot to the mount.
It uses `--no-sandbox` for hosts that disallow Chromium sandbox namespaces; use
that option only with trusted development content. Compose supplies 1 GiB of
shared memory. A project server in another container needs its service hostname,
not `127.0.0.1`.

## FrankenPHP and uxor

`php-frankenphp/8.4-trixie` and `8.5-trixie` add Caddy/FrankenPHP, APCu and worker-mode execution
to the loaded PHP toolchain. Supply the project's Caddyfile, worker entrypoint
and PHP settings. Its default command is Bash, like the other library images.

The [`uxor` profile](uxor.md) offers `uxor-dev/8.4-trixie` and `8.5-trixie`,
which add Node 22/npm and a cached Tailwind CLI to the exact FrankenPHP parent. It overlays the checkout's
existing demo Compose files, Caddyfile, entrypoint and PHP configuration, and
starts the official Playwright container at the version in its lockfile. Tests
execute inside the app container; no Docker socket is mounted there.
The runner supports `phpunit`, per-command Xdebug coverage, and an opt-in
read-only Git metadata mount for linked worktrees; see the profile for commands.

New definitions describe intent until publication produces an available catalog
entry. Use the catalog's digest, or build locally for validation; never guess a
published tag.

## Python and Rust

```sh
# python-dev; use uv.lock from the project
bash scripts/run-image.sh "$IMAGE" uv sync --locked
bash scripts/run-image.sh "$IMAGE" uv run --locked pytest
# rust-dev; use Cargo.lock and the project's toolchain requirements
bash scripts/run-image.sh "$IMAGE" cargo test --locked
bash scripts/run-image.sh "$IMAGE" cargo clippy --locked -- -D warnings
bash scripts/run-image.sh "$IMAGE" cargo build --locked --target wasm32-unknown-unknown
```

Python's uv cache lives in `/home/dev/.cache/uv`, Composer's home in
`/home/dev/.composer`, and Cargo's home in `/home/dev/.cargo`. The Rust target
is tested for compilation; a WASM execution runtime is not advertised.

## Readiness and real consumer acceptance

Run the same public recipe that CI executes:

```sh
bash scripts/verify-image.sh 'php-dev/8.4-trixie' "$IMAGE"
# For the corresponding selected profiles:
bash scripts/verify-image.sh 'php-browser/8.4-trixie' "$IMAGE"
bash scripts/verify-image.sh 'python-dev/3.14-trixie' "$IMAGE"
bash scripts/verify-image.sh 'rust-dev/1.99-trixie' "$IMAGE"
```

Select the matching IMAGE for each line, not a single image for all commands.
Behind a proxy that signs HTTPS with a private CA, supply its PEM certificate
or bundle using the same wrapper option as project commands:

```sh
CA_CERTIFICATE='/absolute/path/to/proxy-ca.pem' \
  bash scripts/verify-image.sh 'python-dev/3.14-trixie' "$IMAGE"
```

The readiness wrapper forwards that file read-only to containers that need it;
see [network access](#network-access). Without `CA_CERTIFICATE`, the recipe keeps
its normal trust configuration.

The script copies a locked mock consuming project to a disposable bind mount,
starts real services where needed, installs dependencies, runs behavior checks,
checks host ownership, exercises cache persistence and cleans up its own data.
PHP tests intl/mbstring/DOM/bcmath, PostgreSQL and Redis, Composer platform
requirements and Symfony HTTP behavior. Browser checks add Panther and a
screenshot. Python checks an installed package and PostgreSQL; Rust checks
tests, formatting, Clippy and WASM compilation. CI reports elapsed time and
image size; no speculative size/time threshold is imposed.

## Network access

Image pulls require host/daemon access to **`ghcr.io` and
`pkg-containers.githubusercontent.com`** (registry and layer downloads).
GitHub [documents these endpoints](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#communication-requirements-for-github-hosted-runners).
Project dependencies need their own hosts, including GitHub, Composer repositories,
importmap/CDN resources and npm as appropriate. The Playwright companion is pulled
from `mcr.microsoft.com`; use the registry's redirects as required by your network.

The wrappers forward `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` when set on the
host. Include service names, localhost and 127.0.0.1 in NO_PROXY for local HTTP
connections. Host networking policy is not automatically inherited by a Docker
container. Run the readiness recipe to verify downloads inside the selected image.

For a proxy that signs HTTPS with private CAs, mount **a PEM CA certificate or
multi-certificate PEM bundle** read-only and set `LIBRARY_CA_FILE` to its absolute
container path. `CA_CERTIFICATE` accepts either format in the wrappers. The root
entrypoint validates every certificate, splits the bundle into one certificate
per `.crt` file for Debian's trust updater, and updates system trust before
dropping privileges. Blank lines and `#` comments between certificates are
accepted. Empty files, incomplete blocks, unrelated text and invalid certificates
fail startup before existing trust changes. The private staging directory is
removed on success or failure.
Composer, curl and git use the trusted bundle; Node gets `NODE_EXTRA_CA_CERTS`.
Explicit existing Composer/Node CA settings take precedence.
In `python-dev` and `php-serena`, supplying `LIBRARY_CA_FILE` also enables uv's
system certificate store with `UV_SYSTEM_CERTS=true`, unless an explicit uv TLS
setting is already supplied. With no `LIBRARY_CA_FILE`, uv's trust selection is
unchanged. Tool command-line TLS options retain their own precedence.

```sh
export CA_CERTIFICATE='/absolute/path/to/proxy-ca.pem'
bash scripts/run-image.sh "$IMAGE" composer install --no-interaction
# Python dependency resolution uses the installed proxy CA too:
bash scripts/run-image.sh "$IMAGE" uv sync --locked
# Equivalent direct invocation:
docker run --rm -e LIBRARY_CA_FILE=/run/proxy.pem \
  --mount "type=bind,src=$CA_CERTIFICATE,dst=/run/proxy.pem,readonly" \
  "$IMAGE" curl --fail https://github.com
```

Missing/invalid certificates fail startup. This option needs the normal root
entrypoint; with an explicit non-root `--user`, use a pre-trusted derivative or
mount a CA bundle and set the tool's CA option (`COMPOSER_CAFILE`, `CURL_CA_BUNDLE`,
`GIT_SSL_CAINFO`, `NODE_EXTRA_CA_CERTS`) directly. Keep public roots in that bundle
when the tool replaces its default trust store. Never disable TLS verification.
Repeated setup replaces this option's files in
`/usr/local/share/ca-certificates/library-proxy/`, removes the older
`library-proxy.crt` layout, and preserves other installed roots. Removing
certificates from a replacement bundle removes their managed trust on the next
setup; a startup with no `LIBRARY_CA_FILE` leaves already installed trust alone.
The Docker host/daemon must separately trust the proxy to pull images: a
container entrypoint cannot fix a pull that happens before it starts.
No Docker socket is mounted by these recipes.
