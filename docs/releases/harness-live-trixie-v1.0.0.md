# harness-live/trixie v1.0.0

- Add an opt-in Python, Node and tmux environment with persistent harness installation, inspection, explicit updates and rollback.

Migration: New opt-in line. Use a dedicated private HOME volume, inspect exact runtime installation receipts, and run credential-free readiness before operator authentication.

Source: `46cf55f87d1913dafb88f99d8b74247b581de588` (`harness-live/trixie/v1.0.0`).

Artifact: `ghcr.io/xormania/harness-live@sha256:247e7bd01adcfc0d6ee321906ada6ac182b72905a5deee3b20b952dd5af746d5`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170`.

[Verification](https://github.com/xormania/xorder/actions/runs/39375517777).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 676.7 MiB (709,614,365 bytes) |
| Build, cache export and image load | 50.36s |
| Public-artifact behavior and inventory verification | 65.91s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:37:23.278588Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
