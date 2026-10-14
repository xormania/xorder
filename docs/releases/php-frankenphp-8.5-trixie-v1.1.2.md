# php-frankenphp/8.5-trixie v1.1.2

- Publish a fresh verified revision after retiring obsolete project namespace records from current discovery.

Migration: Select the new digest only after verified publication and catalog acceptance. Historical exact artifacts and their original public evidence are unchanged.

Source: `e81396fb53b51b110542b0500978880bcabf27b9` (`php-frankenphp/8.5-trixie/v1.1.2`).

Artifact: `ghcr.io/xormania/php-frankenphp@sha256:ab6312943743a6bdb1480561eb47a7c4bfd38b825b3bc9d453be8105645f7e96`.

Base/parent: `docker.io/dunglas/frankenphp:1-php8.5-trixie@sha256:06e3a490ff76db5bfd1c3c410677fc22bdbcb2c735c240cfa4111727d7641f38`.

[Verification](https://github.com/xormania/xorder/actions/runs/38321328835).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 993.3 MiB (1,041,501,367 bytes) |
| Build, cache export and image load | 198.29s |
| Public-artifact behavior and inventory verification | 29.53s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38321328835); 2026-10-12T23:22:45.194640Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
