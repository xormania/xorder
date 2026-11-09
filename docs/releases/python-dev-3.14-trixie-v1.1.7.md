# python-dev/3.14-trixie v1.1.7

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`python-dev/3.14-trixie/v1.1.7`).

Artifact: `ghcr.io/xormania/python-dev@sha256:3fbc574e177b40689afe5e58271f73f002b9dc8e4e04fafe2fc335e5fdfa7e4e`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 582.8 MiB (611,106,558 bytes) |
| Build, cache export and image load | 43.06s |
| Public-artifact behavior and inventory verification | 21.97s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:20:29.742643Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.6, `ghcr.io/xormania/python-dev@sha256:0ecdf09af5352c4bb0762c254dcccd5d49f7dddfccb43a1cea82f080e4ff3518`; 582.5 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41517804597); 2026-11-02T20:20:00.829097Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
