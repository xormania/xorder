# harness-live/trixie v1.0.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `4345c87e032b0b71974c65c44771dea82b7a7ac1` (`harness-live/trixie/v1.0.2`).

Artifact: `ghcr.io/xormania/harness-live@sha256:e1575a8a24b61c6c79429e95ed7638e10c5910067f6805bd907281d229531d89`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8`.

[Verification](https://github.com/xormania/xorder/actions/runs/41517804597).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 676.7 MiB (709,600,368 bytes) |
| Build, cache export and image load | 49.57s |
| Public-artifact behavior and inventory verification | 72.53s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:21:20.775301Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/harness-live@sha256:247e7bd01adcfc0d6ee321906ada6ac182b72905a5deee3b20b952dd5af746d5`; 676.7 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:37:23.278588Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
