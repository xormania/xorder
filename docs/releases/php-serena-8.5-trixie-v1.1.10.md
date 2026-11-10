# php-serena/8.5-trixie v1.1.10

- Update Serena dependencies to filelock 4.2.1 and Werkzeug 3.1.9 to address the November 2026 Dependabot alerts, retaining the reviewed Serena application source.

Migration: Compatible dependency security update. Adopt the newly verified digest after project validation; existing exact releases retain their original contents.

Source: `09f1489c6c1ce4dc4ba32ff108c175a5f720f0f9` (`php-serena/8.5-trixie/v1.1.10`).

Artifact: `ghcr.io/xormania/php-serena@sha256:7e8ef1de281501b4a5fabfecf405ce1a60cb24046e8f213bbea23d2fa6487b81`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:4324fbf6e2424ac7e575e813d5862543c7026611f334c3e1423b676062e1536f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42739860263).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,244.2 MiB (1,304,620,038 bytes) |
| Build, cache export and image load | 92.86s |
| Public-artifact behavior and inventory verification | 97.91s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42739860263); 2026-11-10T02:09:07.250957Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.9, `ghcr.io/xormania/php-serena@sha256:c13753170b586f116ab4d948c5965fa8712f00c00e20e27fecba063cdfb75bc3`; 1,243.7 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/42715280945); 2026-11-09T23:36:22.855776Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
