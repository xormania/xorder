# php-frankenphp/8.4-trixie v1.1.5

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-frankenphp/8.4-trixie/v1.1.5`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:20772c9f93bfd1c4a3d4d07419617335b155d075e964cadd2f84fdff0853fa9f`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.4-trixie@sha256:b5e21479c9e17b9acaba581361ebdcd315705120ab2ad72b7024e67174084723`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 963.9 MiB (1,010,732,447 bytes) |
| Build, cache export and image load | 179.09s |
| Public-artifact behavior and inventory verification | 31.61s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:49.727216Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/php-frankenphp@sha256:828f22b953b34b080e3c233a1402b38dc6d7cb242f6bdb1cbaf5a579a111a3ce`; 965.0 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:16:59.132911Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
