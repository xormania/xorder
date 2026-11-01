# php-toolkit/8.4-trixie v1.0.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-toolkit/8.4-trixie/v1.0.4`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:2fe87102264fc07b09ea79c142aa0180d044ef410c27966c5f089a7f97cd5b91`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:af3cf2730a901f9dbca5eb50e4d01b48bdf749a0ff1bb829d296bcb6656c24d6`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 937.8 MiB (983,392,836 bytes) |
| Build, cache export and image load | 11.98s |
| Public-artifact behavior and inventory verification | 39.75s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:25:21.555468Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.3, `ghcr.io/xormania/php-toolkit@sha256:7a658e512dd19d59f0cbf0b3ec158294f98a98dac101701a5432c172d86473af`; 938.2 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:24:49.860081Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
