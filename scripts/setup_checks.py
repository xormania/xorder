#!/usr/bin/env python3
"""Install the checksum-pinned Linux/amd64 check binaries into an explicit directory."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import platform
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def install(spec: dict, destination: Path) -> None:
    url = spec["url"]
    if not url.startswith("https://github.com/"):
        raise ValueError("Check binaries require an HTTPS GitHub release URL")
    request = urllib.request.Request(url, headers={"User-Agent": "xorder-checks"})
    # The release URL is restricted to HTTPS GitHub above.
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != spec["sha256"]:
        raise ValueError(f"Checksum mismatch: {spec['name']}")
    if spec["archive"] == "tar.gz":
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            member = archive.getmember(spec["member"])
            if not member.isfile():
                raise ValueError(f"Expected a regular binary: {spec['name']}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Missing binary: {spec['name']}")
            payload = stream.read()
    elif spec["archive"] != "raw":
        raise ValueError(f"Unsupported archive: {spec['archive']}")
    target = destination / spec["name"]
    target.write_bytes(payload)
    target.chmod(0o755)
    print(f"Installed {spec['name']} {spec['version']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        parser.error("Binary pins currently support Linux/amd64; other targets are unverified")
    args.bin_dir.mkdir(parents=True, exist_ok=True)
    specs = json.loads((ROOT / "checks/tools.json").read_text())["binaries"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda spec: install(spec, args.bin_dir), specs))


if __name__ == "__main__":
    main()
