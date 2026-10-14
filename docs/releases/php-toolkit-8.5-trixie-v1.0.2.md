# php-toolkit/8.5-trixie v1.0.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-toolkit/8.5-trixie/v1.0.2`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:37c5fbacc336a888a327a5aaf9bb68b33cc0662dbab992a373b8efa0b7ce7e79`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:a5d0557cd8fef44638d13f7e71ff1c4b4482fc34b635e15c0d1fd37c0034b62e`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 966.6 MiB (1,013,550,226 bytes) |
| Build, cache export and image load | 13.11s |
| Public-artifact behavior and inventory verification | 31.23s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:57:57.620489Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.1, `ghcr.io/xormania/php-toolkit@sha256:8170abf3fadcf200a342bedcc3e85c53305afbfdae3061dad1017c9119bb95e1`; 966.6 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:14:41.342203Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
