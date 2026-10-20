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
from urllib.parse import quote

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


def reviewed(name: str, findings: list[dict], *, accepted: dict[int, dict] | None = None) -> tuple[list[dict], int]:
    """Accept only reviewed findings; changed bytes or duplicate findings fail closed."""
    entries = json.loads((ROOT / f"checks/{name}-exceptions.json").read_text())["exceptions"]
    remaining = list(entries)
    rejected = []
    accepted_count = 0
    for index, finding in enumerate(findings):
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
            if accepted is not None:
                reason = matches[0].get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f"{name}: reviewed exception requires a reason")
                accepted[index] = matches[0]
            remaining.remove(matches[0])
            accepted_count += 1
        else:
            rejected.append(finding)
    if remaining:
        raise ValueError(f"{name}: {len(remaining)} stale/changed reviewed exceptions; review and remove/update them")
    return rejected, accepted_count


def bandit_findings(report: dict) -> list[dict]:
    """Validate and retain every finding in the current scanner report."""
    if not isinstance(report, dict) or not isinstance(report.get("results"), list) or not isinstance(report.get("errors"), list):
        raise ValueError("invalid Bandit report")
    if report["errors"]:
        raise ValueError("Bandit could not parse/scan one or more files")
    for row in report["results"]:
        if not isinstance(row, dict):
            raise ValueError("invalid Bandit finding")
        for field in ("issue_severity", "issue_confidence"):
            if row.get(field) not in {"LOW", "MEDIUM", "HIGH"}:
                raise ValueError(f"invalid Bandit {field}")
        for field in ("filename", "test_id", "test_name", "issue_text", "code"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"invalid Bandit {field}")
        path = Path(row["filename"])
        source = (ROOT / path).resolve()
        if path.is_absolute() or not source.is_relative_to(ROOT.resolve()) or not source.is_file():
            raise ValueError("invalid Bandit source path")
        line = row.get("line_number")
        if type(line) is not int or not 1 <= line <= len(source.read_text().splitlines()):
            raise ValueError("invalid Bandit source line")
        if not re.fullmatch(r"B\d{3}", row["test_id"]):
            raise ValueError("invalid Bandit rule ID")
    return report["results"]


def bandit_sarif(findings: list[dict], accepted: dict[int, dict] | None = None) -> dict:
    """Preserve all scanner findings; recorded reviews annotate, never suppress."""
    rules = []
    indices = {}
    results = []
    for index, row in enumerate(findings):
        rule = row["test_id"]
        if rule not in indices:
            indices[rule] = len(rules)
            descriptor = {"id": rule, "name": row["test_name"]}
            if isinstance(row.get("more_info"), str) and row["more_info"].startswith("https://"):
                descriptor["helpUri"] = row["more_info"]
            rules.append(descriptor)
        result = {
            "ruleId": rule, "ruleIndex": indices[rule],
            "level": {"LOW": "note", "MEDIUM": "warning", "HIGH": "error"}[row["issue_severity"]],
            "message": {"text": row["issue_text"]},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": quote(row["filename"].removeprefix("./"), safe="/")},
                "region": {"startLine": row["line_number"]},
            }}],
            "properties": {"issue_severity": row["issue_severity"], "issue_confidence": row["issue_confidence"]},
        }
        if accepted and index in accepted:
            entry = accepted[index]
            result["message"]["text"] += "\n\nRecorded CI exception: " + entry["reason"]
            result["properties"]["recorded_ci_exception"] = entry
        results.append(result)
    return {
        "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.5.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Bandit", "rules": rules}},
                  "invocations": [{"executionSuccessful": True}], "results": results}],
    }


