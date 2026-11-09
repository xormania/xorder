# php-mago-serena/8.4-trixie v1.0.0

- Compose independently reusable Mago native, patched LSP, baseline and frozen Serena dependency artifacts.
- Select current Serena main and latest Symfony/AI Mate prereleases, preserve exact tuple provenance and provide reusable project initialization, compiled metadata preparation and Mago quality commands.

Migration: First release of this line. Adopt its verified digest only after the consumer identity, Mago/Serena and browser smoke checks pass; retain the previous image for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-mago-serena/8.4-trixie/v1.0.0`).

Artifact: `ghcr.io/xormania/php-mago-serena@sha256:7ec4859f1844a109f014730f2de306dbaf49073fbd92092c40ae0f586227316c`.

Base/parent: `ghcr.io/xormania/php-browser@sha256:e0c5fed248b3a9a1f13e73bf747bd4f4559bc0ca37bd76a1a8f1422b2d7f342f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,870.2 MiB (1,961,098,170 bytes) |
| Build, cache export and image load | 33.24s |
| Public-artifact behavior and inventory verification | 54.03s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:27:09.798648Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
