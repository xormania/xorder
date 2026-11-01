# uxor-dev/8.5-trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`uxor-dev/8.5-trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:28af54394cf26d6ff6fcb6f54ce85cfd4784d6cf867cd77b5187c5e1ddf9214b`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:d816d2a805f3d90ed10ffbdbe5e8494bc097407af54236a4ae52553a0ceefe94`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,230.3 MiB (1,290,018,417 bytes) |
| Build, cache export and image load | 28.93s |
| Public-artifact behavior and inventory verification | 379.06s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:32:39.031886Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/uxor-dev@sha256:050d3c3d693ed46cd8912c70fba8c7378c520deff81bb51f3ba96dd82d9154e2`; 1,231.3 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:26:22.728945Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
