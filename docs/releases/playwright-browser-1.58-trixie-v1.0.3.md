# playwright-browser/1.58-trixie v1.0.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`playwright-browser/1.58-trixie/v1.0.3`).

Artifact: `ghcr.io/xormania/playwright-browser@sha256:a9af6ee615412e5e941c1e164beddd157e9eca4c1701e5a08e09f84c016ca9c6`.

Base/parent: `docker.io/library/node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,213.9 MiB (2,321,430,922 bytes) |
| Build, cache export and image load | 153.03s |
| Public-artifact behavior and inventory verification | 174.23s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:07:49.484316Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/playwright-browser@sha256:48c7089b8ca4353f74ba66bda332f94e8ace76743ebd9a98560c83f9f82c3627`; 2,213.9 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38082448522); 2026-10-10T20:34:02.590398Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
