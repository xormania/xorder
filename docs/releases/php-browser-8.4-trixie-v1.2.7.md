# php-browser/8.4-trixie v1.2.7

- Use the decomposed PHP development parent while preserving this image’s existing runtime contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-browser/8.4-trixie/v1.2.7`).

Artifact: `ghcr.io/xormania/php-browser@sha256:e0c5fed248b3a9a1f13e73bf747bd4f4559bc0ca37bd76a1a8f1422b2d7f342f`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:437e6e38f41b88aa10bde916c0dd01a27465f86205cdb9de0a819cea9e9ae5c6`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,621.2 MiB (1,699,933,278 bytes) |
| Build, cache export and image load | 63.53s |
| Public-artifact behavior and inventory verification | 31.52s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:23:50.471310Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.4, `ghcr.io/xormania/php-browser@sha256:628021c4e31dbd226183aefb2186b363849475bcba8a5e176e684e7491054ee7`; 1,621.7 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:22:35.140913Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
