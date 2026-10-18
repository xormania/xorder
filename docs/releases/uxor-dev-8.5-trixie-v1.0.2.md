# uxor-dev/8.5-trixie v1.0.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`uxor-dev/8.5-trixie/v1.0.2`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:050d3c3d693ed46cd8912c70fba8c7378c520deff81bb51f3ba96dd82d9154e2`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:c97b5c086dab63f3afba096bcaaae6f9f7134f6592d28d20fe979c75df2a5b80`.

[Verification](https://github.com/xormania/xorder/actions/runs/39103252258).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,231.3 MiB (1,291,077,421 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 348.61s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:26:22.728945Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.1, `ghcr.io/xormania/uxor-dev@sha256:76f4ed34ff037df2fbbeb6015ba5e8787011d3e3352f5ef4af631002c7616c1f`; 1,229.9 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:02:03.103125Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
