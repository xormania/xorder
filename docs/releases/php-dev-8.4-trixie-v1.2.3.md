# php-dev/8.4-trixie v1.2.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-dev/8.4-trixie/v1.2.3`).

Artifact: `ghcr.io/xormania/php-dev@sha256:6a2455e84058b89b9589461d1183dc282d851d5f376a141f140e59de7a6419e7`.

Base/parent: `docker.io/library/php:8.4-cli-trixie@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 913.7 MiB (958,124,444 bytes) |
| Build, cache export and image load | 180.94s |
| Public-artifact behavior and inventory verification | 30.07s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:23.763482Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.2, `ghcr.io/xormania/php-dev@sha256:705f3be65d0867a19f08c6b666d129898bbb0f6ec3cfbcfd22c54a1eceb1e906`; 912.4 MiB in the same image store. Change: **+0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:24.122378Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
