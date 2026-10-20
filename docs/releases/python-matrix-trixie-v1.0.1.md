# python-matrix/trixie v1.0.1

- Support optional build-time private CA trust for Python downloads through a BuildKit secret and temporary trust store.

Migration: Compatible build fix. Local builds may supply CA_CERTIFICATE without persisting that CA in image layers; existing runtime pins remain valid.

Source: `cd75ad6ef31d99b34fec2edf8d3c0695636d3541` (`python-matrix/trixie/v1.0.1`).

Artifact: `ghcr.io/xormania/python-matrix@sha256:dc0da00ee10740bb20406e4a0544ed4672e6ed0fc82169c34a246ccd20f93662`.

Base/parent: `ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589`.

[Verification](https://github.com/xormania/xorder/actions/runs/39398360633).

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 852.4 MiB (893,824,088 bytes) |
| Build, cache export and image load | 44.12s |
| Public-artifact behavior and inventory verification | 93.79s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39398360633); 2026-10-20T09:12:06.453467Z.

Plan about **2 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `restored`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.0, `ghcr.io/xormania/python-matrix@sha256:082cc0f69976211e661ca4c844b61eae78040be1d64e419cf227419a02a1854c`; 852.4 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/39375517777); 2026-10-20T05:39:00.526114Z.

The release record and GitHub Release asset retain the exact definition and per-platform inventory. The generated documentation commit is later than the build source commit.
