# php-toolkit/8.4-trixie v1.0.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-toolkit/8.4-trixie/v1.0.2`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:8fa2f8103ade24533a69ef7bc8fc326ccc5c108b037c2a470b9e100a5776400e`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:705f3be65d0867a19f08c6b666d129898bbb0f6ec3cfbcfd22c54a1eceb1e906`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 936.8 MiB (982,284,715 bytes) |
| Build, cache export and image load | 11.51s |
| Public-artifact behavior and inventory verification | 36.48s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:53:46.761154Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.1, `ghcr.io/xormania/php-toolkit@sha256:85f60474582b2d43a8a121e8c7ebc7c2d6e619245973db3dab2404f0f61b4a23`; 936.8 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:14:41.034687Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
