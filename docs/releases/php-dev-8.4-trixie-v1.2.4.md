# php-dev/8.4-trixie v1.2.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-dev/8.4-trixie/v1.2.4`).

Artifact: `ghcr.io/xormania/php-dev@sha256:af3cf2730a901f9dbca5eb50e4d01b48bdf749a0ff1bb829d296bcb6656c24d6`.

Base/parent: `docker.io/library/php:8.4-cli-trixie@sha256:debadc2e36b857657846e2e952cbaf52702e55482dd3c2c43806f68d8c534a70`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 913.4 MiB (957,789,564 bytes) |
| Build, cache export and image load | 178.35s |
| Public-artifact behavior and inventory verification | 31.36s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:18:41.333796Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.3, `ghcr.io/xormania/php-dev@sha256:6a2455e84058b89b9589461d1183dc282d851d5f376a141f140e59de7a6419e7`; 913.7 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:17:23.763482Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
