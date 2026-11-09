# uxor-dev/8.4-trixie v1.0.5

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`uxor-dev/8.4-trixie/v1.0.5`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:7a3da062ccdee24173f8a6042264cd3231ea0d7cf258da575356886229476365`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:ed4c8554c5dbdf3057a2da8402d9c453d40368ac99862affadad12a11a14fcdd`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,201.6 MiB (1,259,939,832 bytes) |
| Build, cache export and image load | 38.33s |
| Public-artifact behavior and inventory verification | 225.95s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:32:06.919917Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.3, `ghcr.io/xormania/uxor-dev@sha256:dee7bad6852f2b22960535e3ddb3d64675719b42ea766e8151b008477c5d6143`; 1,200.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:29:44.326282Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
