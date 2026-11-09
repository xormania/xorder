# harness-live/trixie v1.0.4

- Reuse independently published runtime capability components without changing executable paths, permissions or readiness behavior.

Migration: Compatible build decomposition. Update the exact digest only after normal image readiness checks; retain the prior release for rollback.

Source: `ffbd6f81da52b0ac89fe1ea47cb52b6659859132` (`harness-live/trixie/v1.0.4`).

Artifact: `ghcr.io/xormania/harness-live@sha256:7cd2dba80df2c9fe39f6be511bf06ddfadac666d8fc940b40ee2a2d3f1b70811`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597978081).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 678.7 MiB (711,617,400 bytes) |
| Build, cache export and image load | 53.20s |
| Public-artifact behavior and inventory verification | 69.58s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597978081); 2026-11-09T10:50:36.056330Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/harness-live@sha256:e1575a8a24b61c6c79429e95ed7638e10c5910067f6805bd907281d229531d89`; 676.7 MiB in the same image store. Change: **+0.3%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:21:20.775301Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
