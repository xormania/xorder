# php-toolkit/8.5-trixie v1.0.7

- Use the decomposed PHP development parent while preserving this image’s existing runtime contract.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `e3c02b8709e6d620ea27fb001714749f91d6ae94` (`php-toolkit/8.5-trixie/v1.0.7`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:db9a0ff566b63dabbf303a09528b856a5a627925719d3b201d74f4e5c4e5529d`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:4324fbf6e2424ac7e575e813d5862543c7026611f334c3e1423b676062e1536f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42715280945).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 967.1 MiB (1,014,086,037 bytes) |
| Build, cache export and image load | 17.67s |
| Public-artifact behavior and inventory verification | 39.64s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42715280945); 2026-11-09T23:39:06.234396Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.3, `ghcr.io/xormania/php-toolkit@sha256:3c25724c04a3b854e6a4d90098fbc08ff9ca15306d1e07373fce42ae3d8b185c`; 968.0 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:38.798809Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
