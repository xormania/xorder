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

    def run_report(self, results, *, errors=None, stderr="", returncode=1, dashboard=False):
        report = {"results": results, "errors": errors or []}
        completed = subprocess.CompletedProcess(["bandit"], returncode, json.dumps(report), stderr)
        with patch.object(checks, "ROOT", self.root), patch.object(checks.subprocess, "run", return_value=completed):
            return checks.execute("bandit", ["bandit"], self.output, bandit_dashboard=dashboard)

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
        result = self.read_results()[0]
        self.assertIn(entry["reason"], result["message"]["text"])
        self.assertEqual(result["properties"]["recorded_ci_exception"], entry)
        self.assertNotIn("suppressions", result)
        audit = json.loads((self.output / "bandit-reviewed.json").read_text())
        self.assertEqual(audit["reviewed"], [{"finding": self.finding, "exception": entry}])

    def test_advisory_findings_remain_in_sarif_without_failing_ci_gate(self):
        low_severity = {**self.finding, "issue_severity": "LOW"}
        low_confidence = {**self.finding, "issue_confidence": "LOW"}
        record = self.run_report([low_severity, low_confidence])
        self.assertEqual(record["status"], "passed")
        self.assertEqual(record["advisory"], 2)
        results = self.read_results()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["level"], "note")
        self.assertEqual(results[1]["level"], "warning")
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
        results = checks.bandit_sarif(findings, accepted)["runs"][0]["results"]
        self.assertEqual(len(results), 2)
        self.assertIn("recorded_ci_exception", results[0]["properties"])
        self.assertNotIn("recorded_ci_exception", results[1]["properties"])
        self.assertTrue(all("suppressions" not in row for row in results))

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

    def test_stale_review_warns_without_freezing_complete_dashboard_signal(self):
        self.review()
        (self.root / "example.py").write_text("changed()\n")
        record = self.run_report([self.finding], dashboard=True)
        self.assertEqual(record["status"], "reported")
        self.assertEqual(record["findings"], 1)
        self.assertIn("stale/changed", record["review_warning"])
        result = self.read_results()[0]
        self.assertEqual(result["ruleId"], "B108")
        self.assertNotIn("recorded_ci_exception", result["properties"])
        audit = json.loads((self.output / "bandit-reviewed.json").read_text())
        self.assertEqual(audit["warning"], record["review_warning"])

    def test_dashboard_reports_high_finding_instead_of_applying_ci_threshold(self):
        record = self.run_report([{**self.finding, "issue_severity": "HIGH"}], dashboard=True)
        self.assertEqual(record["status"], "reported")
        self.assertEqual(record["findings"], 1)
        self.assertEqual(self.read_results()[0]["level"], "error")

    def test_dashboard_report_write_failure_is_an_integrity_error(self):
        write_text = Path.write_text

        def fail_sarif(path, *args, **kwargs):
            if path.name == "bandit.sarif":
                write_text(path, "partial report")
                raise OSError("cannot write current SARIF")
            return write_text(path, *args, **kwargs)

        with patch.object(Path, "write_text", new=fail_sarif):
            record = self.run_report([self.finding], dashboard=True)
        self.assertEqual(record["status"], "error")
        self.assertIn("cannot write", record["error"])
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

        def execute(name, command, output, **kwargs):
            observed.append((name, command))
            return {"name": name, "status": "passed", "findings": 0, "reviewed": 0, "seconds": 0}

        with patch.object(checks, "ROOT", self.root), patch.object(checks, "tracked_files", return_value=["example.py"]), \
                patch.object(checks, "execute", side_effect=execute), \
                patch.object(sys, "argv", ["checks.py", "--only", "bandit", "--output", str(self.output)]):
            self.assertEqual(checks.main(), 0)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "bandit")
        self.assertIn("example.py", observed[0][1])

    def test_dashboard_cli_uses_full_scan_and_separate_default_output(self):
        observed = []

        def execute(name, command, output, **kwargs):
            observed.append((name, command, output, kwargs))
            return {"name": name, "status": "reported", "findings": 2, "reviewed": 0, "seconds": 0}

        with patch.object(checks, "ROOT", self.root), patch.object(checks, "tracked_files", return_value=["example.py"]), \
                patch.object(checks, "execute", side_effect=execute), \
                patch.object(sys, "argv", ["checks.py", "--bandit-dashboard"]):
            self.assertEqual(checks.main(), 0)
        self.assertEqual(len(observed), 1)
        name, command, output, kwargs = observed[0]
        self.assertEqual(name, "bandit")
        self.assertIn("--ignore-nosec", command)
        self.assertNotIn("-c", command)
        self.assertNotIn("checks/bandit.yaml", command)
        self.assertEqual(output, self.root / "out/bandit-dashboard")
        self.assertTrue(kwargs["bandit_dashboard"])
        summary = (output / "summary.md").read_text()
        self.assertIn("All findings", summary)
        self.assertIn("not that findings were resolved", summary)

    @unittest.skipUnless(shutil.which("bandit"), "Bandit canary runs with the fast-check tools installed")
    def test_full_dashboard_scan_retains_assertions_and_nosec_annotations(self):
        (self.root / "tests").mkdir()
        source = self.root / "tests/test_probe.py"
        source.write_text("assert True\nresult = eval('1 + 1')  # nosec B307\n")
        (self.root / "checks/bandit.yaml").write_text("assert_used:\n  skips:\n    - tests/test_*.py\n    - ./tests/test_*.py\n")
        command = ["bandit", "-q", "-f", "json"]
        with patch.object(checks, "ROOT", self.root):
            gate = checks.execute("bandit", [*command, "-c", "checks/bandit.yaml", "tests/test_probe.py"], self.output)
            self.assertEqual(gate["status"], "passed")
            self.assertEqual(self.read_results(), [])
            dashboard = checks.execute("bandit", [*command, "--ignore-nosec", "tests/test_probe.py"],
                                       self.output, bandit_dashboard=True)
        self.assertEqual(dashboard["status"], "reported")
        self.assertEqual({row["ruleId"] for row in self.read_results()}, {"B101", "B307"})


if __name__ == "__main__":
    unittest.main()
