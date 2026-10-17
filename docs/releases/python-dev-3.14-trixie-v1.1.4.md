# python-dev/3.14-trixie v1.1.4

- Refresh locked upstream inputs and Debian packages; preserve the advertised development contract.
- Use system certificates for uv when LIBRARY_CA_FILE supplies a private CA, while preserving explicit uv and OpenSSL trust settings.

Migration: Compatible refresh and trust fix. Supply CA_CERTIFICATE through the public runners for intercepted HTTPS; explicit UV_SYSTEM_CERTS, UV_NATIVE_TLS, SSL_CERT_FILE and SSL_CERT_DIR settings retain precedence. Validate the new digest in the consuming project before upgrading; retain the previous exact release for rollback.

Source: `5257ce74a4e141f4ad7c9d64a351e88001cabf83` (`python-dev/3.14-trixie/v1.1.4`).

Artifact: `ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589`.

Base/parent: `docker.io/library/python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170`.

[Verification](https://github.com/xormania/xorder/actions/runs/39078086672).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 583.7 MiB (612,053,203 bytes) |
| Build, cache export and image load | 46.35s |
| Public-artifact behavior and inventory verification | 23.57s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39078086672); 2026-10-17T23:14:42.480412Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.1.3, `ghcr.io/xormania/python-dev@sha256:4116c87ab9a1ffc4a742d32ea92a1dcbd991867c5bb029c14d0e4c7523f1fbf1`; 585.5 MiB in the same image store. Change: **-0.3%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T05:46:09.319301Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
