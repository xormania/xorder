# python-dev/3.14-trixie v1.1.8

- Reuse independently published runtime capability components without changing executable paths, permissions or readiness behavior.

Migration: Compatible build decomposition. Update the exact digest only after normal image readiness checks; retain the prior release for rollback.

Source: `ffbd6f81da52b0ac89fe1ea47cb52b6659859132` (`python-dev/3.14-trixie/v1.1.8`).

Artifact: `ghcr.io/xormania/python-dev@sha256:a1bd1bfd06fb15348c541f6538bdb98425e9d1ab1116b4941e660c7c5ea0d8ed`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597978081).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 584.1 MiB (612,448,514 bytes) |
| Build, cache export and image load | 28.67s |
| Public-artifact behavior and inventory verification | 23.73s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597978081); 2026-11-09T10:48:35.175251Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.6, `ghcr.io/xormania/python-dev@sha256:0ecdf09af5352c4bb0762c254dcccd5d49f7dddfccb43a1cea82f080e4ff3518`; 582.5 MiB in the same image store. Change: **+0.3%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:20:00.829097Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
