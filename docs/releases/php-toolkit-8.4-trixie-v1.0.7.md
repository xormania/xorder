# php-toolkit/8.4-trixie v1.0.7

- Use the decomposed PHP development parent while preserving this image’s existing runtime contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-toolkit/8.4-trixie/v1.0.7`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:b7f45a34538f87d28be96c69d392fcd1f6b4b509a55048c50e492c0da8f0c9cd`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:437e6e38f41b88aa10bde916c0dd01a27465f86205cdb9de0a819cea9e9ae5c6`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 937.3 MiB (982,858,171 bytes) |
| Build, cache export and image load | 16.61s |
| Public-artifact behavior and inventory verification | 38.25s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:33:56.049898Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.4, `ghcr.io/xormania/php-toolkit@sha256:2fe87102264fc07b09ea79c142aa0180d044ef410c27966c5f089a7f97cd5b91`; 937.8 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:25:21.555468Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
