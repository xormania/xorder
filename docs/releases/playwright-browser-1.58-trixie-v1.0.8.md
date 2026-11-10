# playwright-browser/1.58-trixie v1.0.8

- Retain the locked Playwright npm closure and all three engine payloads as one independently reusable component.
- Assemble browser runtime packages and RGB font configuration separately; preserve all-engine launch and screenshot parity verification.

Migration: Compatible browser packaging change. Adopt its verified digest after all-engine and committed screenshot parity checks; existing exact releases remain available.

Source: `ba41ead18a052911f1a0d7a4ee26f9c2b7b865d1` (`playwright-browser/1.58-trixie/v1.0.8`).

Artifact: `ghcr.io/xormania/playwright-browser@sha256:ad168a781c7663f1f5aaa694289a3ba86660809b136a850897bed3d55c77edb6`.

Base/parent: `docker.io/library/node:22-trixie-slim@sha256:be1e2a3dc2c4fd68cdfadad2a696a280e0d2749098bee509230174d72fb768c6`.

[Verification](https://github.com/xormania/xorder/actions/runs/42715328359).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,209.8 MiB (2,317,159,803 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 211.57s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42715328359); 2026-11-09T23:57:20.242490Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.4, `ghcr.io/xormania/playwright-browser@sha256:b932c432efe06cb33cdd5e7cf859f73e68ef65dcee3e4a7baaaa60ae3be6534b`; 2,213.9 MiB in the same image store. Change: **-0.2%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:32:06.572207Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
