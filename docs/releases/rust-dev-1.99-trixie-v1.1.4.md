# rust-dev/1.99-trixie v1.1.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`rust-dev/1.99-trixie/v1.1.4`).

Artifact: `ghcr.io/xormania/rust-dev@sha256:32642bd79d80e7ebdb36b4634dfa852db966aa8b71be4e52060f79603c61d557`.

Base/parent: `docker.io/library/rust:1.99-slim-trixie@sha256:4df2ae8cfdfebdfc13a65da7f253b73d68983dc0339f2719bc17a279c913b13d`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,274.9 MiB (1,336,881,643 bytes) |
| Build, cache export and image load | 52.51s |
| Public-artifact behavior and inventory verification | 11.68s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:21.257126Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.3, `ghcr.io/xormania/rust-dev@sha256:a95105f8859f25ce4c50e8990dadfaff56afa3791056db9e4cf79438b7fb53d5`; 1,274.9 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:34.058025Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
