# Opt-in live harness environment

`harness-live/trixie` provides Python, Node 22/npm, tmux 3.x, Git, Bash,
certificate handling and the `harnesses` management command. It is a standalone
image and is not selected by a default profile. A definition is not a published
image: use its digest only after normal publication and release acceptance.

Vendor CLIs are installed when the container first starts, rather than shipped
in image layers. First initialization needs network access. Matching persistent
installations are reused; starting another container does not upgrade them.
The committed [pins](../images/harness-live/harness-pins.json) select exact initial
versions. No authentication or model call is part of installation or readiness.

## Start and authenticate

Select the accepted image digest, then start an interactive shell:

```sh
export IMAGE='<accepted harness-live digest_reference>'
export WORKSPACE='/absolute/path/to/project'
export CACHE_VOLUME='my-private-harness-home'
bash scripts/run-image.sh --interactive "$IMAGE" bash
```

Inside the container, start `tmux` and run the desired harness. The operator
answers its authentication, workspace trust and approval prompts. Follow each
vendor's authentication instructions; xorder does not provide account credentials.
The `/home/dev` volume now contains credentials and must remain private to its
owner. Do not publish, share or use it as a public CI cache.

This image keeps `HOME=/home/dev` even with `PUID=0 PGID=0`, so root sessions also
retain their authentication across container replacement. Give each UID its own
private volume. Root startup checks ownership and permissions before any recursive
ownership change or harness launch. It rejects a HOME previously writable by a
lower UID, mixed ownership, group/other-writable content and links importing
external state. A receipt rewritten by that earlier user cannot authorize root
execution. Root use of a custom installation store is checked the same way.
The image's ordinary default is 1000:1000.
For a root-owned checkout:

```sh
CACHE_VOLUME='my-private-root-harness-home' PUID=0 PGID=0 \
  bash scripts/run-image.sh --interactive "$IMAGE" bash
```

The tools live under `/home/dev/.local/share/xorder/harnesses`; vendor account
state lives outside that installation tree under `HOME`. `HARNESS_AUTO_INSTALL=0`
disables startup installation for inspection or disconnected environments. It
does not erase installed tools or credentials.

## Inspect, update and reproduce a run

```sh
harnesses status
harnesses check-updates
harnesses install codex '<exact-version>'
harnesses update claude --version '<exact-version>'
harnesses update grok
harnesses rollback grok
harnesses rollback codex '<previous-installed-version>'
harnesses exec codex -- --version
```

`check-updates` observes upstream releases without changing installations.
`update NAME` deliberately selects the current upstream release; `--version`
selects an exact one. `install NAME VERSION` installs and selects an exact version.
`rollback` selects a previously installed version without downloading it.
`ensure` installs missing selections from the initial pins and preserves existing
selections, including versions selected by an explicit update or rollback.

Updates install alongside existing versions and atomically select the replacement
for new launches. Existing processes keep their executable. Old versions remain
available for rollback; updating does not delete account state. Built-in vendor
self-updaters are disabled for managed launches so version changes go through the
management command.

Retain `harnesses status` output with acceptance evidence. It records exact
version output, verified release provenance, executable identity and installed
hashes and permission bits. Changes to executable or directory permissions fail
integrity checks before managed execution. The image inventory
measures the image's Python/Node/tmux and manager; it does not claim that vendor
binaries are part of the image. Reproducing a run requires its image digest,
harness selections/receipts and project revision. A version pin makes selection
explicit; byte-for-byte upstream rebuild reproducibility is not claimed.

The manager accepts `--root PATH` and `--pins PATH` before the subcommand, or
`HARNESS_ROOT` and `HARNESS_PINS`. A custom pins file must use the same format as
the committed file and be mounted read-only into the container. Keep its
installation root separate from vendor credential directories.

## Official installation paths and verification

