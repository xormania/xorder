# php-browser/8.5-trixie v1.2.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-browser/8.5-trixie/v1.2.4`).

Artifact: `ghcr.io/xormania/php-browser@sha256:86e074a244a0d283d9ca2180703846a90e864ca06183054e88f72954c37da427`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:5f3e3b7337cae950064f82b0ef0a0b20100860f74688ed2e8916ddb65ae1254b`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,651.5 MiB (1,731,691,151 bytes) |
| Build, cache export and image load | 61.47s |
| Public-artifact behavior and inventory verification | 32.30s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:22:25.459883Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.3, `ghcr.io/xormania/php-browser@sha256:ee4d9e2c6f8d9f2122ac541967439c6dc5ad859107a092bffe87420853607192`; 1,650.0 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:20:23.272909Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
