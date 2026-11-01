# php-dev/8.5-trixie v1.2.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-dev/8.5-trixie/v1.2.4`).

Artifact: `ghcr.io/xormania/php-dev@sha256:5f3e3b7337cae950064f82b0ef0a0b20100860f74688ed2e8916ddb65ae1254b`.

Base/parent: `docker.io/library/php:8.5-cli-trixie@sha256:635a4b998025ab269194639a5549c6fdcd9b4f88ec8cd761b092de8653d40663`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 943.2 MiB (989,017,430 bytes) |
| Build, cache export and image load | 191.12s |
| Public-artifact behavior and inventory verification | 31.15s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:49.429171Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.3, `ghcr.io/xormania/php-dev@sha256:43080f1e46b15f3b204f08f12abdb3f1a9aa16dd999450509d85d3aff4b97335`; 943.6 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:05.808962Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
