# uxor-dev/8.5-trixie v1.0.5

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`uxor-dev/8.5-trixie/v1.0.5`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:64f1b5331de0cd52f958f4f233c4eaf7a0626f68e80fc48273d884de224fdc92`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:840f9f96aebc86bcc0bbe994e668d68e204036212ef5f223f0736f3ba52433af`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597978081).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,231.2 MiB (1,291,049,162 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 415.17s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597978081); 2026-11-09T11:02:48.497262Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.3, `ghcr.io/xormania/uxor-dev@sha256:28af54394cf26d6ff6fcb6f54ce85cfd4784d6cf867cd77b5187c5e1ddf9214b`; 1,230.3 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:32:39.031886Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
