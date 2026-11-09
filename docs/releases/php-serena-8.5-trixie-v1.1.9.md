# php-serena/8.5-trixie v1.1.9

- Update only the pinned Serena Python dependency closure to certifi 2026.10.23 and Pillow 13.0.0 for the publication scan's fixable critical findings. Retain the same Serena/PHPactor backend and all other dependency versions.

Migration: Compatible packaging change. Adopt the newly verified digest after project validation; retain existing exact releases for rollback.

Source: `e3c02b8709e6d620ea27fb001714749f91d6ae94` (`php-serena/8.5-trixie/v1.1.9`).

Artifact: `ghcr.io/xormania/php-serena@sha256:c13753170b586f116ab4d948c5965fa8712f00c00e20e27fecba063cdfb75bc3`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:4324fbf6e2424ac7e575e813d5862543c7026611f334c3e1423b676062e1536f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42715280945).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,243.7 MiB (1,304,114,088 bytes) |
| Build, cache export and image load | 98.46s |
| Public-artifact behavior and inventory verification | 101.78s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42715280945); 2026-11-09T23:36:22.855776Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.3, `ghcr.io/xormania/php-serena@sha256:a21a6d18ae9be3d528fb01f19446769904ca4898fdf19b6bd4176769de809e04`; 1,245.1 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:25:11.078823Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
