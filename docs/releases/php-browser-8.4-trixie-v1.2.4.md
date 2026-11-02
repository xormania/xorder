# php-browser/8.4-trixie v1.2.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c5e5c86e9c25bff2c2a29c198e958c92cba5a045` (`php-browser/8.4-trixie/v1.2.4`).

Artifact: `ghcr.io/xormania/php-browser@sha256:628021c4e31dbd226183aefb2186b363849475bcba8a5e176e684e7491054ee7`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:af3cf2730a901f9dbca5eb50e4d01b48bdf749a0ff1bb829d296bcb6656c24d6`.

[Verification](https://github.com/xormania/xorder/actions/runs/41260170505).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,621.7 MiB (1,700,463,285 bytes) |
| Build, cache export and image load | 64.36s |
| Public-artifact behavior and inventory verification | 32.55s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/41260170505); 2026-11-01T01:22:35.140913Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.3, `ghcr.io/xormania/php-browser@sha256:ad37c8138c4aacdbba8c64f0436669104e0e57dd206aa6f5099c512440f65a3e`; 1,620.2 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:22:03.457341Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
