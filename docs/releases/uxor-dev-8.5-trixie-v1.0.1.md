# uxor-dev/8.5-trixie v1.0.1

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`uxor-dev/8.5-trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:76f4ed34ff037df2fbbeb6015ba5e8787011d3e3352f5ef4af631002c7616c1f`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:60c7f640d19ea35993ff31a74c48f1f163b352152ef4ab019bff12c63660606b`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,229.9 MiB (1,289,633,425 bytes) |
| Build, cache export and image load | 30.58s |
| Public-artifact behavior and inventory verification | 341.84s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:02:03.103125Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/uxor-dev@sha256:c271b1f78c7bccaf5a0c3e962c2ac09707d3088705fc8ff8f1bae83c70c0cdfd`; 1,229.9 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:41:32.011996Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
