# uxor-dev/8.4-trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`uxor-dev/8.4-trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:dee7bad6852f2b22960535e3ddb3d64675719b42ea766e8151b008477c5d6143`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:20772c9f93bfd1c4a3d4d07419617335b155d075e964cadd2f84fdff0853fa9f`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,200.6 MiB (1,258,904,991 bytes) |
| Build, cache export and image load | 28.76s |
| Public-artifact behavior and inventory verification | 278.78s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:29:44.326282Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/uxor-dev@sha256:ad891975441273af65c3a9ea441aaebe310454c82abd186bc01994727ebdb8f8`; 1,201.6 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:29.248088Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
