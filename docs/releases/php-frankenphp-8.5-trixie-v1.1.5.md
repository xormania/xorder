# php-frankenphp/8.5-trixie v1.1.5

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-frankenphp/8.5-trixie/v1.1.5`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:d816d2a805f3d90ed10ffbdbe5e8494bc097407af54236a4ae52553a0ceefe94`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.5-trixie@sha256:73053ec45f0ad33c8e6f71f60ec3a11133899eecc73d7aa577b6d3a1ff5649c2`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 993.6 MiB (1,041,845,873 bytes) |
| Build, cache export and image load | 160.43s |
| Public-artifact behavior and inventory verification | 26.14s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:19.453551Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.4, `ghcr.io/xormania/php-frankenphp@sha256:c97b5c086dab63f3afba096bcaaae6f9f7134f6592d28d20fe979c75df2a5b80`; 994.7 MiB in the same image store. Change: **-0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:39.186124Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
