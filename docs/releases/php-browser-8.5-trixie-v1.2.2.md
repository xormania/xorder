# php-browser/8.5-trixie v1.2.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-browser/8.5-trixie/v1.2.2`).

Artifact: `ghcr.io/xormania/php-browser@sha256:9f8e9d147578381199b3a916f9fc9d4792ce9b310aab499b08bee595cb9b7425`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:a5d0557cd8fef44638d13f7e71ff1c4b4482fc34b635e15c0d1fd37c0034b62e`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,648.6 MiB (1,728,723,524 bytes) |
| Build, cache export and image load | 55.10s |
| Public-artifact behavior and inventory verification | 24.09s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:51:13.012595Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.2.1, `ghcr.io/xormania/php-browser@sha256:3bd07aa66ea6af93ee3e690be1cb2e09352d3fa2e19f522f458e7020d664aded`; 1,645.3 MiB in the same image store. Change: **+0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38002658722); 2026-10-09T23:12:13.407279Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
