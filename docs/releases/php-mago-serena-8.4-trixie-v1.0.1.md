# php-mago-serena/8.4-trixie v1.0.1

- Update Serena dependencies to filelock 4.2.1 and Werkzeug 3.1.9 to address the November 2026 Dependabot alerts, retaining the reviewed Serena application source.

Migration: Compatible dependency security update. Adopt the newly verified digest after project validation; existing exact releases retain their original contents.

Source: `09f1489c6c1ce4dc4ba32ff108c175a5f720f0f9` (`php-mago-serena/8.4-trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/php-mago-serena@sha256:1f2129133e9754a88e6553bb7f2a69f760b817f5d0667a0db2ef48549b089ded`.

Base/parent: `ghcr.io/xormania/php-browser@sha256:e0c5fed248b3a9a1f13e73bf747bd4f4559bc0ca37bd76a1a8f1422b2d7f342f`.

[Verification](https://github.com/xormania/xorder/actions/runs/42739860263).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,870.7 MiB (1,961,609,779 bytes) |
| Build, cache export and image load | 82.28s |
| Public-artifact behavior and inventory verification | 53.11s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42739860263); 2026-11-10T02:08:00.869529Z.

Plan about **4 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/php-mago-serena@sha256:7ec4859f1844a109f014730f2de306dbaf49073fbd92092c40ae0f586227316c`; 1,870.2 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:27:09.798648Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
