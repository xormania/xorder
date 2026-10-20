# python-matrix/trixie

Python 3.10, 3.12 and 3.14 compatibility testing with tmux and the Python development toolchain.

**Not available:** no verified public release. The following capabilities describe the intended profile.

Capabilities: `native-build`, `pip`, `postgresql-client`, `python`, `python-matrix`, `sqlite-readonly-uri`, `sqlite-wal`, `tmux`, `uv`, `venv`.

Workspace `/workspace`, HOME `/home/dev`, default UID/GID 1000; configure `PUID` and `PGID`.

[Python matrix and tmux recipe](../python-matrix.md) · [Usage](../usage.md) · [Selection](../selection.md) · [Compatibility evidence](../compatibility.md)

## Limitations

- Compatibility with a particular project must include its dependencies, not only requires-python.
- Install project dependencies from uv.lock, requirements files, or the project manifest.
- Python 3.10 reached upstream end of life on 2026-10-01; it is included for compatibility testing, without upstream security support.
- The selected interpreter patches are fixed in images/python-matrix/versions.json and installed during the build; runtime downloads are disabled.
- Vendor harness CLIs and credentials are not part of this image.
