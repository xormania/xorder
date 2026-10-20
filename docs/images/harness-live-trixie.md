# harness-live/trixie

Opt-in live harness environment with persistent installation, explicit updates and private operator authentication.

**Not available:** no verified public release. The following capabilities describe the intended profile.

Capabilities: `python`, `node`, `tmux`, `harness-installation`, `harness-updates`, `interactive-harnesses`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Harness installation, updates and interactive use](../harness-live.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Vendor harnesses are installed on initialization, not bundled in the image; first installation needs the documented vendor endpoints.
- The persistent HOME contains private authentication state and must not be shared or published.
- Reproduction requires the image digest, exact installed harness versions and consumer source revision; the image digest alone does not identify runtime-installed tools.
- Live model acceptance is operator-run and paid; image readiness never authenticates or calls a model.
- Use a dedicated persistent HOME for one operator and UID; root runs retain HOME=/home/dev and reject non-root-owned or group/other-writable state before ownership changes.
- Native release signatures are verified against image-pinned keys; adopting a rotated signing key requires an image update.
