"""Expand independently owned component pins for the common runtime identity."""
import json
from pathlib import Path
import re


def compose(root=Path("/opt/xorder")):
    root = Path(root)
    selected = json.loads((root / "chrome-composition.lock.json").read_text())
    browser = json.loads((root / "components/chrome-for-testing-157.lock.json").read_text())
    package = json.loads((root / "chrome-devtools/package.json").read_text())
    version = package["dependencies"]["chrome-devtools-mcp"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Chrome DevTools MCP must have an exact npm version")
    return {"schema_version": 1, "components": selected["components"],
            "browser": browser["browser"], "mcp": {"chrome_devtools_mcp": version}}


if __name__ == "__main__":
    print(json.dumps(compose(), indent=2))
