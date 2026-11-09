# php-dev/8.5-trixie v1.2.7

- Compose PHP CLI foundations, ABI-matched native extensions and retained portable tool payloads independently; preserve the existing development contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-dev/8.5-trixie/v1.2.7`).

Artifact: `ghcr.io/xormania/php-dev@sha256:4324fbf6e2424ac7e575e813d5862543c7026611f334c3e1423b676062e1536f`.

Base/parent: `docker.io/library/php:8.5-cli-trixie@sha256:50956f094e90a716d43bea28087d447555ad80510e386ab8c9c10d8c70d781a9`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 942.7 MiB (988,482,765 bytes) |
| Build, cache export and image load | 63.04s |
| Public-artifact behavior and inventory verification | 30.29s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:21:05.689550Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.4, `ghcr.io/xormania/php-dev@sha256:5f3e3b7337cae950064f82b0ef0a0b20100860f74688ed2e8916ddb65ae1254b`; 943.2 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:49.429171Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
