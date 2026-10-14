# python-dev/3.14-trixie

Python development with uv, pip, venv, native compilation and PostgreSQL clients.

Available revision: **1.1.3**. Pin:

```text
ghcr.io/xormania/python-dev@sha256:4116c87ab9a1ffc4a742d32ea92a1dcbd991867c5bb029c14d0e4c7523f1fbf1
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:43.892330Z.

## Measured inventory — linux/amd64

Runtime: 3.14.8; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| jq | jq-1.7 |
| pip | pip 26.2.1 from /usr/local/lib/python3.14/site-packages/pip (python 3.14) |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| python | Python 3.14.8 |
| rg | ripgrep 14.1.1 |
| uv | uv 0.13.0 (x86_64-unknown-linux-musl) |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 585.5 MiB (613,932,615 bytes) |
| Build, cache export and image load | 40.82s |
| Public-artifact behavior and inventory verification | 22.12s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:09.319301Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/python-dev@sha256:f9821a6dba4ee2e50715c37421ff46437dc9104d4652ead1bc74eec561bcafba`; 593.9 MiB in the same image store. Change: **-1.4%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/37884893194); 2026-10-09T04:41:45.296878Z.

[Release notes](../releases/python-dev-3.14-trixie-v1.1.3.md).

Capabilities: `python`, `uv`, `pip`, `venv`, `native-build`, `postgresql-client`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Install project dependencies from uv.lock, requirements files, or the project manifest.
- Compatibility with a particular project must include its dependencies, not only requires-python.
