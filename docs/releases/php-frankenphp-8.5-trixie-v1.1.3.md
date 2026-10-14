# php-frankenphp/8.5-trixie v1.1.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-frankenphp/8.5-trixie/v1.1.3`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:60c7f640d19ea35993ff31a74c48f1f163b352152ef4ab019bff12c63660606b`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.5-trixie@sha256:a052ae7cccd4a025eca17767e7acac57a4fc660a4f3dfc790be9b9cd5182d6e6`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 993.3 MiB (1,041,535,545 bytes) |
| Build, cache export and image load | 164.14s |
| Public-artifact behavior and inventory verification | 26.11s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:48:25.132661Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/php-frankenphp@sha256:ab6312943743a6bdb1480561eb47a7c4bfd38b825b3bc9d453be8105645f7e96`; 993.3 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:22:45.194640Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
