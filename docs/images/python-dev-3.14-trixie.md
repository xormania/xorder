# python-dev/3.14-trixie

Python development with uv, pip, venv, native compilation and PostgreSQL clients.

Available revision: **1.1.5**. Pin:

```text
ghcr.io/xormania/python-dev@sha256:d6d61b3de04f1587a4a017b4fd1a6c2b80a827165115ec30ce2612c772c16120
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:16:28.759454Z.

## Measured inventory — linux/amd64

Runtime: 3.14.9; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| bash | GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu) |
| curl | curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10 |
| gh | gh version 2.46.0 (2025-01-13 Debian 2.46.0-3) |
| git | git version 2.47.3 |
| jq | jq-1.7 |
| pip | pip 26.2.2 from /usr/local/lib/python3.14/site-packages/pip (python 3.14) |
| psql | psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1) |
| python | Python 3.14.9 |
| rg | ripgrep 14.1.1 |
| uv | uv 0.13.5 (x86_64-unknown-linux-musl) |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 582.5 MiB (610,800,820 bytes) |
| Build, cache export and image load | 39.17s |
| Public-artifact behavior and inventory verification | 20.45s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:15:51.374502Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589`; 583.7 MiB in the same image store. Change: **-0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:42.480412Z.

[Release notes](../releases/python-dev-3.14-trixie-v1.1.5.md).

Capabilities: `python`, `uv`, `pip`, `venv`, `native-build`, `postgresql-client`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Install project dependencies from uv.lock, requirements files, or the project manifest.
- Compatibility with a particular project must include its dependencies, not only requires-python.
