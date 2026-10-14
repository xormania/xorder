# php-frankenphp/8.4-trixie v1.1.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-frankenphp/8.4-trixie/v1.1.3`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:0f4167f208cea0466fa39f4612706914f8bd4600f9ccdcba42968fe90a84c37a`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.4-trixie@sha256:7027c395e4a3b9f0624fd2091989eeaa1a5b7f7bd74677992df31a07a6655312`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 963.6 MiB (1,010,384,346 bytes) |
| Build, cache export and image load | 141.85s |
| Public-artifact behavior and inventory verification | 24.94s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:07.706964Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/php-frankenphp@sha256:db129945845787737366fe7e8c65510251f031c2ef36e362e08f3c4f398aba2e`; 963.5 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:22:08.272114Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
