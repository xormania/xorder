# python-dev/3.14-trixie

Python development with uv, pip, venv, native compilation and PostgreSQL clients.

Available revision: **1.1.7**. Pin:

```text
ghcr.io/xormania/python-dev@sha256:3fbc574e177b40689afe5e58271f73f002b9dc8e4e04fafe2fc335e5fdfa7e4e
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:21:00.876888Z.

## Measured inventory — linux/amd64

Runtime: 3.14.10; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| jq | jq-1.7 |
| pip | pip 26.2.2 from /usr/local/lib/python3.14/site-packages/pip (python 3.14) |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| python | Python 3.14.10 |
| rg | ripgrep 14.1.1 |
| uv | uv 0.13.7 (x86_64-unknown-linux-musl) |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 582.8 MiB (611,106,558 bytes) |
| Build, cache export and image load | 43.06s |
| Public-artifact behavior and inventory verification | 21.97s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:20:29.742643Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.6, `ghcr.io/xormania/python-dev@sha256:0ecdf09af5352c4bb0762c254dcccd5d49f7dddfccb43a1cea82f080e4ff3518`; 582.5 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:20:00.829097Z.

[Release notes](../releases/python-dev-3.14-trixie-v1.1.7.md).

Capabilities: `python`, `uv`, `pip`, `venv`, `native-build`, `postgresql-client`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Install project dependencies from uv.lock, requirements files, or the project manifest.
- Compatibility with a particular project must include its dependencies, not only requires-python.
