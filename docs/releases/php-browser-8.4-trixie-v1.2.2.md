# php-browser/8.4-trixie v1.2.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-browser/8.4-trixie/v1.2.2`).

Artifact: `ghcr.io/xormania/php-browser@sha256:7d0b3157fd7c2a26a1e7646c59199fcae51f5471b415c7d0b778f0248f6034fe`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:705f3be65d0867a19f08c6b666d129898bbb0f6ec3cfbcfd22c54a1eceb1e906`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,618.8 MiB (1,697,458,013 bytes) |
| Build, cache export and image load | 59.29s |
| Public-artifact behavior and inventory verification | 28.73s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:33.878317Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.1, `ghcr.io/xormania/php-browser@sha256:730e67ff5d712550b7cce91387e9891e13092af05f70ae719f55f4c12f0a7f05`; 1,615.5 MiB in the same image store. Change: **+0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:13:05.903283Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
