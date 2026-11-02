# rust-dev/1.99-trixie

Rust 2024 native compilation, Clippy, formatting and wasm32-unknown-unknown builds.

Available revision: **1.1.5**. Pin:

```text
ghcr.io/xormania/rust-dev@sha256:846314820c3b22d0672564d3acff0f65d5213df6970e681f815c48cbed10abde
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:16:50.483515Z.

## Measured inventory — linux/amd64

Runtime: 1.99.1; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| clippy | clippy 0.1.99 (58cf8f9c35 2026-10-13) |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| jq | jq-1.7 |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| rg | ripgrep 14.1.1 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| rustfmt | rustfmt 1.10.0-stable (58cf8f9c35 2026-10-13) |
| rustup | rustup 1.29.2 (d8c92c676 2026-10-21) |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,274.8 MiB (1,336,679,722 bytes) |
| Build, cache export and image load | 54.34s |
| Public-artifact behavior and inventory verification | 12.48s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:16:00.969870Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/rust-dev@sha256:32642bd79d80e7ebdb36b4634dfa852db966aa8b71be4e52060f79603c61d557`; 1,274.9 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:21.257126Z.

[Release notes](../releases/rust-dev-1.99-trixie-v1.1.5.md).

Capabilities: `rust`, `cargo`, `rustfmt`, `clippy`, `native-build`, `postgresql-client`, `wasm32-unknown-unknown`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- WASM target compilation is tested; a WASM runtime and browser execution are not provided.
- No CUE executable or global third-party Cargo tools are included.
