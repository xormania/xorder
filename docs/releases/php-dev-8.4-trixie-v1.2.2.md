# php-dev/8.4-trixie v1.2.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-dev/8.4-trixie/v1.2.2`).

Artifact: `ghcr.io/xormania/php-dev@sha256:705f3be65d0867a19f08c6b666d129898bbb0f6ec3cfbcfd22c54a1eceb1e906`.

Base/parent: `docker.io/library/php:8.4-cli-trixie@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 912.4 MiB (956,681,443 bytes) |
| Build, cache export and image load | 163.13s |
| Public-artifact behavior and inventory verification | 28.01s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:24.122378Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.1, `ghcr.io/xormania/php-dev@sha256:e00b85cb224a1f9ded14529d4c640c69bf5758237ec4720e67b9016282704a8f`; 912.4 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:10:30.194990Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
