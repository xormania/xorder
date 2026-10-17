# php-dev/8.5-trixie v1.2.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-dev/8.5-trixie/v1.2.3`).

Artifact: `ghcr.io/xormania/php-dev@sha256:43080f1e46b15f3b204f08f12abdb3f1a9aa16dd999450509d85d3aff4b97335`.

Base/parent: `docker.io/library/php:8.5-cli-trixie@sha256:01a109229f4465bc9ef042d9198f09a4d9da7775a825dbd8572dcdbd8756c4d3`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 943.6 MiB (989,389,955 bytes) |
| Build, cache export and image load | 173.91s |
| Public-artifact behavior and inventory verification | 25.31s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:05.808962Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.2, `ghcr.io/xormania/php-dev@sha256:a5d0557cd8fef44638d13f7e71ff1c4b4482fc34b635e15c0d1fd37c0034b62e`; 942.2 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:18.375450Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
