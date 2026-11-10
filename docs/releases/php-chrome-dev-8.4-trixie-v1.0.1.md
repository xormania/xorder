# php-chrome-dev/8.4-trixie v1.0.1

- Inherit the Mago/Serena dependency security refresh with filelock 4.2.1 and Werkzeug 3.1.9.

Migration: Compatible dependency security update. Adopt the newly verified digest after project validation; existing exact releases retain their original contents.

Source: `09f1489c6c1ce4dc4ba32ff108c175a5f720f0f9` (`php-chrome-dev/8.4-trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/php-chrome-dev@sha256:91f6406a6b0912b24acccbc0bd7e8032a6129c20ac8c41d733e38e2e422ba2d2`.

Base/parent: `ghcr.io/xormania/php-mago-serena@sha256:1f2129133e9754a88e6553bb7f2a69f760b817f5d0667a0db2ef48549b089ded`.

[Verification](https://github.com/xormania/xorder/actions/runs/42739860263).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,421.9 MiB (2,539,588,838 bytes) |
| Build, cache export and image load | 94.07s |
| Public-artifact behavior and inventory verification | 56.86s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/42739860263); 2026-11-10T02:13:36.410875Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/php-chrome-dev@sha256:7850d077feda5b07f9eee244cd85d91ec3ae35197dd8a672756a9ce2f278ac93`; 2,421.5 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/42597027964); 2026-11-09T10:31:34.145331Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
