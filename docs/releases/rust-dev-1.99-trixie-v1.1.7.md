# rust-dev/1.99-trixie v1.1.7

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`rust-dev/1.99-trixie/v1.1.7`).

Artifact: `ghcr.io/xormania/rust-dev@sha256:759940d4877fa1c636c439b3b25d96f967d6ffeb105eb7c134bc42268fead2c2`.

Base/parent: `docker.io/library/rust:1.99-slim-trixie@sha256:7eab7ce19273ce785e0ca7578bdf7bc1fcbae621775a8197379a04c9f6e03cd5`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,275.0 MiB (1,336,926,883 bytes) |
| Build, cache export and image load | 54.93s |
| Public-artifact behavior and inventory verification | 12.38s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:20:34.645273Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.5, `ghcr.io/xormania/rust-dev@sha256:846314820c3b22d0672564d3acff0f65d5213df6970e681f815c48cbed10abde`; 1,274.8 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:16:00.969870Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
