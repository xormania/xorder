import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import checks


class FastCheckTests(unittest.TestCase):
    def test_required_aggregate_rejects_failed_cancelled_or_skipped_fast_checks(self):
        source = (checks.ROOT / ".github/workflows/validate.yml").read_text().split("  checks:\n", 1)[1]
        needs = re.search(r"needs: \[([^]]+)\]", source)[1].split(", ")
        self.assertIn("fast-checks", needs)
        bindings = re.findall(r"([A-Z_]+): \$\{\{ needs\.([a-z-]+)\.result \}\}", source)
        fast_variable = next(variable for variable, job in bindings if job == "fast-checks")
        script = textwrap.dedent(source.split("        run: |\n", 1)[1])
        environment = {variable: "success" for variable, _ in bindings}
        self.assertEqual(subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                                        env=environment, capture_output=True).returncode, 0)
        for outcome in ("failure", "cancelled", "skipped"):
            with self.subTest(outcome=outcome):
                result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                                        env={**environment, fast_variable: outcome}, capture_output=True)
                self.assertNotEqual(result.returncode, 0)

    def test_duplicate_finding_is_not_covered_by_one_review(self):
        finding = {"filename": "example.py", "test_id": "B108", "code": "1 example()\n"}
        exception = {"path": "example.py", "test_id": "B108",
                     "code_sha256": hashlib.sha256(b"example()").hexdigest(), "reason": "fixture"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checks").mkdir()
            (root / "example.py").write_text("example()\n")
            exception["file_sha256"] = hashlib.sha256((root / "example.py").read_bytes()).hexdigest()
            (root / "checks/bandit-exceptions.json").write_text(json.dumps({"exceptions": [exception]}))
            with patch.object(checks, "ROOT", root):
                remaining, count = checks.reviewed("bandit", [finding, finding])
                self.assertEqual(count, 1)
                self.assertEqual(remaining, [finding])
                with self.assertRaisesRegex(ValueError, "stale/changed"):
                    checks.reviewed("bandit", [{**finding, "code": "1 changed()\n"}])

    def test_later_docker_instruction_change_requires_another_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checks").mkdir()
            source = b"RUN echo checksum\nCOPY app /app\n"
            (root / "Dockerfile").write_bytes(source)
            exception = {"path": "Dockerfile", "line": 1, "rule": "DL4006",
                         "code_sha256": hashlib.sha256(b"RUN echo checksum").hexdigest(),
                         "file_sha256": hashlib.sha256(source).hexdigest(), "reason": "fixture"}
            (root / "checks/hadolint-exceptions.json").write_text(json.dumps({"exceptions": [exception]}))
            finding = {"file": "Dockerfile", "line": 1, "rule": "DL4006"}
            with patch.object(checks, "ROOT", root):
                self.assertEqual(checks.reviewed("hadolint", [finding]), ([], 1))
                (root / "Dockerfile").write_bytes(source + b"RUN changed\n")
                with self.assertRaisesRegex(ValueError, "stale/changed"):
                    checks.reviewed("hadolint", [finding])

    def test_missing_tool_and_engine_failure_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for command in ([str(output / "missing-binary")], [sys.executable, "-c", "raise SystemExit(2)"]):
                self.assertEqual(checks.execute("ruff", command, output)["status"], "error")

    def test_bandit_parse_error_is_not_a_clean_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, "-c", 'print(\'{"results": [], "errors": [{"reason": "parse failure"}]}\')']
            self.assertEqual(checks.execute("bandit", command, Path(directory))["status"], "error")

    def test_bandit_plugin_error_with_valid_empty_report_is_not_a_clean_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            code = 'import sys; print(\'{"results": [], "errors": []}\'); print("Bandit internal error running plugin", file=sys.stderr)'
            self.assertEqual(checks.execute("bandit", [sys.executable, "-c", code], Path(directory))["status"], "error")

    def test_gitleaks_empty_object_is_not_a_clean_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            code = f"from pathlib import Path; Path({str(output / 'gitleaks-history.json')!r}).write_text('{{}}')"
            result = checks.execute("gitleaks-history", [sys.executable, "-c", code], output)
            self.assertEqual(result["status"], "error")

    def test_gitleaks_cannot_reuse_a_stale_clean_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "gitleaks-history.json").write_text("[]")
            result = checks.execute("gitleaks-history", [sys.executable, "-c", "pass"], output)
            self.assertEqual(result["status"], "error")

    @unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks canary runs with the fast-check tools installed")
    def test_build_fingerprint_exception_does_not_hide_a_secret_in_the_same_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Synthetic entropy, assembled at runtime; never a real credential.
            token = hashlib.sha256(b"xorder synthetic scanner canary").hexdigest()
            (root / "catalog.json").write_text(json.dumps({"build_key": token, "api_key": token}, indent=2))
            report = root / "report.json"
            completed = subprocess.run(
                ["gitleaks", "dir", ".", f"--config={checks.ROOT / '.gitleaks.toml'}", "--redact=100",
                 "--no-banner", "--report-format=json", f"--report-path={report}"],
                cwd=root, capture_output=True, text=True, timeout=15)
            self.assertEqual(completed.returncode, 1)
            findings = json.loads(report.read_text())
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["RuleID"], "generic-api-key")
            self.assertNotIn(token, report.read_text())

    @unittest.skipUnless(shutil.which("bandit"), "Bandit canary runs with the fast-check tools installed")
    def test_bandit_tuning_preserves_risk_detection_and_limits_test_exemptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests/fixtures").mkdir(parents=True)
            (root / "production.py").write_text(textwrap.dedent('''\
                import os
                import subprocess
                import requests
                import urllib.request
                def exercise(command):
                    assert command
                    subprocess.run(command, shell=True)
                    runner(command, shell=True)
                    os.system(command)
                    subprocess.run("tar -cf out.tar *", shell=True)
                    requests.get("https://example.invalid", verify=False)
                    urllib.request.urlopen(command)
                    password = "synthetic-production-canary"
                    connect(password="synthetic-argument-canary")
                    return password
                '''))
            (root / "safe.py").write_text(textwrap.dedent('''\
                import os
                import subprocess
                subprocess.run(["git", "--version"])
                os.execvp("git", ["git", "--version"])
                '''))
            (root / "tests/fixtures/probe.py").write_text(textwrap.dedent('''\
                assert True
                password = "synthetic-reviewed-canary"  # nosec B105
                secret = "synthetic-unreviewed-canary"
                '''))
            completed = subprocess.run(
                ["bandit", "-q", "-f", "json", "-c", str(checks.ROOT / "checks/bandit.yaml"),
                 "production.py", "safe.py", "tests/fixtures/probe.py"],
                cwd=root, capture_output=True, text=True, timeout=15)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["errors"], [])
            results = report["results"]
            production_rules = {row["test_id"] for row in results if row["filename"].endswith("/production.py")}
            self.assertTrue({"B101", "B105", "B106", "B501", "B602", "B604", "B605", "B609", "B310"}
                            .issubset(production_rules), production_rules)
            self.assertFalse(any(row["filename"].endswith("/safe.py") for row in results))
            fixture_results = [row for row in results if row["filename"].endswith("/tests/fixtures/probe.py")]
            self.assertEqual([(row["test_id"], row["line_number"]) for row in fixture_results], [("B105", 3)])


if __name__ == "__main__":
    unittest.main()
