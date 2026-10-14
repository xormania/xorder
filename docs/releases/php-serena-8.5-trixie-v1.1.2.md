# php-serena/8.5-trixie v1.1.2

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.
- Apply the reviewed dependency-only security patch and hashed uv closure: AnyIO 4.14.2 and PyJWT 2.14.0; retain the proven Serena source revision.

Migration: Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback.

Source: `c9493dc8cbc423ced71358fd3deb50ea9ce19386` (`php-serena/8.5-trixie/v1.1.2`).

Artifact: `ghcr.io/xormania/php-serena@sha256:9aa4981b585e76a812cc3070381e55488ffb86a850effa600779919c48b2d132`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:a5d0557cd8fef44638d13f7e71ff1c4b4482fc34b635e15c0d1fd37c0034b62e`.

[Verification](https://github.com/xormania/xorder/actions/runs/38518179175).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,243.7 MiB (1,304,119,166 bytes) |
| Build, cache export and image load | 35.07s |
| Public-artifact behavior and inventory verification | 84.77s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:55:34.549911Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
