import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import checks


class BanditSarifTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "checks").mkdir()
        (self.root / "example.py").write_text("example()\n")
        (self.root / "checks/bandit-exceptions.json").write_text('{"exceptions": []}')
        self.output = self.root / "reports"
        self.output.mkdir()
        self.finding = {
            "filename": "./example.py", "test_id": "B108", "test_name": "hardcoded_tmp_directory",
            "line_number": 1, "code": "1 example()\n", "issue_text": "Review temporary directory use.",
            "issue_severity": "MEDIUM", "issue_confidence": "HIGH",
            "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b108_hardcoded_tmp_directory.html",
        }

    def run_report(self, results, *, errors=None, stderr="", returncode=1):
        report = {"results": results, "errors": errors or []}
        completed = subprocess.CompletedProcess(["bandit"], returncode, json.dumps(report), stderr)
        with patch.object(checks, "ROOT", self.root), patch.object(checks.subprocess, "run", return_value=completed):
            return checks.execute("bandit", ["bandit"], self.output)

    def read_results(self):
        run = json.loads((self.output / "bandit.sarif").read_text())["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "Bandit")
        self.assertTrue(run["invocations"][0]["executionSuccessful"])
        return run["results"]

    def review(self):
        source = (self.root / "example.py").read_bytes()
        entry = {
            "path": "example.py", "test_id": "B108",
            "code_sha256": hashlib.sha256(b"example()").hexdigest(),
            "file_sha256": hashlib.sha256(source).hexdigest(),
            "reason": "This is fixture data used to exercise scanner reporting.",
        }
        (self.root / "checks/bandit-exceptions.json").write_text(json.dumps({"exceptions": [entry]}))
        return entry

    def test_new_blocking_finding_is_uploaded_and_still_fails_gate(self):
        record = self.run_report([self.finding])
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["findings"], 1)
        result = self.read_results()[0]
        self.assertEqual(result["level"], "warning")
        self.assertEqual(result["ruleId"], "B108")
        self.assertNotIn("suppressions", result)
        self.assertEqual(result["locations"][0]["physicalLocation"], {
            "artifactLocation": {"uri": "example.py"}, "region": {"startLine": 1},
        })

    def test_reviewed_finding_keeps_exact_exception_in_separate_audit_report(self):
        entry = self.review()
        record = self.run_report([self.finding])
        self.assertEqual(record["status"], "passed")
        self.assertEqual(record["reviewed"], 1)
        self.assertEqual(self.read_results(), [])
        audit = json.loads((self.output / "bandit-reviewed.json").read_text())
        self.assertEqual(audit["reviewed"], [{"finding": self.finding, "exception": entry}])

    def test_advisory_findings_remain_raw_without_becoming_dashboard_alerts(self):
        low_severity = {**self.finding, "issue_severity": "LOW"}
        low_confidence = {**self.finding, "issue_confidence": "LOW"}
        record = self.run_report([low_severity, low_confidence])
        self.assertEqual(record["status"], "passed")
        self.assertEqual(record["advisory"], 2)
        self.assertEqual(self.read_results(), [])
        self.assertEqual(len(json.loads((self.output / "bandit.json").read_text())["results"]), 2)

    def test_duplicate_is_not_suppressed_by_one_review(self):
        self.review()
        findings = [self.finding, self.finding]
        accepted = {}
        with patch.object(checks, "ROOT", self.root):
            remaining, count = checks.reviewed("bandit", findings, accepted=accepted)
        self.assertEqual(count, 1)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(list(accepted), [0])
        results = checks.bandit_sarif(remaining)["runs"][0]["results"]
        self.assertEqual(len(results), 1)
        self.assertNotIn("suppressions", results[0])

    def test_invalid_json_or_report_structure_cannot_reuse_previous_report(self):
        for stdout in ("not JSON", "[]", '{"results": {}, "errors": []}'):
            with self.subTest(stdout=stdout):
                (self.output / "bandit.sarif").write_text('{"stale": true}')
                completed = subprocess.CompletedProcess(["bandit"], 0, stdout, "")
                with patch.object(checks.subprocess, "run", return_value=completed):
                    record = checks.execute("bandit", ["bandit"], self.output)
                self.assertEqual(record["status"], "error")
                self.assertFalse((self.output / "bandit.sarif").exists())

    def test_scanner_error_or_malformed_finding_removes_stale_sarif(self):
        cases = [
            {"errors": [{"reason": "cannot parse"}]},
            {"stderr": "Bandit internal error running plugin"},
            {"returncode": 2},
            {"results": [{**self.finding, "issue_severity": "UNKNOWN"}]},
            {"results": [{**self.finding, "filename": "../escape.py"}]},
            {"results": [{**self.finding, "line_number": 0}]},
            {"results": [{**self.finding, "test_id": "not-a-rule"}]},
            {"results": [{**self.finding, "issue_text": ""}]},
            {"results": [{**self.finding, "issue_confidence": "LOW", "code": None}]},
        ]
        for case in cases:
            with self.subTest(case=case):
                (self.output / "bandit.sarif").write_text('{"stale": true}')
                record = self.run_report(**{"results": [self.finding], **case})
                self.assertEqual(record["status"], "error")
                self.assertFalse((self.output / "bandit.sarif").exists())

    def test_changed_review_cannot_publish_current_or_stale_clean_report(self):
        self.review()
        (self.root / "example.py").write_text("changed()\n")
        (self.output / "bandit.sarif").write_text('{"stale": true}')
        record = self.run_report([self.finding])
        self.assertEqual(record["status"], "error")
        self.assertIn("stale/changed", record["error"])
        self.assertFalse((self.output / "bandit.sarif").exists())

    def test_missing_binary_cannot_reuse_previous_report(self):
        (self.output / "bandit.sarif").write_text('{"stale": true}')
        with patch.object(checks.subprocess, "run", side_effect=FileNotFoundError("missing Bandit")):
            record = checks.execute("bandit", ["missing-bandit"], self.output)
        self.assertEqual(record["status"], "error")
        self.assertFalse((self.output / "bandit.sarif").exists())

    def test_high_severity_maps_to_error_with_confidence_preserved(self):
        self.run_report([{**self.finding, "issue_severity": "HIGH", "issue_confidence": "MEDIUM"}])
        result = self.read_results()[0]
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["properties"]["issue_confidence"], "MEDIUM")

    def test_only_bandit_does_not_require_or_invoke_other_tools(self):
        observed = []

        def execute(name, command, output):
            observed.append((name, command))
            return {"name": name, "status": "passed", "findings": 0, "reviewed": 0, "seconds": 0}

        with patch.object(checks, "ROOT", self.root), patch.object(checks, "tracked_files", return_value=["example.py"]), \
                patch.object(checks, "execute", side_effect=execute), \
                patch.object(sys, "argv", ["checks.py", "--only", "bandit", "--output", str(self.output)]):
            self.assertEqual(checks.main(), 0)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "bandit")
        self.assertIn("example.py", observed[0][1])


if __name__ == "__main__":
    unittest.main()
