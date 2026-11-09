# php-browser/8.5-trixie v1.2.7

- Use the decomposed PHP development parent while preserving this image’s existing runtime contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-browser/8.5-trixie/v1.2.7`).

Artifact: `ghcr.io/xormania/php-browser@sha256:7d563a60793d5022473f5ca1a54dfb7660a2cb63cdff56d754637c90f99e69d1`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:4324fbf6e2424ac7e575e813d5862543c7026611f334c3e1423b676062e1536f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,651.0 MiB (1,731,161,144 bytes) |
| Build, cache export and image load | 64.20s |
| Public-artifact behavior and inventory verification | 31.28s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:24:50.850042Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.4, `ghcr.io/xormania/php-browser@sha256:86e074a244a0d283d9ca2180703846a90e864ca06183054e88f72954c37da427`; 1,651.5 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:22:25.459883Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
