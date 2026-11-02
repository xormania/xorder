# harness-live/trixie

Opt-in live harness environment with persistent installation, explicit updates and private operator authentication.

Available revision: **1.0.1**. Pin:

```text
ghcr.io/xormania/harness-live@sha256:bb6f0b7ae9d5a0ad53d6525d76f93caa9b52f0f2b632f8933de8b94971c1b1da
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:12.896992Z.

## Measured inventory — linux/amd64

Runtime: 3.14.9; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| harnesses | harnesses 1.0.0 |
| jq | jq-1.7 |
| node | v22.23.4 |
| npm | 10.9.9 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| python | Python 3.14.9 |
| rg | ripgrep 14.1.1 |
| tmux | tmux 3.5a |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 676.6 MiB (709,491,482 bytes) |
| Build, cache export and image load | 53.03s |
| Public-artifact behavior and inventory verification | 71.75s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:17:42.048706Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/harness-live@sha256:247e7bd01adcfc0d6ee321906ada6ac182b72905a5deee3b20b952dd5af746d5`; 676.7 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:37:23.278588Z.

[Release notes](../releases/harness-live-trixie-v1.0.1.md).

Capabilities: `python`, `node`, `tmux`, `harness-installation`, `harness-updates`, `interactive-harnesses`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Harness installation, updates and interactive use](../harness-live.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Vendor harnesses are installed on initialization, not bundled in the image; first installation needs the documented vendor endpoints.
- The persistent HOME contains private authentication state and must not be shared or published.
- Reproduction requires the image digest, exact installed harness versions and consumer source revision; the image digest alone does not identify runtime-installed tools.
- Live model acceptance is operator-run and paid; image readiness never authenticates or calls a model.
- Use a dedicated persistent HOME for one operator and UID; root runs retain HOME=/home/dev and reject non-root-owned or group/other-writable state before ownership changes.
- Native release signatures are verified against image-pinned keys; adopting a rotated signing key requires an image update.
