"""Select behavior checks separately from image build prerequisites."""
import json
from pathlib import Path

from image_inputs import TOOL_KEYS, consumes


METADATA_SCRIPTS = {
    "scripts/release.py", "scripts/writeback.py", "scripts/refresh.py", "scripts/github_http.py",
    "scripts/registry.py", "scripts/xorder_cli.py", "scripts/validation_base.py",
    "scripts/catalog_checks.py", "scripts/catalog_summary.py",
    "scripts/refresh_browser.py", "scripts/browser_release.py",
    "scripts/image_assurance.py", "scripts/agent_eval.py",
    "scripts/claude_prompt_clock.py",
    "scripts/release_groups.py", "scripts/group_writeback.py",
    "scripts/retention.py", "scripts/publication_attempt.py",
    "examples/shared/failure_hooks.py", "examples/jev/failure_triage.py",
    "examples/jev/failure-questions.json",
}
METADATA_WORKFLOWS = {
    ".github/workflows/publish.yml", ".github/workflows/refresh.yml",
    ".github/workflows/aliases.yml", ".github/workflows/catalog.yml",
    ".github/workflows/browser-refresh.yml",
    ".github/workflows/release-groups.yml",
}
METADATA_SCHEMAS = {
    "schemas/definition.schema.json", "schemas/release-record.schema.json",
    "schemas/catalog.schema.json", "schemas/resource.schema.json",
    "schemas/artifact-release-record.schema.json", "schemas/catalog-v2.schema.json",
    "schemas/profile.schema.json", "schemas/resolution-lock.schema.json",
    "schemas/installation-receipt.schema.json",
    "schemas/discovery-organization.schema.json", "schemas/agent-observation.schema.json",
    "schemas/release-groups.schema.json",
}


def descendants(selected, defs):
    """Include consumers whose exact parent artifact may change."""
    selected = set(selected)
    while True:
        children = {line for line, d in defs.items() if d["base"].get("parent") in selected}
        if children <= selected:
            return sorted(selected)
        selected.update(children)


def prerequisites(root, selected, defs):
    """Return only selected nodes and their ancestor paths within one build tree."""
    needed = {root}
    for line in selected:
        if line not in defs:
            raise ValueError(f"Unknown image line: {line}")
        while line != root:
            needed.add(line)
            line = defs[line]["base"].get("parent")
            if line is None:
                raise ValueError(f"Selected image is outside the {root} build tree")
    return needed


def affected_lines(changed, defs, root, previous_tools=None, previous_definitions=None):
    """Propagate changed artifact inputs; keep fixture-only checks on their consumers."""
    selected, inputs = set(), set()
    for path in changed:
        if (path.startswith(("scripts/xorder/", "artifacts/", "profiles/", "discovery/", "lifecycle/", "tests/agent-evals/", "tests/scenarios/",
                             "tests/fixtures/devenv/", "tests/fixtures/artifacts/",
                             "examples/resources/", "examples/devenv/",
                             "tests/test_", "tests/requirements/"))
                or path in METADATA_SCRIPTS | METADATA_WORKFLOWS | METADATA_SCHEMAS):
            continue
        families = set()
        is_input = False
        if path == "images/tools.json":
            current = json.loads((Path(root) / path).read_text())
            keys = set(current) | set(previous_tools or {})
            if previous_tools is not None:
                keys = {key for key in keys if current.get(key) != previous_tools.get(key)}
            families = {family for family, used in TOOL_KEYS.items() if keys.intersection(used)}
            is_input = True
        elif path.startswith("images/") and path.endswith("/definition.json"):
            current_path = Path(root) / path
            # Retired definitions have no current artifact to validate. Renames
            # arrive as a deletion plus an addition; process the added path below.
            if not current_path.is_file():
                continue
            current = json.loads(current_path.read_text())
            family = current["family"]
            family_lines = {line for line, d in defs.items() if d["family"] == family}
            previous = (previous_definitions or {}).get(path)
            if previous is not None:
                common = lambda d: {key: value for key, value in d.items() if key != "lines"}
                if common(current) == common(previous):
                    family_lines = {line for line in family_lines
                                    if current["lines"][defs[line]["line"]] != previous["lines"].get(defs[line]["line"])}
            inputs.update(family_lines)
            continue
        else:
            # COPY inputs can live outside images/, such as prepared Toolkit locks.
            inputs.update(line for line, d in defs.items() if consumes(d["family"], path, root, d.get("line")))
            if path.startswith("images/shared/") or path == ".dockerignore":
                continue
            elif path.startswith(("tests/fixtures/php/", "tests/fixtures/mutation/")):
                families = {"php-dev", "php-browser", "php-toolkit", "php-serena", "php-frankenphp", "uxor-dev"}
            elif path.startswith(("examples/php-toolkit/", "tests/fixtures/php-toolkit/")):
                families = {"php-toolkit"}
            elif path.startswith(("examples/serena/", "tests/fixtures/serena/")):
                families = {"php-serena"}
            elif path.startswith("tests/fixtures/playwright/consumers/"):
                selected.update(line for line, d in defs.items() if d["family"] == "playwright-browser"
                                and path == f"tests/fixtures/playwright/consumers/{d['line']}.json")
                continue
            elif path == "scripts/playwright_fixture.py" or path.startswith("tests/fixtures/playwright/"):
                families = {"playwright-browser"}
            elif path.startswith("tests/fixtures/frankenphp/"):
                families = {"php-frankenphp", "uxor-dev"}
            elif path.startswith(("examples/shared/", "tests/fixtures/network/")):
                families = {"uxor-dev", "php-toolkit"}
            elif path.startswith(("examples/uxor/", "tests/fixtures/uxor/")):
                families = {"uxor-dev"}
            elif path.startswith("examples/php/"):
                families = {"php-dev", "php-browser", "php-toolkit", "php-serena", "php-frankenphp", "uxor-dev", "python-dev"}
            elif path.startswith("tests/fixtures/python/"):
                families = {"python-dev"}
            elif path.startswith("tests/fixtures/python-matrix/"):
                families = {"python-matrix"}
            elif path.startswith("tests/fixtures/rust/"):
                families = {"rust-dev"}
            elif path.startswith(("scripts/", "schemas/", "tests/", "examples/", ".github/workflows/")):
                selected.update(defs)
                continue
            else:
                if path.startswith("images/playwright-browser/lines/"):
                    # Exact COPY consumers above already retain the affected line.
                    continue
                families = {d["family"] for d in defs.values() if path.startswith(f"images/{d['family']}/")}
                is_input = True
        target = inputs if is_input else selected
        target.update(line for line, d in defs.items() if d["family"] in families)
    return sorted(selected | set(descendants(inputs, defs)))


def matrix(selected, defs):
    """Group checks by root to share local parents, retaining exact test targets."""
    groups = {}
    for line in sorted(set(selected)):
        root = line
        while defs[root]["base"].get("parent"):
            root = defs[root]["base"]["parent"]
        groups.setdefault(root, []).append(line)
    return {"include": [{"line": root, "verify_lines": lines} for root, lines in sorted(groups.items())]}
