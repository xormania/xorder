# php-chrome-dev/8.4-trixie v1.0.0

- Add the separately pinned Node 22, Chrome for Testing 157.0.8103.38 and Chrome DevTools MCP 1.12.0 toolchain.
- Preserve inherited Mago/Serena identity and record Chrome and MCP versions and installed browser hash.
- Compose independently retained Node, Chrome for Testing and MCP payloads without downloading them during final image assembly.

Migration: First release of this line. Adopt its verified digest only after the consumer identity, Mago/Serena and browser smoke checks pass; retain the previous image for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-chrome-dev/8.4-trixie/v1.0.0`).

Artifact: `ghcr.io/xormania/php-chrome-dev@sha256:7850d077feda5b07f9eee244cd85d91ec3ae35197dd8a672756a9ce2f278ac93`.

Base/parent: `ghcr.io/xormania/php-mago-serena@sha256:7ec4859f1844a109f014730f2de306dbaf49073fbd92092c40ae0f586227316c`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,421.5 MiB (2,539,076,745 bytes) |
| Build, cache export and image load | 75.25s |
| Public-artifact behavior and inventory verification | 55.98s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:31:34.145331Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
