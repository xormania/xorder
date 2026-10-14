# rust-dev/1.99-trixie v1.1.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`rust-dev/1.99-trixie/v1.1.3`).

Artifact: `ghcr.io/xormania/rust-dev@sha256:a95105f8859f25ce4c50e8990dadfaff56afa3791056db9e4cf79438b7fb53d5`.

Base/parent: `docker.io/library/rust:1.99-slim-trixie@sha256:2752b332db73fdbb7dc576f06c82ed1f312005784ef913d7e04a28f5f55dc581`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,274.9 MiB (1,336,842,792 bytes) |
| Build, cache export and image load | 69.63s |
| Public-artifact behavior and inventory verification | 10.55s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:34.058025Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/rust-dev@sha256:a83e113d10653abffb8896e5d41ec898b9e9c768e9007816fea545d675935890`; 1,274.9 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/37884893194); 2026-10-09T04:41:49.591415Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
