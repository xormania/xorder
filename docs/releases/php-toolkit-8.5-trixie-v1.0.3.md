# php-toolkit/8.5-trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-toolkit/8.5-trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:3c25724c04a3b854e6a4d90098fbc08ff9ca15306d1e07373fce42ae3d8b185c`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:43080f1e46b15f3b204f08f12abdb3f1a9aa16dd999450509d85d3aff4b97335`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 968.0 MiB (1,014,993,227 bytes) |
| Build, cache export and image load | 13.12s |
| Public-artifact behavior and inventory verification | 32.11s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:27:38.798809Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/php-toolkit@sha256:37c5fbacc336a888a327a5aaf9bb68b33cc0662dbab992a373b8efa0b7ce7e79`; 966.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:57:57.620489Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
