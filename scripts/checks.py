#!/usr/bin/env python3
"""Run xorder's fast, local/CI static checks and retain their actual results."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True
    )
    return sorted({path for path in result.stdout.decode().split("\0") if path and (ROOT / path).is_file()})


def shell_file(path: str) -> bool:
    if path.endswith(".sh"):
        return True
    with (ROOT / path).open("rb") as stream:
        first_line = stream.readline(256)
    return bool(re.match(rb"^#!.*(?:/|\s)(?:ba|da|k|a)?sh(?:\s|$)", first_line))


def reviewed(name: str, findings: list[dict]) -> tuple[list[dict], int]:
    """Accept only reviewed findings; changed bytes or duplicate findings fail closed."""
    entries = json.loads((ROOT / f"checks/{name}-exceptions.json").read_text())["exceptions"]
    remaining = list(entries)
    rejected = []
    accepted = 0
    for finding in findings:
        path = finding.get("file", finding.get("filename", "")).removeprefix("./")
        rule = finding.get("rule", finding.get("test_id"))
        if name == "bandit":
            code = re.sub(r"^\d+ ", "", finding["code"], flags=re.MULTILINE).strip()
            digest = hashlib.sha256(code.encode()).hexdigest()
            matches = [entry for entry in remaining if entry["path"] == path
                       and entry["test_id"] == rule and entry["code_sha256"] == digest
                       and entry["file_sha256"] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()]
        else:
            source = (ROOT / path).read_bytes()
            line = finding["line"]
            digest = hashlib.sha256(source.decode().splitlines()[line - 1].encode()).hexdigest()
            matches = [entry for entry in remaining if entry["path"] == path and entry["rule"] == rule
                       and entry["line"] == line and entry["code_sha256"] == digest
                       and entry["file_sha256"] == hashlib.sha256(source).hexdigest()]
        if len(matches) == 1:
            remaining.remove(matches[0])
            accepted += 1
        else:
            rejected.append(finding)
    if remaining:
        raise ValueError(f"{name}: {len(remaining)} stale/changed reviewed exceptions; review and remove/update them")
    return rejected, accepted


def execute(name: str, command: list[str], output: Path) -> dict:
    started = time.monotonic()
    record = {"name": name, "status": "error", "findings": 0, "reviewed": 0}
    try:
        if name in {"gitleaks-history", "gitleaks-worktree"}:
            (output / f"{name}.json").unlink(missing_ok=True)
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=75)
        (output / f"{name}.log").write_text(completed.stderr)
        if name in {"actionlint", "zizmor", "ruff"}:
            (output / f"{name}.txt").write_text(completed.stdout)
        if completed.returncode not in {0, 1}:
            raise ValueError(f"tool exited {completed.returncode}; see {name}.log")
        if name in {"gitleaks-history", "gitleaks-worktree"}:
            report = output / f"{name}.json"
            if not report.is_file():
                raise ValueError("missing Gitleaks report")
            findings = json.loads(report.read_text())
            if not isinstance(findings, list):
                raise ValueError("invalid Gitleaks report: expected a list")
            record["findings"] = len(findings)
            record["status"] = "passed" if completed.returncode == 0 and not findings else "failed"
        elif name in {"shellcheck", "hadolint", "bandit"}:
            report = json.loads(completed.stdout)
            (output / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
            if name == "shellcheck":
                if not isinstance(report, dict) or not isinstance(report.get("comments"), list):
                    raise ValueError("invalid ShellCheck report")
                findings = [{**row, "rule": f"SC{row['code']}"} for row in report["comments"]]
            elif name == "bandit":
                if not isinstance(report, dict) or not isinstance(report.get("results"), list) or not isinstance(report.get("errors"), list):
                    raise ValueError("invalid Bandit report")
                if re.search(r"\bERROR\b|Bandit internal error", completed.stderr):
                    raise ValueError("Bandit reported an internal/plugin error; see bandit.log")
                if report.get("errors"):
                    raise ValueError("Bandit could not parse/scan one or more files")
                findings = [row for row in report["results"]
                            if row["issue_severity"] in {"MEDIUM", "HIGH"}
                            and row["issue_confidence"] in {"MEDIUM", "HIGH"}]
                record["advisory"] = len(report["results"]) - len(findings)
            else:
                if not isinstance(report, list):
                    raise ValueError("invalid Hadolint report: expected a list")
                findings = [{**row, "rule": row["code"]} for row in report
                            if row["level"] in {"warning", "error"}]
            unreviewed, record["reviewed"] = reviewed(name, findings)
            record["findings"] = len(unreviewed)
            record["status"] = "failed" if unreviewed else "passed"
            for row in unreviewed:
                location = row.get("file", row.get("filename", ""))
                line = row.get("line", row.get("line_number", ""))
                rule = row.get("rule", row.get("test_id", ""))
                print(f"{name}: {location}:{line}: {rule}", flush=True)
        else:
            (output / f"{name}.txt").write_text(completed.stdout)
            record["status"] = "passed" if completed.returncode == 0 else "failed"
            if completed.returncode:
                # Gitleaks never enters this branch; its output is always fully redacted.
                print(completed.stdout[:12000], flush=True)
    except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.TimeoutExpired) as error:
        record["error"] = str(error)
        print(f"{name}: execution error: {error}", flush=True)
    record["seconds"] = round(time.monotonic() - started, 3)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "out/fast-checks")
    parser.add_argument("--budget-seconds", type=float, default=90)
    parser.add_argument("--started-at", type=float, default=None,
                        help="Unix timestamp before tool installation, for the CI setup+checks target")
    args = parser.parse_args()
    started = args.started_at if args.started_at is not None else time.time()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = tracked_files()
    shells = [path for path in paths if shell_file(path)]
    python = [path for path in paths if path.endswith(".py")]
    dockerfiles = [path for path in paths if Path(path).name == "Dockerfile"]
    if not shells or not python or not dockerfiles:
        raise ValueError("Expected maintained shell, Python and Dockerfile inputs; refusing an empty scan")
    commands = [
        ("shellcheck", ["shellcheck", "--format=json1", "--severity=warning", *shells]),
        ("hadolint", ["hadolint", "--format=json", "--failure-threshold=warning", *dockerfiles]),
        ("ruff", ["ruff", "check", "--no-cache", *python]),
        ("actionlint", ["actionlint", "-oneline"]),
        ("zizmor", ["zizmor", "--offline", "--strict-collection", ".github"]),
        ("bandit", ["bandit", "-q", "-f", "json", "-c", "checks/bandit.yaml", *python]),
    ]
    for mode, command in (("history", ["git", "--log-opts=--all"]), ("worktree", ["dir", "."])):
        name = f"gitleaks-{mode}"
        commands.append((name, ["gitleaks", *command, "--config=.gitleaks.toml", "--redact=100",
                                "--no-banner", "--report-format=json",
                                f"--report-path={args.output / (name + '.json')}"]))
    with ThreadPoolExecutor(max_workers=len(commands)) as pool:
        results = list(pool.map(lambda item: execute(*item, args.output), commands))
    elapsed = round(time.time() - started, 3)
    summary = {"seconds": elapsed, "target_seconds": args.budget_seconds,
               "within_target": elapsed <= args.budget_seconds,
               "inputs": {"python": len(python), "shell": len(shells), "dockerfile": len(dockerfiles)},
               "results": results}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["### Fast static checks", "", "| Check | Result | Seconds | New blocking findings | Reviewed |",
             "| --- | --- | ---: | ---: | ---: |"]
    for row in results:
        lines.append(f"| {row['name']} | {row['status']} | {row['seconds']:.3f} | {row['findings']} | {row['reviewed']} |")
    lines.extend(["", f"Setup + checks (when --started-at supplied): **{elapsed:.1f}s / {args.budget_seconds:.0f}s target**.",
                  "The target excludes runner queue/provisioning, checkout and report upload.",
                  "Bandit low-severity/low-confidence findings remain in bandit.json; execution errors fail the check.",
                  "zizmor runs offline; online vulnerability/stale-reference audits are not included.", ""])
    if not summary["within_target"]:
        lines.append("Runtime exceeded the target; inspect timings before broadening the suite.")
    markdown = "\n".join(lines)
    (args.output / "summary.md").write_text(markdown)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(markdown)
    print(markdown, flush=True)
    return int(any(row["status"] != "passed" for row in results))


if __name__ == "__main__":
    sys.exit(main())
