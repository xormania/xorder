# php-frankenphp/8.5-trixie v1.1.7

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `6412757e07ecda600e9e5e35e3a11429daf75fcd` (`php-frankenphp/8.5-trixie/v1.1.7`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:840f9f96aebc86bcc0bbe994e668d68e204036212ef5f223f0736f3ba52433af`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.5-trixie@sha256:7e73a27eb7712a5b4073b92f8f0dec91e9400138604b76cc791589faaa6a639c`.

[Verification](https://github.com/xormania/xorder/actions/runs/42597027964).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 994.6 MiB (1,042,876,618 bytes) |
| Build, cache export and image load | 195.97s |
| Public-artifact behavior and inventory verification | 28.43s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:23:41.204354Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.5, `ghcr.io/xormania/php-frankenphp@sha256:d816d2a805f3d90ed10ffbdbe5e8494bc097407af54236a4ae52553a0ceefe94`; 993.6 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:19.453551Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
