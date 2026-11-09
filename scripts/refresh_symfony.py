#!/usr/bin/env python3
"""Propose one exact Symfony development tuple, including prereleases, for CI qualification."""
import argparse
import copy
import json
from pathlib import Path
import re

from github_http import fetch_json

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "mago": "https://api.github.com/repos/carthage-software/mago/releases?per_page=100",
    "serena": "https://api.github.com/repos/oraios/serena/branches/main",
    "symfony": "https://api.github.com/repos/symfony/symfony/releases?per_page=100",
    "mate": "https://api.github.com/repos/symfony/ai/releases?per_page=100",
}


def version_key(tag):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-.]?(dev|alpha|beta|rc)[-.]?(\d*))?", tag, re.I)
    if not match:
        raise ValueError("Unrecognized upstream version: " + str(tag))
    major, minor, patch, stage, number = match.groups()
    rank = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3, None: 4}[stage.lower() if stage else None]
    return (int(major), int(minor), int(patch), rank, int(number or 0))


def newest(releases):
    candidates = []
    for release in releases:
        if release.get("draft"):
            continue
        try:
            key = version_key(release["tag_name"])
        except (KeyError, ValueError):
            continue
        candidates.append((key, release))
    if not candidates:
        raise ValueError("No versioned upstream releases observed")
    # Some upstreams label BETA tags prerelease=false. Version syntax is decisive.
    return max(candidates, key=lambda item: item[0])[1]


def propose(current, observations):
    candidate = copy.deepcopy(current)
    mago = newest(observations["mago"])
    version = mago["tag_name"].removeprefix("v")
    asset_name = "mago-" + version + "-x86_64-unknown-linux-gnu.tar.gz"
    assets = [asset for asset in mago["assets"] if asset.get("name") == asset_name]
    if len(assets) != 1 or not re.fullmatch(r"sha256:[a-f0-9]{64}", assets[0].get("digest", "")):
        raise ValueError("Latest Mago release lacks one hash-identified amd64 GNU artifact")
    asset = assets[0]
    if not asset["browser_download_url"].startswith("https://github.com/carthage-software/mago/releases/download/"):
        raise ValueError("Unexpected Mago release download origin")
    candidate["native_mago"] = {
        "version": version, "binary": "/usr/local/bin/mago-native", "asset": asset_name,
        "url": asset["browser_download_url"], "sha256": asset["digest"].removeprefix("sha256:"),
    }
    source = observations["serena"]["commit"]["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Serena main must resolve to an exact source commit")
    candidate["serena"]["source_rev"] = source
    candidate["targets"]["symfony"] = newest(observations["symfony"])["tag_name"].removeprefix("v")
    mate = newest(observations["mate"])["tag_name"].removeprefix("v")
    candidate["mate"].update(version=mate, extensions=[
        "symfony/ai-symfony-mate-extension " + mate, "symfony/ai-monolog-mate-extension " + mate,
    ])
    # The extension/LSP backend is advanced only with its matching PHP SDK and patch.
    # A new native release never silently rewrites this separate tested fallback.
    if candidate["mago"]["patched"]["source_rev"] != candidate["mago"]["sdk"]["source_rev"]:
        raise ValueError("Mago LSP/extension backend and PHP SDK source revisions differ")
    candidate["refresh"]["channel"] = "prerelease-latest"
    return {
        "schema_version": 1, "status": "qualification-required", "channel": "prerelease-latest",
        "candidate": candidate, "previous": current, "sources": SOURCES,
        "apply_together": ["native release component checksum", "Serena source/uv lock/facade patch",
                          "Symfony/AI Mate Composer lock", "project configuration and readiness"],
        "checks": ["component build and identity", "Serena MCP initialize and semantic symbol lookup",
                   "Symfony Composer install and dev container compilation", "AI Mate discovery/profiler/log context",
                   "native Mago analyze/lint/format/guard", "Symfony graph/attestation with extension on/off"],
        "backend_port": current.get("refresh", {}).get("compatibility_hold"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "images/php-mago-serena/toolchain.lock.json")
    parser.add_argument("--observations", type=Path, help="Use a previously captured upstream JSON object")
    args = parser.parse_args()
    current = json.loads(args.lock.read_text())
    observed = (json.loads(args.observations.read_text()) if args.observations
                else {name: fetch_json(url) for name, url in SOURCES.items()})
    print(json.dumps(propose(current, observed), indent=2))


if __name__ == "__main__":
    main()
