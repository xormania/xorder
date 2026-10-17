# php-browser/8.4-trixie v1.2.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-browser/8.4-trixie/v1.2.3`).

Artifact: `ghcr.io/xormania/php-browser@sha256:ad37c8138c4aacdbba8c64f0436669104e0e57dd206aa6f5099c512440f65a3e`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:6a2455e84058b89b9589461d1183dc282d851d5f376a141f140e59de7a6419e7`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,620.2 MiB (1,698,891,103 bytes) |
| Build, cache export and image load | 59.59s |
| Public-artifact behavior and inventory verification | 30.42s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:22:03.457341Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.2, `ghcr.io/xormania/php-browser@sha256:7d0b3157fd7c2a26a1e7646c59199fcae51f5471b415c7d0b778f0248f6034fe`; 1,618.8 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:33.878317Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
