#!/usr/bin/env python3
"""Resolve moving upstream inputs into reviewable pins and fresh revisions."""
import json
import copy
import re
import subprocess
import urllib.request
from library import ROOT, encoded, read, version
from registry import resolve
from image_inputs import TOOL_KEYS
from github_http import fetch_json


APT_RELEASES = (
    "https://deb.debian.org/debian/dists/trixie/Release",
    "https://deb.debian.org/debian/dists/trixie-updates/Release",
    "https://security.debian.org/debian-security/dists/trixie-security/Release",
)


def apt_indexes():
    """Track package-index changes, excluding Release dates and signatures."""
    result = {}
    for url in APT_RELEASES:
        # APT_RELEASES is a fixed list of HTTPS Debian release endpoints.
        with urllib.request.urlopen(url, timeout=60) as response:  # nosec B310
            text = response.read().decode()
        match = re.search(r"^ ([a-f0-9]{64})\s+\d+\s+main/binary-amd64/Packages.xz$", text, re.M)
        if not match:
            raise ValueError(f"No amd64 package-index checksum in {url}")
        result[url] = match[1]
    return result


def refresh(base_ref=None):
    def inputs(path):
        if base_ref:
            return json.loads(subprocess.check_output(
                ["git", "show", f"{base_ref}:{path.relative_to(ROOT)}"], cwd=ROOT, text=True))
        return read(path)

    tools_path = ROOT / "images/tools.json"
    tools = inputs(tools_path)
    previous_tools = copy.deepcopy(tools)
    for name in ("composer", "uv", "node"):
        tools[name]["digest"] = resolve(tools[name]["tag"])["digest"]
    for name in ("redis", "xdebug", "pcov", "apcu"):
        # Both the HTTPS origin and the extension-name set are fixed here.
        with urllib.request.urlopen(f"https://pecl.php.net/rest/r/{name}/stable.txt", timeout=60) as response:  # nosec B310
            tools[name + "_version"] = response.read().decode().strip()
    release = fetch_json("https://api.github.com/repos/symfony-cli/symfony-cli/releases/latest")
    asset = next(a for a in release["assets"] if a["name"] == "symfony-cli_linux_amd64.tar.gz")
    if not (isinstance(asset.get("digest"), str) and re.fullmatch(r"sha256:[a-f0-9]{64}", asset["digest"])):
        raise AssertionError("No upstream artifact checksum")
    tools["symfony"] = {"version": release["tag_name"].removeprefix("v"), "url": asset["browser_download_url"], "sha256": asset["digest"].removeprefix("sha256:")}
    release = fetch_json("https://api.github.com/repos/infection/infection/releases/latest")
    asset = next(a for a in release["assets"] if a["name"] == "infection.phar")
    if not (isinstance(asset.get("digest"), str) and re.fullmatch(r"sha256:[a-f0-9]{64}", asset["digest"])):
        raise AssertionError("No upstream Infection artifact checksum")
    tools["infection"] = {"version": release["tag_name"].removeprefix("v"), "url": asset["browser_download_url"], "sha256": asset["digest"].removeprefix("sha256:")}
    tools["apt_indexes"] = apt_indexes()
    if tools != previous_tools:
        tools_path.write_text(encoded(tools))
    changed_keys = {key for key in set(tools) | set(previous_tools) if tools.get(key) != previous_tools.get(key)}
    proposals = {}
    changed_lines = set()
    for path in (ROOT / "images").glob("*/definition.json"):
        d = inputs(path)
        proposals[path] = d
        for name, line in d["lines"].items():
            before = copy.deepcopy(line["base"])
            if "tag" in line["base"]:
                line["base"]["digest"] = resolve(line["base"]["tag"])["digest"]
            if line["base"] != before or changed_keys.intersection(TOOL_KEYS.get(d["family"], ())):
                changed_lines.add(f"{d['family']}/{name}")
    # A changed parent requires each derived consumer's new exact revision.
    while True:
        descendants = {f"{d['family']}/{name}" for d in proposals.values() for name, line in d["lines"].items()
                       if line["base"].get("parent") in changed_lines}
        if descendants <= changed_lines:
            break
        changed_lines.update(descendants)
    for path, d in proposals.items():
        selected = False
        for name, line in d["lines"].items():
            if f"{d['family']}/{name}" not in changed_lines:
                continue
            selected = True
            major, minor, patch = version(line["revision"])
            line["revision"] = f"{major}.{minor}.{patch + 1}"
            line["changes"] = ["Refresh locked upstream inputs and Debian packages; preserve the advertised development contract."]
            line["migration"] = "Compatible refresh. Update the digest deliberately after project validation; retain the previous exact release for rollback."
        if selected:
            path.write_text(encoded(d))
    print(f"Resolved upstream inputs; {len(changed_lines)} changed image lines receive fresh patch revisions. Unchanged inputs allocate no rebuild. Apt package versions remain measured from each artifact.")


if __name__ == "__main__":
    refresh()
