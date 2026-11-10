# Mago, Serena and Chrome development images

The authored `php-mago-serena/8.4-trixie` and `php-chrome-dev/8.4-trixie`
lines prepare the toolchain used by
[symfony-chrome](https://github.com/xormania/symfony-chrome). Each starts at
revision 1.0.0. They become selectable only after the normal publication run
builds, verifies and records their exact public digests. Their definitions and
this page do not establish image availability; consult the generated catalog.

| Line | Parent | Additional tools |
| --- | --- | --- |
| `php-mago-serena/8.4-trixie` | `php-browser/8.4-trixie` | Native Mago 1.59.0, patched Mago 1.58.2 LSP/backend, Python 3.12.12, uv 0.12.8, current Serena v2 and Symfony/AI Mate project preparation |
| `php-chrome-dev/8.4-trixie` | `php-mago-serena/8.4-trixie` | Node 22, Chrome for Testing 157.0.8103.38, Chrome DevTools MCP 1.12.0 |

The separate lines compose independently reusable compiled Mago, upstream native
release and frozen Python dependency payloads. Config and adapter changes do not
reinstall dependencies; browser tools change independently. Rust source, build
caches and compiler stay in the build stage. Debian Chromium and chromedriver
remain available for Panther. This Serena variant uses Mago;
`php-serena/8.5-trixie` uses PHPactor and has its own pins and verification.
See [the Symfony composition](symfony-mago.md) for the complete selected tuple,
new-project commands, and prerelease refresh path.

## Provenance and identity

The donor is symfony-chrome's `toolchain.lock.json`, Serena adapter, frozen uv
lock and bounded patches, originating in `xormania/mago-serena_v2-poc`.
The consumer lock takes precedence over its earlier requirements document.
That consumer currently pins the accepted php-browser 1.2.3 digest; xorder's
new lines derive from the declared php-browser line and bind the exact parent
selected by the standard build/publication path.

`/opt/xorder/image-identity.json` records observed versions, Mago source, patch,
Cargo lock, Rust compiler and executable hashes, Serena's patch result and uv
lock hash. `DEV_IMAGE_IDENTITY` points the adapter at this file. The browser
child retains those facts and records its Node, Chrome and MCP versions and
Chrome executable hash. Browser-specific fields are null in the Mago parent.
The adapter checks the Mago executable against the identity before startup.

The Serena dependency component checks out commit
`ede329aaf0c824bea75455a2926f01420d7aa620` and applies the dependency-only
`images/php-mago-serena/serena/security.patch` before `uv sync --locked`.
This updates filelock to 4.2.1 and Werkzeug to 3.1.9 without changing Serena's
application source. The lock uses the prepared local `upstream` directory;
the image records the original commit, patched manifest hash, dependency patch
hash and effective lock hash. Final assembly installs the adapter offline from
the already prepared dependency payload and checks installed requirements.
To regenerate the lock locally, prepare that ignored `upstream` checkout at the
same commit, apply the patch, then run uv 0.12.8 from the Serena project directory.

The release tarball is verified by its locked SHA-256 and installed as
`mago-baseline`; `mago` is the patched source build. `mago-native` is the latest
selected upstream release for ordinary quality commands, with its own version
and executable hash in identity. Cross-builder binary
equality with the PoC is not required. Chrome for Testing publishes no artifact
checksum in its index. xorder pins a locally acquired SHA-256 of the versioned
archive, checks it before extraction, and retains the measured executable hash.
The archive pin was matched against a fresh HTTPS download and the consumer's
cached archive; it is not a vendor-published checksum.

The browser child composes three independently retained build inputs: its exact
Node donor, the hash-verified Chrome for Testing payload, and the integrity-locked
MCP npm closure. The Chrome archive pin belongs to the browser component's own
lock; the MCP version belongs to its npm manifest and lock. Final assembly expands
those component pins into `/opt/xorder/chrome-toolchain.lock.json` before writing
the common identity record. Changing MCP or the PHP parent therefore reuses the
completed Chrome payload. Node's donor remains the qualified consumer pin,
independent of other image families' Node refreshes.

## Runtime

The first entrypoint remains `library-entrypoint`, with `PUID`/`PGID` mapping,
`gosu` privilege drop and `LIBRARY_CA_FILE` support. Its chained Serena hook
seeds `$SERENA_HOME/serena_config.yml` after privileges drop and preserves an
existing configuration. `SERENA_HOME` defaults to `/home/dev/serena`.
The default command is `bash`; consumers can override it with their HTTP server.
The project template is `/opt/xorder/serena/config/project.yml`; the consumer
owns its `.serena/project.yml` and Composer dependencies.

Run these tools against trusted checkouts. Starting patched Mago or Serena
can execute extension-host commands configured by the project's `mago.toml`,
as the mapped user with the container's mounts, environment and network
access. Image identity checks verify the toolchain, not project worker code.
Consumers choose which directories, credentials and network access to expose
to those workers; the image starts no language server or project worker by itself.

Use the accepted digest from the catalog as `IMAGE`, then run the full readiness
recipe on a Docker-capable Linux amd64 host:

```sh
bash scripts/verify-image.sh php-chrome-dev/8.4-trixie "$IMAGE"
docker run --rm -it --shm-size=1g \
  -e PUID="$(id -u)" -e PGID="$(id -g)" \
  -v "$PWD:/workspace" "$IMAGE" bash
```

For owned Chrome on hosts that prohibit user namespaces:

```sh
chrome-devtools-mcp --headless --isolated \
  --executablePath /usr/local/bin/chrome \
  --chromeArg=--no-sandbox --chromeArg=--disable-dev-shm-usage
```

Use trusted development content when disabling the browser sandbox. Prefer
Compose `shm_size: 1gb`; `--disable-dev-shm-usage` is the alternative.
`CI=1`, `CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1` and
`CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1` disable telemetry/update activity.
No daemon, Docker socket or credentials are included. Workspace, home,
`/evidence` and `/packages` mounts belong to the consumer.

## Build, verification and refresh

The existing validation matrix builds exact ancestor inputs and checks each
selected image. The full recipe exercises the inherited PHP contract, native
compilation and CA trust, Mago's patched LSP initialization, and Serena MCP
initial instructions on a one-file PHP project. The Chrome child additionally
checks headless Chrome and MCP initialization, tool enumeration, page listing,
and the experimental third-party tool category.

For a source build of the two new lines:

```sh
python3 scripts/build.py php-dev/8.4-trixie image-library-check:dev \
  --children --reuse-accepted \
  --verify-lines '["php-mago-serena/8.4-trixie","php-chrome-dev/8.4-trixie"]'
```

Use `--build-arg MAGO_NATIVE_TESTS=1` in an explicit Docker build of the
`images/components/mago-lsp/Dockerfile` payload to run its external-analyzer Rust regression test. The normal
publication build retains the default `MAGO_NATIVE_TESTS=0`.
Normal publication uses the shared verified release workflow. No release
record or selectable catalog entry is authored in advance.

Mago/Serena updates require deliberate pin changes, revalidation of both patches
and the adapter, and a fresh compatible image revision. Browser updates change
the browser component's own lock and the child revision. MCP updates change its
npm closure, retaining the browser payload and stable parent when their inputs match.
Shared parent changes still propagate through the existing release dependency
graph. The compressed-image size target is under 2.5 GB for the Chrome child;
actual size and timings must be measured by publication.

Build egress includes GitHub and its release hosts, Docker Hub/GHCR, npm, PyPI,
crates.io and its index/artifact hosts, Debian repositories, and
`storage.googleapis.com`. Runtime smoke checks use local fixtures and stdio;
application dependency installation remains a consumer task.

## Consumer adoption

After an accepted release, replace the consumer's toolchain build stages with
the exact `php-chrome-dev` digest and its project-owned `docker/` scripts.
Read identity through `DEV_IMAGE_IDENTITY`. Remove the migrated adapter,
patches and Python lock from the consumer only after its live Mago, enriched
analysis, Serena and Chrome checks pass against the published image. Update
the consumer lock and `FROM` together, retaining its downstream support check.

The Mago PHP SDK for the experimental extension/LSP backend must match source
revision `46df50c96d93d0ac3655c116c375574277cf0b30` and MANA 2.1.
Mago 1.59 native quality commands are supplied independently. The latest source
removes the experimental server tree; port and verify the LSP/extension tuple
before advancing that backend. The LSP patch is a repository extension;
the PoC's external-edit span defect requires restarting the language server.
Browser built-in AI APIs require eligible hardware and model downloads;
headless container checks do not establish their availability. These lines
support Linux amd64 only.
