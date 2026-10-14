# php-dev/8.5-trixie v1.2.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-dev/8.5-trixie/v1.2.2`).

Artifact: `ghcr.io/xormania/php-dev@sha256:a5d0557cd8fef44638d13f7e71ff1c4b4482fc34b635e15c0d1fd37c0034b62e`.

Base/parent: `docker.io/library/php:8.5-cli-trixie@sha256:01a109229f4465bc9ef042d9198f09a4d9da7775a825dbd8572dcdbd8756c4d3`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 942.2 MiB (987,946,954 bytes) |
| Build, cache export and image load | 150.79s |
| Public-artifact behavior and inventory verification | 24.02s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:18.375450Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.1, `ghcr.io/xormania/php-dev@sha256:cd670b7c7b9624ce7dc7ee6b7b2a4d5b19ce36d6226f077a417667ae8505e000`; 942.2 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:10:02.526451Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
