# harness-live/trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`harness-live/trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/harness-live@sha256:0a3302298d6667cd0434035cc1654975628f023be51087361ff30bf6e006d873`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 676.7 MiB (709,600,428 bytes) |
| Build, cache export and image load | 57.59s |
| Public-artifact behavior and inventory verification | 74.77s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:22:30.754825Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/harness-live@sha256:e1575a8a24b61c6c79429e95ed7638e10c5910067f6805bd907281d229531d89`; 676.7 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:21:20.775301Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
