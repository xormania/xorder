"""Forge lower-UID harness state and prove a later root startup leaves it alone."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("tamper", "snapshot"))
    args = parser.parse_args()
    assert os.getuid() == 1000, "Cross-UID fixture must run as UID 1000"
    home = Path("/home/dev")
    marker = home / "root-workload-ran"
    assert not marker.exists(), "A rejected root startup must not execute forged workload bytes"
    store = Path(os.environ.get("HARNESS_ROOT", str(home / ".local/share/xorder/harnesses")))
    selected_path = store / "selected.json"
    selected = json.loads(selected_path.read_text())
    version = selected["harnesses"]["codex"]["version"]
    assert "/" not in version and version not in (".", ".."), "Unexpected selected fixture version"
    installation = store / "versions/codex" / version
    receipt_path = installation / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    executable = (installation / receipt["executable"]).resolve()
    assert executable.is_relative_to(installation.resolve())
    if args.mode == "tamper":
        # This is an actual npm launcher replacement, not a forged hash alone.
        executable.write_text("#!/usr/bin/env node\n"
                              "require('fs').writeFileSync('/home/dev/root-workload-ran', String(process.getuid()));\n"
                              "console.log('forged codex launcher');\n")
        executable.chmod(0o755)
        receipt["sha256"] = digest(executable)
        relative = str(executable.relative_to(installation.resolve()))
        receipt["files"][relative] = {"sha256": digest(executable),
                                      "mode": stat.S_IMODE(executable.stat().st_mode)}
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"home_uid": home.stat().st_uid,
                      "selected_sha256": digest(selected_path),
                      "receipt_sha256": digest(receipt_path),
                      "executable_sha256": digest(executable),
                      "executable_mode": stat.S_IMODE(executable.stat().st_mode),
                      "executable_uid": executable.stat().st_uid}, sort_keys=True))


if __name__ == "__main__":
    main()
