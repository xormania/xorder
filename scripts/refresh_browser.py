#!/usr/bin/env python3
"""Propose a browser image matching an immutable uxor Playwright pin."""
import argparse
import copy
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from library import ROOT, encoded, version
from playwright_fixture import application_image

REPOSITORY = "xormania/uxor"


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "xorder-browser-refresh"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def consumer_pin(ref):
    commit = fetch_json(f"https://api.github.com/repos/{REPOSITORY}/commits/{urllib.parse.quote(ref, safe='')}")["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Consumer must resolve to an immutable commit")
    base = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}"
    package, lock = fetch_json(base + "/package.json"), fetch_json(base + "/package-lock.json")
    pin = package.get("devDependencies", {}).get("@playwright/test")
    if not isinstance(pin, str):
        raise ValueError("Consumer must pin an exact Playwright version")
    version(pin)
    if lock["packages"]["node_modules/@playwright/test"]["version"] != pin:
        raise ValueError("Consumer manifest and lock must pin the same exact Playwright version")
    return {"repository": f"https://github.com/{REPOSITORY}.git", "commit": commit, "playwright_version": pin}


def prepare(pin, root=ROOT):
    browser_version = pin["playwright_version"]
    major, minor, _ = version(browser_version)
    if not re.fullmatch(r"[a-f0-9]{40}", pin["commit"]):
        raise ValueError("Consumer must be pinned to an immutable commit")
    path = root / "images/playwright-browser/definition.json"
    definition = json.loads(path.read_text())
    line = f"{major}.{minor}-trixie"
    previous = definition["lines"].get(line)
    if previous and previous.get("playwright_version") == browser_version:
        return False
    if previous and version(previous["playwright_version"]) > version(browser_version):
        raise ValueError("Refusing an automatic browser downgrade")
    fixture_pin = dict(pin, application_image=application_image(json.loads((root / "catalog-v2.json").read_text())))
    proposal = copy.deepcopy(previous or definition["lines"][sorted(definition["lines"])[-1]])
    proposal.update(runtime_line=f"{major}.{minor}", playwright_version=browser_version,
                    revision="1.0.0" if previous is None else ".".join(map(str, (*version(previous["revision"])[:2], version(previous["revision"])[2] + 1))),
                    changes=[f"Match the consumer's Playwright {browser_version} pin; retain RGB rendering and verify committed screenshot parity."],
                    migration="Select the verified digest matching the consuming lock after publication and catalog acceptance. Existing exact releases remain available.")
    packages = root / "images/playwright-browser/lines" / line
    packages.mkdir(parents=True, exist_ok=True)
    (packages / "package.json").write_text(encoded({"name": "xorder-playwright-browser", "private": True,
        "version": "1.0.0", "dependencies": {"playwright": browser_version}}))
    subprocess.run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=packages, check=True)
    lock = json.loads((packages / "package-lock.json").read_text())
    for package in ("playwright", "playwright-core"):
        item = lock["packages"]["node_modules/" + package]
        if item["version"] != browser_version or not item.get("integrity", "").startswith("sha512-"):
            raise ValueError("Browser closure must contain the exact version and npm integrity hashes")
    definition["lines"][line] = proposal
    path.write_text(encoded(definition))
    fixture = root / "tests/fixtures/playwright/consumers" / (line + ".json")
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(encoded(fixture_pin))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer-ref", default="main", help="Consumer branch, tag or immutable commit")
    parser.add_argument("--pr", action="store_true", help="Use normal feature-branch writeback and open a PR")
    args = parser.parse_args()
    pin = consumer_pin(args.consumer_ref)
    if args.pr:
        from writeback import prepare_branch, upsert_pr, run, output
        current = json.loads((ROOT / "images/playwright-browser/definition.json").read_text())
        if any(item.get("playwright_version") == pin["playwright_version"] for item in current["lines"].values()):
            print("Consumer Playwright pin already has an authored browser line; no proposal")
            return
        run("git", "config", "user.name", "xorder automation")
        run("git", "config", "user.email", "xorder@users.noreply.github.com")
        branch = "automation/browser-" + pin["playwright_version"]
        prepare_branch(branch)
    changed = prepare(pin)
    if not args.pr:
        print("Prepared matching browser inputs" if changed else "No changed browser inputs")
        return
    run("python3", "scripts/library.py", "generate")
    run("python3", "scripts/library.py", "check")
    if output("git", "status", "--porcelain").strip():
        run("git", "add", "images/playwright-browser", "tests/fixtures/playwright/consumers", "catalog.json", "catalog-v2.json", "README.md", "docs")
        run("git", "commit", "-m", "Match consumer Playwright " + pin["playwright_version"])
    if output("git", "log", "--oneline", "origin/master..HEAD").strip():
        run("git", "push", "origin", branch)
        fixture = json.loads((ROOT / "tests/fixtures/playwright/consumers" / (".".join(pin["playwright_version"].split(".")[:2]) + "-trixie.json")).read_text())
        upsert_pr(branch, "Match consumer Playwright " + pin["playwright_version"],
            f"The consumer pins Playwright {pin['playwright_version']} at {fixture['commit']}. This proposes the matching locked browser line with RGB rendering. CI must pass all-engine launch and committed screenshot parity before merge. Publication and catalog acceptance then expose the verified digest. Exact existing image pins remain unchanged.\n\nMerge through normal review; this workflow does not enable automatic merge. LIBRARY_BOT_TOKEN allows PR checks to start automatically.")


if __name__ == "__main__":
    main()
