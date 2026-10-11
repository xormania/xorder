# Isolated Symfony UX Toolkit validation

The source profile in [`examples/php-toolkit`](../examples/php-toolkit/) validates
any kit using its own committed Composer lock and exactly `symfony/ux-toolkit`
3.5.1. It never loads the kit's consuming application's `vendor` directory.
This is a reusable checkout helper, not a newly published catalog artifact.

On a machine with PHP 8.4 or newer and Composer 2:

```sh
examples/php-toolkit/run.sh check /path/to/kit
```

Or select a compatible accepted `php-toolkit` image's exact digest from the catalog:

```sh
IMAGE='ghcr.io/xormania/php-toolkit@sha256:SELECT_FROM_CATALOG' \
  examples/php-toolkit/run.sh check /path/to/kit
```

Docker needs Python 3, a working engine, and access to that image. Archive mode
also needs Git and tar on the host. The mounted kit is read
only. `PUID` and `PGID` default to the invoking user and support `0`.
`PHP_BIN` and `COMPOSER_BIN` select native executable paths when `IMAGE` is unset.
For HTTPS through a custom trust gateway, set `CA_CERTIFICATE` to a readable
absolute PEM file or bundle. Docker mounts it for the shared image entrypoint;
native Composer receives `COMPOSER_CAFILE`. Docker proxy handling uses the same
shared [proxy support](uxor.md) as the development profile: loopback
proxies receive a local Docker-bridge relay for the duration of the command;
`PROXY_PASSTHROUGH=0` disables container proxies. Host settings remain unchanged.
The relay is cleaned up when the command exits.
Its source-address check only admits the running container labeled for that
command; other containers cannot use the relay. Docker lookup failures deny
access, and host networking is unsupported.

The prepared `php-toolkit` image supplies the locked validator dependencies and
clean Symfony baseline under `/opt/xorder/php-toolkit`. Docker execution requires
these prepared paths and makes no Composer distribution downloads. A generic PHP
image cannot substitute for this profile. Until the new lines have verified
release records, they remain unavailable in the catalog; native execution remains
usable with its own prerequisites. `TOOLKIT_NETWORK=none` can verify that prepared
Toolkit and baseline use needs no network after the kit is present locally.
Image-build acceptance sets `TOOLKIT_LOCAL_IMAGE=1` to test the just-built local
candidate before publication. Normal use selects an accepted digest.

`check` runs the upstream `ux-toolkit-kit-lint` and `ux-toolkit-kit-debug`
executables. `lint` and `debug` expose each check independently. At a Git
repository root, lint checks `git archive HEAD`, matching the tree GitHub serves
with `.gitattributes` export exclusions. Debug inspects the supplied checkout.
Use `KIT_MODE=directory` to lint uncommitted working files or a prepared export;
the upstream linter rejects unrelated top-level directories in a kit. A kit
directory outside a Git repository root automatically uses directory mode.

Native execution caches Composer downloads and installs from the committed
validator lock into a disposable directory, so concurrent native checks do not
share a mutable `vendor` tree. Prepared images use their immutable locked tools.
`COMPOSER_CACHE_DIR` selects an existing mounted cache,
defaulting to `${XDG_CACHE_HOME:-$HOME/.cache}/xorder/composer`. A cold run requires
access to the locked packages. Populate this cache in an environment that can
download them before using a sandbox with blocked distribution downloads.

The locks belong to this tooling profile. Updating a consuming application's
dependencies does not change the validator; update its manifest and lock
deliberately and run the consumer verifier when changing the toolkit pin. Changes
to baked locks or baseline source require a fresh image revision and acceptance;
the helper rejects prepared dependencies or source that differ from its checkout.

## Fresh Symfony 7.4 app

Create a separate empty application ready to run `ux:install`:

```sh
examples/php-toolkit/run.sh fresh /tmp/my-toolkit-test-app
cd /tmp/my-toolkit-test-app
php bin/console ux:install button --kit=https://github.com/xormania/uxor
```

`IMAGE` also supports this action. It leaves the app in the supplied host
directory; subsequent commands can use native PHP or the same image with the
app mounted at `/workspace` and Composer's cache mounted as usual.

The destination must not exist. Every run copies a clean baseline into a new
directory. Prepared images copy their baseline source and dependency bytes;
native execution installs the committed lock. No previous consuming app's `vendor`, kit registry,
recipe output, application fixture, or warmed cache is copied. Composer's
download cache remains reusable across runs. The helper refuses an existing
destination instead of deleting an app that may contain user work.

The [baseline](../examples/php-toolkit/symfony-7.4/) pins Symfony components to
the 7.4 line and UX Toolkit, Twig Component, and Stimulus Bundle to 3.5.1 through
the committed Composer lock. Its `symfony.lock` retains exact Flex recipe
references, and `provenance.json` identifies the upstream skeleton and generation
tools. Twig, AssetMapper, and Stimulus are configured; application routes and
kit output are absent. The toolkit is a development dependency, while Twig
Component is a regular dependency so its property accessor is available when
the application boots in production.

Native preparation runs Composer without application auto scripts. Both paths warm the PHP
container and checks that it boots. Each app gets its own generated development
secret in `.env.local`. AssetMapper JavaScript downloads are left
to `php bin/console importmap:install` when a browser test needs them. Recipes may
request additional Composer packages; the consuming project owns those choices
and its updated lock. The baseline does not preload uxor's dependencies,
controllers, fixtures, or rendered pages.

Run `bash tests/fixtures/php-toolkit/run.sh` to check the pinned real kit,
reject malformed input, install its button recipe into a fresh baseline, and
prove a second fresh baseline contains neither that kit nor its generated file.