| Harness | Installation source | Reference |
| --- | --- | --- |
| Codex | Exact `@openai/codex` version through npm into a versioned prefix | [Official repository](https://github.com/openai/codex#installing-and-running-codex) |
| Claude Code | Exact native binary from the versioned official release; verify its GPG-signed manifest, then binary SHA-256 | [Official binary verification](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing) |
| Grok Build | Exact official npm platform artifact; verify registry ECDSA signature and tarball SHA-512, then extract the named native binary | [Official npm alternative](https://docs.x.ai/build/enterprise) |

Installations use isolated staging state before activation. No downloaded vendor
shell installer runs. Codex npm lifecycle hooks are disabled. Claude and Grok
release signatures are checked using the reviewed [keys in the image](../images/harness-live/trust/README.md)
before their downloaded code executes. Receipts retain signed metadata and payload
identities. Later versions signed by those keys remain eligible for explicit
updates; a new signing key requires a reviewed image update. Failed verification
preserves the prior selection. This image does not redistribute vendor CLI
binaries or contain vendor account state. Usage of the installed CLIs remains
subject to the corresponding vendor's terms.

## Network and trust

The [ordinary image network guidance](usage.md#network-access) applies to pulls,
proxy forwarding and `CA_CERTIFICATE`. The root entrypoint installs the supplied
CA before dropping privileges; Node receives `NODE_EXTRA_CA_CERTS`. Host Docker
pulls and host-side consumer checkout fetches need their own working trust path.
Never disable certificate validation.

| Harness | API and authentication hosts | Installation and additional hosts |
| --- | --- | --- |
| Codex | `auth.openai.com` for sign-in; `chatgpt.com` for subscription traffic; `api.openai.com` for API-key traffic | `registry.npmjs.org`; browser sign-in may use further hosts from OpenAI's published allowlist |
| Claude Code | `api.anthropic.com`, `claude.ai`, `claude.com`, `platform.claude.com` | `claude.ai`, `downloads.claude.ai`; plugins and connected tools have their own hosts |
| Grok Build | `auth.x.ai`, `cli-chat-proxy.grok.com`; `api.x.ai` for direct API-key use | `registry.npmjs.org` for signed installation artifacts; `x.ai` for version discovery; `code.grok.com` for remote session features |

Allow HTTPS on port 443 and the vendor's required WebSocket traffic. Enterprise
SSO, third-party providers, plugins and MCP servers can introduce additional
hosts. The table identifies direct vendor paths rather than a universal firewall
policy. Sources: [Codex login implementation](https://github.com/openai/codex/blob/main/codex-rs/login/src/server.rs),
[OpenAI network guidance](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps),
[OpenAI API reference](https://developers.openai.com/api/reference/overview),
[Claude network configuration](https://code.claude.com/docs/en/network-config),
and [Grok enterprise network requirements](https://docs.x.ai/build/enterprise).

## Readiness and operator acceptance

```sh
CA_CERTIFICATE='/absolute/path/to/proxy-ca.pem' \
  bash scripts/verify-image.sh 'harness-live/trixie' "$IMAGE"
```

The readiness fixture fetches the exact consumer commit in
[its source lock](../tests/fixtures/harness-live/consumer.json), starts with a
fresh private home volume and installs the pinned CLIs. It then disables container
network access and uses xordination's actual `doctor` implementation to check
versions, Codex JSON schema, Claude options and Grok ACP help. It also runs
xordination's real private-socket tmux self-check. Fresh-container reuse is checked
independently as UID 1000 and UID 0 with a dedicated HOME for each. It also forges
an executable and receipt as UID 1000, verifies root startup rejects that volume
before ownership changes or execution, and compares the unchanged state afterward.
Root ownership/permissions tests run inside the container so host UID namespace
limitations cannot skip them. No credentials are supplied, and no authenticated
session or model turn is started. The fixture removes its disposable home volumes.

This establishes local capability readiness, not live communication acceptance.
The operator runs xordination's `doctor --harness` and live launcher with their
private authenticated home; xordination owns that paid live-matrix evidence.
