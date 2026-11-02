# rust-dev/1.99-trixie v1.1.5

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`rust-dev/1.99-trixie/v1.1.5`).

Artifact: `ghcr.io/xormania/rust-dev@sha256:846314820c3b22d0672564d3acff0f65d5213df6970e681f815c48cbed10abde`.

Base/parent: `docker.io/library/rust:1.99-slim-trixie@sha256:aab42391a986424e22d6a3ec14f37bc6dd3dacff4d457ca7cccd781e02297cc6`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,274.8 MiB (1,336,679,722 bytes) |
| Build, cache export and image load | 54.34s |
| Public-artifact behavior and inventory verification | 12.48s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:16:00.969870Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/rust-dev@sha256:32642bd79d80e7ebdb36b4634dfa852db966aa8b71be4e52060f79603c61d557`; 1,274.9 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:21.257126Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
