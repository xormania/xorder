# php-frankenphp/8.4-trixie v1.1.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-frankenphp/8.4-trixie/v1.1.4`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:828f22b953b34b080e3c233a1402b38dc6d7cb242f6bdb1cbaf5a579a111a3ce`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.4-trixie@sha256:b32a81ad4db40b528ada04087f47e22833f260266e73b3d88c62fd54e2a29aa6`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 965.0 MiB (1,011,828,342 bytes) |
| Build, cache export and image load | 169.42s |
| Public-artifact behavior and inventory verification | 30.46s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:16:59.132911Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.3, `ghcr.io/xormania/php-frankenphp@sha256:0f4167f208cea0466fa39f4612706914f8bd4600f9ccdcba42968fe90a84c37a`; 963.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:07.706964Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
