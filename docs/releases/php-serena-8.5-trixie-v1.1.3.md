# php-serena/8.5-trixie v1.1.3

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.
- Use system certificates for uv when LIBRARY_CA_FILE supplies a private CA, while preserving explicit uv and OpenSSL trust settings.
- Retain the proven Serena source revision and its reviewed dependency-only security patch.

Migration: Compatible refresh and trust fix. Supply CA_CERTIFICATE through the public runners for intercepted HTTPS; explicit UV_SYSTEM_CERTS, UV_NATIVE_TLS, SSL_CERT_FILE and SSL_CERT_DIR settings retain precedence. Validate the new digest in the consuming project before upgrading; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`php-serena/8.5-trixie/v1.1.3`).

Artifact: `ghcr.io/xormania/php-serena@sha256:a21a6d18ae9be3d528fb01f19446769904ca4898fdf19b6bd4176769de809e04`.

Base/parent: `ghcr.io/xormania/php-dev@sha256:43080f1e46b15f3b204f08f12abdb3f1a9aa16dd999450509d85d3aff4b97335`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 1,245.1 MiB (1,305,562,766 bytes) |
| Build, cache export and image load | 39.42s |
| Public-artifact behavior and inventory verification | 91.34s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:25:11.078823Z.

Plan about **3 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.2, `ghcr.io/xormania/php-serena@sha256:9aa4981b585e76a812cc3070381e55488ffb86a850effa600779919c48b2d132`; 1,243.7 MiB in the same image store. Change: **+0.1%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:55:34.549911Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
