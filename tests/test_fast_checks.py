import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import checks


class FastCheckTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
