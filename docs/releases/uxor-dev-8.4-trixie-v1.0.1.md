# uxor-dev/8.4-trixie v1.0.1

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`uxor-dev/8.4-trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:5cd997c0bd669043db747e0cb9b4d61afb6fd5c2038bbbdb21c63e88ba304351`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:0f4167f208cea0466fa39f4612706914f8bd4600f9ccdcba42968fe90a84c37a`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,200.2 MiB (1,258,482,226 bytes) |
| Build, cache export and image load | 36.49s |
| Public-artifact behavior and inventory verification | 199.18s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:56:40.553104Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/uxor-dev@sha256:1dbff6efad5a12e14bab57bad99790ffe0d1eb6ffe12d5e406e13fcea18725f7`; 1,200.1 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:32:36.276204Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
