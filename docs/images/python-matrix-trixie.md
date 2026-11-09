# python-matrix/trixie

Python 3.10, 3.12 and 3.14 compatibility testing with tmux and the Python development toolchain.

Available revision: **1.0.6**. Pin:

```text
ghcr.io/xormania/python-matrix@sha256:31caf4654d8f1e059574887298c51a3df06acfc20216d01c69006fcca7b4a2a5
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/42715328359); 2026-11-09T23:51:26.491303Z.

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
| python3.10 | Python 3.10.22 |
| python3.12 | Python 3.12.15 |
| python3.14 | Python 3.14.8 |
| rg | ripgrep 14.1.1 |
| tmux | tmux 3.5a |
| uv | uv 0.13.7 (x86_64-unknown-linux-musl) |

| Interpreter | Python | SQLite | Executable |
| --- | --- | --- | --- |
| 3.10 | 3.10.22 | 3.53.1 | `/opt/xorder/python-bin/python3.10` |
| 3.12 | 3.12.15 | 3.53.1 | `/opt/xorder/python-bin/python3.12` |
| 3.14 | 3.14.8 | 3.53.1 | `/opt/xorder/python-bin/python3.14` |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 867.0 MiB (909,078,546 bytes) |
| Build, cache export and image load | 60.52s |
| Public-artifact behavior and inventory verification | 97.70s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42715328359); 2026-11-09T23:50:40.762967Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.1, `ghcr.io/xormania/python-matrix@sha256:dc0da00ee10740bb20406e4a0544ed4672e6ed0fc82169c34a246ccd20f93662`; 852.4 MiB in the same image store. Change: **+1.7%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39398360633); 2026-10-20T09:12:06.453467Z.

[Release notes](../releases/python-matrix-trixie-v1.0.6.md).

Capabilities: `native-build`, `pip`, `postgresql-client`, `python`, `python-matrix`, `sqlite-readonly-uri`, `sqlite-wal`, `tmux`, `uv`, `venv`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Python matrix and tmux recipe](../python-matrix.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Compatibility with a particular project must include its dependencies, not only requires-python.
- Install project dependencies from uv.lock, requirements files, or the project manifest.
- Python 3.10 reached upstream end of life on 2026-10-01; it is included for compatibility testing, without upstream security support.
- The selected interpreter patches are fixed in images/python-matrix/versions.json and installed during the build; runtime downloads are disabled.
- Vendor harness CLIs and credentials are not part of this image.
