# php-toolkit/8.4-trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-toolkit/8.4-trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/php-toolkit@sha256:7a658e512dd19d59f0cbf0b3ec158294f98a98dac101701a5432c172d86473af`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:6a2455e84058b89b9589461d1183dc282d851d5f376a141f140e59de7a6419e7`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 938.2 MiB (983,727,716 bytes) |
| Build, cache export and image load | 12.00s |
| Public-artifact behavior and inventory verification | 38.79s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:24:49.860081Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/php-toolkit@sha256:8fa2f8103ade24533a69ef7bc8fc326ccc5c108b037c2a470b9e100a5776400e`; 936.8 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:53:46.761154Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
