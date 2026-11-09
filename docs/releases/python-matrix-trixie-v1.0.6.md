# python-matrix/trixie v1.0.6

- Update only Python 3.10/3.14's installed and offline-bootstrap pip to hash-pinned 26.2.2, which vendors fixed certifi 2026.10.19. Preserve all three interpreter patch pins and offline virtual-environment support.

Migration: Compatible build decomposition. Update the exact digest only after normal image readiness checks; retain the prior release for rollback.

Source: `7c8bd71d96ad54a9b5115faae5d970f38fba9a25` (`python-matrix/trixie/v1.0.6`).

Artifact: `ghcr.io/xormania/python-matrix@sha256:31caf4654d8f1e059574887298c51a3df06acfc20216d01c69006fcca7b4a2a5`.

Base/parent: `ghcr.io/xormania/python-dev@sha256:a1bd1bfd06fb15348c541f6538bdb98425e9d1ab1116b4941e660c7c5ea0d8ed`.

[Verification](https://github.com/xormania/xorder/actions/runs/42715328359).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 867.0 MiB (909,078,546 bytes) |
| Build, cache export and image load | 60.52s |
| Public-artifact behavior and inventory verification | 97.70s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42715328359); 2026-11-09T23:50:40.762967Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.1, `ghcr.io/xormania/python-matrix@sha256:dc0da00ee10740bb20406e4a0544ed4672e6ed0fc82169c34a246ccd20f93662`; 852.4 MiB in the same image store. Change: **+1.7%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39398360633); 2026-10-20T09:12:06.453467Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
