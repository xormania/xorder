# playwright-browser/1.58-trixie

Version-matched Chromium, Firefox and WebKit browser server without PHP or development build tools.

Available revision: **1.0.3**. Pin:

```text
ghcr.io/xormania/playwright-browser@sha256:a9af6ee615412e5e941c1e164beddd157e9eca4c1701e5a08e09f84c016ca9c6
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:06:43.723983Z.

## Measured inventory — linux/amd64

Runtime: 1.58.2; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| node | v22.23.3 |
| playwright | Version 1.58.2 |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,213.9 MiB (2,321,430,922 bytes) |
| Build, cache export and image load | 153.03s |
| Public-artifact behavior and inventory verification | 174.23s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:07:49.484316Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

External build cache at start: `empty`. This does not assert that every layer was a cache hit.

Size baseline: v1.0.2, `ghcr.io/xormania/playwright-browser@sha256:48c7089b8ca4353f74ba66bda332f94e8ace76743ebd9a98560c83f9f82c3627`; 2,213.9 MiB in the same image store. Change: **-0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38082448522); 2026-10-10T20:34:02.590398Z.

[Release notes](../releases/playwright-browser-1.58-trixie-v1.0.3.md).

Capabilities: `playwright`, `chromium`, `firefox`, `webkit`, `browser-server`, `node`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Use the exact Playwright version pinned by the consuming project.
- Linux/amd64 only. All three engines are included; size savings are measured during validation and publication.
