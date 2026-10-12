# php-frankenphp/8.4-trixie v1.1.2

- Publish a fresh verified revision after retiring obsolete project namespace records from current discovery.

Migration: Select the new digest only after verified publication and catalog acceptance. Historical exact artifacts and their original public evidence are unchanged.

Source: `e81396fb53b51b110542b0500978880bcabf27b9` (`php-frankenphp/8.4-trixie/v1.1.2`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:db129945845787737366fe7e8c65510251f031c2ef36e362e08f3c4f398aba2e`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.4-trixie@sha256:2fd4a848c05bf4902a3d9ff1a4991c2f4d4665df0567aee21be4eee120ded038`.

[Verification](https://github.com/xormania/xorder/actions/runs/38321328835).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 963.5 MiB (1,010,350,168 bytes) |
| Build, cache export and image load | 172.35s |
| Public-artifact behavior and inventory verification | 29.24s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:22:08.272114Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
