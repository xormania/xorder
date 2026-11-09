# php-frankenphp/8.4-trixie v1.1.7

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-frankenphp/8.4-trixie/v1.1.7`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:ed4c8554c5dbdf3057a2da8402d9c453d40368ac99862affadad12a11a14fcdd`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.4-trixie@sha256:08af88488ce218936d530b80f6f55dc2afe4d0d91f13f9e6ae350a9e7752128e`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 964.9 MiB (1,011,767,288 bytes) |
| Build, cache export and image load | 165.58s |
| Public-artifact behavior and inventory verification | 27.31s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:22:46.310277Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.5, `ghcr.io/xormania/php-frankenphp@sha256:20772c9f93bfd1c4a3d4d07419617335b155d075e964cadd2f84fdff0853fa9f`; 963.9 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:49.727216Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
