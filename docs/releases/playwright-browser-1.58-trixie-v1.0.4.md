# playwright-browser/1.58-trixie v1.0.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`playwright-browser/1.58-trixie/v1.0.4`).

Artifact: `ghcr.io/xormania/playwright-browser@sha256:b932c432efe06cb33cdd5e7cf859f73e68ef65dcee3e4a7baaaa60ae3be6534b`.

Base/parent: `docker.io/library/node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa`.

[Verification](https://github.com/xormania/xorder/actions/runs/39103252258).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,213.9 MiB (2,321,431,758 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 165.35s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:32:06.572207Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.3, `ghcr.io/xormania/playwright-browser@sha256:a9af6ee615412e5e941c1e164beddd157e9eca4c1701e5a08e09f84c016ca9c6`; 2,213.9 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:07:49.484316Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
