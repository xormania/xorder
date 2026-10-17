# uxor-dev/8.4-trixie v1.0.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`uxor-dev/8.4-trixie/v1.0.2`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:ad891975441273af65c3a9ea441aaebe310454c82abd186bc01994727ebdb8f8`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:828f22b953b34b080e3c233a1402b38dc6d7cb242f6bdb1cbaf5a579a111a3ce`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,201.6 MiB (1,259,926,222 bytes) |
| Build, cache export and image load | 28.81s |
| Public-artifact behavior and inventory verification | 261.46s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:29.248088Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.1, `ghcr.io/xormania/uxor-dev@sha256:5cd997c0bd669043db747e0cb9b4d61afb6fd5c2038bbbdb21c63e88ba304351`; 1,200.2 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:56:40.553104Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
