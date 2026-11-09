# php-dev/8.4-trixie v1.2.7

- Compose PHP CLI foundations, ABI-matched native extensions and retained portable tool payloads independently; preserve the existing development contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-dev/8.4-trixie/v1.2.7`).

Artifact: `ghcr.io/xormania/php-dev@sha256:437e6e38f41b88aa10bde916c0dd01a27465f86205cdb9de0a819cea9e9ae5c6`.

Base/parent: `docker.io/library/php:8.4-cli-trixie@sha256:d63e8b80cd4c6cfd01cfa7c910522e299cdc7ca1a2b6d6563db48df3c17e6c55`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 912.9 MiB (957,254,899 bytes) |
| Build, cache export and image load | 38.38s |
| Public-artifact behavior and inventory verification | 30.76s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:20:29.315634Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.4, `ghcr.io/xormania/php-dev@sha256:af3cf2730a901f9dbca5eb50e4d01b48bdf749a0ff1bb829d296bcb6656c24d6`; 913.4 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:41.333796Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
