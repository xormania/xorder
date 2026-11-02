# harness-live/trixie v1.0.1

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`harness-live/trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/harness-live@sha256:bb6f0b7ae9d5a0ad53d6525d76f93caa9b52f0f2b632f8933de8b94971c1b1da`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 676.6 MiB (709,491,482 bytes) |
| Build, cache export and image load | 53.03s |
| Public-artifact behavior and inventory verification | 71.75s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:17:42.048706Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/harness-live@sha256:247e7bd01adcfc0d6ee321906ada6ac182b72905a5deee3b20b952dd5af746d5`; 676.7 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:37:23.278588Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