def execute(name: str, command: list[str], output: Path, *, bandit_dashboard: bool = False) -> dict:
    started = time.monotonic()
    record = {"name": name, "status": "error", "findings": 0, "reviewed": 0}
    try:
        if name == "bandit":
            (output / "bandit.sarif").unlink(missing_ok=True)
            (output / "bandit-reviewed.json").unlink(missing_ok=True)
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
                if re.search(r"\bERROR\b|Bandit internal error", completed.stderr):
                    raise ValueError("Bandit reported an internal/plugin error; see bandit.log")
                findings = bandit_findings(report)
                blocking_indices = [index for index, row in enumerate(findings)
                                    if row["issue_severity"] in {"MEDIUM", "HIGH"}
                                    and row["issue_confidence"] in {"MEDIUM", "HIGH"}]
                record["advisory"] = len(findings) - len(blocking_indices)
            else:
                if not isinstance(report, list):
                    raise ValueError("invalid Hadolint report: expected a list")
                findings = [{**row, "rule": row["code"]} for row in report
                            if row["level"] in {"warning", "error"}]
            accepted = {} if name == "bandit" else None
            if name == "bandit":
                if bandit_dashboard:
                    try:
                        reviewed(name, findings, accepted=accepted)
                    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
                        record["review_warning"] = str(error)
                    unreviewed = []
                    record["reviewed"] = len(accepted)
                    record["findings"] = len(findings)
                    record["status"] = "reported"
                else:
                    blocking = [findings[index] for index in blocking_indices]
                    unreviewed, record["reviewed"] = reviewed(name, blocking, accepted=accepted)
                    accepted = {blocking_indices[index]: entry for index, entry in accepted.items()}
                reviews = {"schema_version": 1, "reviewed": [
                    {"finding": findings[index], "exception": entry} for index, entry in accepted.items()
                ]}
                if record.get("review_warning"):
                    reviews["warning"] = record["review_warning"]
                (output / "bandit-reviewed.json").write_text(json.dumps(reviews, indent=2) + "\n")
                (output / "bandit.sarif").write_text(json.dumps(bandit_sarif(findings, accepted), indent=2) + "\n")
            else:
                unreviewed, record["reviewed"] = reviewed(name, findings)
            if not (name == "bandit" and bandit_dashboard):
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
        record["status"] = "error"
        if name == "bandit":
            (output / "bandit.sarif").unlink(missing_ok=True)
        record["error"] = str(error)
        print(f"{name}: execution error: {error}", flush=True)
    record["seconds"] = round(time.monotonic() - started, 3)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--only", choices=["bandit"], help="Run only the existing Bandit CI gate")
    mode.add_argument("--bandit-dashboard", action="store_true",
                      help="Report every Bandit finding, including assertions and nosec annotations; no finding gate")
    parser.add_argument("--budget-seconds", type=float, default=90)
    parser.add_argument("--started-at", type=float, default=None,
                        help="Unix timestamp before tool installation, for the CI setup+checks target")
    args = parser.parse_args()
    started = args.started_at if args.started_at is not None else time.time()
    args.output = (args.output or ROOT / "out" / ("bandit-dashboard" if args.bandit_dashboard else "fast-checks")).resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bandit.sarif").unlink(missing_ok=True)
    (args.output / "bandit-reviewed.json").unlink(missing_ok=True)
    paths = tracked_files()
    only_bandit = bool(args.only or args.bandit_dashboard)
    shells = [path for path in paths if shell_file(path)] if not only_bandit else []
    python = [path for path in paths if path.endswith(".py")]
    dockerfiles = [path for path in paths if Path(path).name == "Dockerfile"] if not only_bandit else []
    if not python or (not only_bandit and (not shells or not dockerfiles)):
        raise ValueError("Expected maintained shell, Python and Dockerfile inputs; refusing an empty scan")
    commands = [
        ("shellcheck", ["shellcheck", "--format=json1", "--severity=warning", *shells]),
        ("hadolint", ["hadolint", "--format=json", "--failure-threshold=warning", *dockerfiles]),
        ("ruff", ["ruff", "check", "--no-cache", *python]),
        ("actionlint", ["actionlint", "-oneline"]),
        ("zizmor", ["zizmor", "--offline", "--strict-collection", ".github"]),
        ("bandit", ["bandit", "-q", "-f", "json",
                    *(["--ignore-nosec"] if args.bandit_dashboard else ["-c", "checks/bandit.yaml"]), *python]),
    ]
    for mode, command in (("history", ["git", "--log-opts=--all"]), ("worktree", ["dir", "."])):
        name = f"gitleaks-{mode}"
        commands.append((name, ["gitleaks", *command, "--config=.gitleaks.toml", "--redact=100",
                                "--no-banner", "--report-format=json",
                                f"--report-path={args.output / (name + '.json')}"]))
    if only_bandit:
        commands = [(name, command) for name, command in commands if name == "bandit"]
    with ThreadPoolExecutor(max_workers=len(commands)) as pool:
        results = list(pool.map(lambda item: execute(*item, args.output, bandit_dashboard=args.bandit_dashboard), commands))
    elapsed = round(time.time() - started, 3)
    summary = {"seconds": elapsed, "target_seconds": args.budget_seconds,
               "within_target": elapsed <= args.budget_seconds,
               "inputs": {"python": len(python), "shell": len(shells), "dockerfile": len(dockerfiles)},
               "results": results}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    title = "Bandit dashboard scan" if args.bandit_dashboard else "Fast static checks"
    finding_column = "All findings" if args.bandit_dashboard else "New blocking findings"
    lines = [f"### {title}", "", f"| Check | Result | Seconds | {finding_column} | Reviewed |",
             "| --- | --- | ---: | ---: | ---: |"]
    for row in results:
        lines.append(f"| {row['name']} | {row['status']} | {row['seconds']:.3f} | {row['findings']} | {row['reviewed']} |")
    lines.extend(["", f"Setup + checks (when --started-at supplied): **{elapsed:.1f}s / {args.budget_seconds:.0f}s target**.",
                  "The target excludes runner queue/provisioning, checkout and report upload.",
                  "Bandit JSON and SARIF retain every finding from the selected scanner mode.",
                  ""])
    if args.bandit_dashboard:
        lines.append("Reported means the scanner completed, not that findings were resolved. Assertions and nosec annotations remain scanned; recorded reviews do not suppress alerts.")
        for row in results:
            if row.get("review_warning"):
                lines.append(f"Review metadata warning: {row['review_warning']}")
    elif not only_bandit:
        lines.append("zizmor runs offline; online vulnerability/stale-reference audits are not included.")
    if not summary["within_target"]:
        lines.append("Runtime exceeded the target; inspect timings before broadening the suite.")
    markdown = "\n".join(lines)
    (args.output / "summary.md").write_text(markdown)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(markdown)
    print(markdown, flush=True)
    expected = "reported" if args.bandit_dashboard else "passed"
    return int(any(row["status"] != expected for row in results))


if __name__ == "__main__":
    sys.exit(main())
