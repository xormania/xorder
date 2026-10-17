# php-browser/8.5-trixie v1.2.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-browser/8.5-trixie/v1.2.3`).

Artifact: `ghcr.io/xormania/php-browser@sha256:ee4d9e2c6f8d9f2122ac541967439c6dc5ad859107a092bffe87420853607192`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:43080f1e46b15f3b204f08f12abdb3f1a9aa16dd999450509d85d3aff4b97335`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,650.0 MiB (1,730,156,614 bytes) |
| Build, cache export and image load | 60.82s |
| Public-artifact behavior and inventory verification | 25.92s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:20:23.272909Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.2, `ghcr.io/xormania/php-browser@sha256:9f8e9d147578381199b3a916f9fc9d4792ce9b310aab499b08bee595cb9b7425`; 1,648.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:13.012595Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
