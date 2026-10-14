# python-dev/3.14-trixie v1.1.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`python-dev/3.14-trixie/v1.1.3`).

Artifact: `ghcr.io/xormania/python-dev@sha256:4116c87ab9a1ffc4a742d32ea92a1dcbd991867c5bb029c14d0e4c7523f1fbf1`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 585.5 MiB (613,932,615 bytes) |
| Build, cache export and image load | 40.82s |
| Public-artifact behavior and inventory verification | 22.12s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:09.319301Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/python-dev@sha256:f9821a6dba4ee2e50715c37421ff46437dc9104d4652ead1bc74eec561bcafba`; 593.9 MiB in the same image store. Change: **-1.4%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/37884893194); 2026-10-09T04:41:45.296878Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
