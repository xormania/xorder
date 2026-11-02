# python-dev/3.14-trixie v1.1.6

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `4345c87e032b0b71974c65c44771dea82b7a7ac1` (`python-dev/3.14-trixie/v1.1.6`).

Artifact: `ghcr.io/xormania/python-dev@sha256:0ecdf09af5352c4bb0762c254dcccd5d49f7dddfccb43a1cea82f080e4ff3518`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8`.

[Verification](https://github.com/xormania/xorder/actions/runs/41517804597).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 582.5 MiB (610,820,826 bytes) |
| Build, cache export and image load | 43.60s |
| Public-artifact behavior and inventory verification | 31.08s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:20:00.829097Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589`; 583.7 MiB in the same image store. Change: **-0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:42.480412Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
