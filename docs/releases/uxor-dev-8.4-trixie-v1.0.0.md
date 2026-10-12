# uxor-dev/8.4-trixie v1.0.0

- Publish the canonical uxor development image and executable names as a new independently versioned family.

Migration: Select the new digest only after verified publication and catalog acceptance. Historical exact artifacts and their original public evidence are unchanged.

Source: `e81396fb53b51b110542b0500978880bcabf27b9` (`uxor-dev/8.4-trixie/v1.0.0`).

Artifact: `ghcr.io/xormania/uxor-dev@sha256:1dbff6efad5a12e14bab57bad99790ffe0d1eb6ffe12d5e406e13fcea18725f7`.

Base/parent: `ghcr.io/xormania/php-frankenphp@sha256:db129945845787737366fe7e8c65510251f031c2ef36e362e08f3c4f398aba2e`.

[Verification](https://github.com/xormania/xorder/actions/runs/38321328835).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,200.1 MiB (1,258,448,048 bytes) |
| Build, cache export and image load | 29.42s |
| Public-artifact behavior and inventory verification | 259.97s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:32:36.276204Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
