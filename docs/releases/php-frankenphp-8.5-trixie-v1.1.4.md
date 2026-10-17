# php-frankenphp/8.5-trixie v1.1.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-frankenphp/8.5-trixie/v1.1.4`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:c97b5c086dab63f3afba096bcaaae6f9f7134f6592d28d20fe979c75df2a5b80`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.5-trixie@sha256:4a8eebee6b3bed92d01ffa6ec5b1bc2cb9c2ab7eeb546027a3f7e6a52937ebbb`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 994.7 MiB (1,042,979,541 bytes) |
| Build, cache export and image load | 199.37s |
| Public-artifact behavior and inventory verification | 30.75s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:39.186124Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.3, `ghcr.io/xormania/php-frankenphp@sha256:60c7f640d19ea35993ff31a74c48f1f163b352152ef4ab019bff12c63660606b`; 993.3 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:25.132661Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
