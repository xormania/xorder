# python-matrix/trixie v1.0.0

- Add preinstalled Python 3.10, 3.12 and 3.14 compatibility interpreters, SQLite behavior validation, and tmux.

Migration: New opt-in matrix line. Keep existing Python development pins unless the additional interpreters and tmux are needed; adopt its verified digest after publication.

Source: `46cf55f87d1913dafb88f99d8b74247b581de588` (`python-matrix/trixie/v1.0.0`).

Artifact: `ghcr.io/xormania/python-matrix@sha256:082cc0f69976211e661ca4c844b61eae78040be1d64e419cf227419a02a1854c`.

Base/parent: `ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589`.

[Verification](https://github.com/xormania/xorder/actions/runs/39375517777).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 852.4 MiB (893,823,329 bytes) |
| Build, cache export and image load | 43.85s |
| Public-artifact behavior and inventory verification | 112.93s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:39:00.526114Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
