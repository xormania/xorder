# playwright-browser/1.58-trixie

Version-matched Chromium, Firefox and WebKit browser server without PHP or development build tools.

Available revision: **1.0.4**. Pin:

```text
ghcr.io/xormania/playwright-browser@sha256:b932c432efe06cb33cdd5e7cf859f73e68ef65dcee3e4a7baaaa60ae3be6534b
```

[Verification evidence](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:30:59.241065Z.

## Measured inventory — linux/amd64

Runtime: 1.58.2; OS: Debian GNU/Linux 13 (trixie).

| Tool | Version |
| --- | --- |
| node | v22.23.3 |
| playwright | Version 1.58.2 |

### Release measurements — linux/amd64

| Metric | Measured value |
| --- | ---: |
| Local image size | 2,213.9 MiB (2,321,431,758 bytes) |
| Build, cache export and image load | Not measured; artifact resumed |
| Public-artifact behavior and inventory verification | 165.35s |

Size method: `docker-image-inspect-size`; image store: `overlay2/classic`. [Measurement evidence](https://github.com/xormania/xorder/actions/runs/39103252258); 2026-10-18T06:32:06.572207Z.

Plan about **5 GiB free for a cold pull**, plus space for project dependencies and test output. This estimate is twice the measured unpacked image size, rounded up; shared layers may lower it, while the image store, temporary files and sandbox quotas can increase the requirement. Check free space on the Docker data filesystem; it may differ from the checkout filesystem.

Size baseline: v1.0.3, `ghcr.io/xormania/playwright-browser@sha256:a9af6ee615412e5e941c1e164beddd157e9eca4c1701e5a08e09f84c016ca9c6`; 2,213.9 MiB in the same image store. Change: **+0.0%**. [Baseline measurement](https://github.com/xormania/xorder/actions/runs/38518179175); 2026-10-14T06:07:49.484316Z.

[Release notes](../releases/playwright-browser-1.58-trixie-v1.0.4.md).

Capabilities: `playwright`, `chromium`, `firefox`, `webkit`, `browser-server`, `node`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Use the exact Playwright version pinned by the consuming project.
- Linux/amd64 only. All three engines are included; size savings are measured during validation and publication.
