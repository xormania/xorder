"""Independent fixture routing and the accepted-artifact boundary for CI."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
from image_validation import supported_suites


ROOT = Path(__file__).resolve().parents[1]
LINE = "python-dev/3.14-trixie"
DIGEST = "ghcr.io/xormania/python-dev@sha256:" + "a" * 64


class BuilderSuiteTests(unittest.TestCase):
    def arguments(self, destination, suites, lines=None):
        return [LINE, "candidate:test", "--reuse-accepted", "--inventory", str(destination),
                "--verify-lines", json.dumps([LINE] if lines is None else lines),
                "--verify-suites", json.dumps(suites)]

    def test_partial_checks_extend_only_an_exact_accepted_artifact(self):
        for reused, expected, status in ((DIGEST, ["trust", "native"], "partial-passed"),
                                         (None, ["full"], "passed")):
            with self.subTest(reused=bool(reused)), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(build, "reusable_artifact", return_value=reused), \
                    patch.object(build.subprocess, "run") as docker, \
                    patch.object(build, "build") as builder, \
                    patch.object(build, "verify") as verifier, \
                    patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
                destination = Path(temporary) / "inventory.json"
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(self.arguments(destination, {LINE: ["trust", "native"]}))
                if reused:
                    builder.assert_not_called()
                    docker.assert_called_once_with(["docker", "pull", "--platform", "linux/amd64", DIGEST], check=True)
                    verifier.assert_called_once_with(LINE, DIGEST, str(destination), suites=expected)
                else:
                    builder.assert_called_once()
                    verifier.assert_called_once_with(LINE, "candidate:test", str(destination))
                metrics = json.loads(destination.with_suffix(".metrics.json").read_text())
                self.assertEqual(metrics["verification_suites"], expected)
                self.assertEqual(metrics["requested_verification_suites"], ["trust", "native"])
                self.assertEqual(metrics["verification_status"], status)

    def test_invalid_suite_plans_fail_before_any_docker_action(self):
        for suites in (None, [], {}, {LINE: []}, {LINE: "trust"}, {LINE: ["unknown"]},
                       {LINE: ["trust", "trust"]}, {LINE: ["full", "trust"]},
                       {LINE: [3]}, {"rust-dev/1.99-trixie": ["trust"]},
                       {LINE: ["trust"], "missing/image": ["full"]}):
            with self.subTest(suites=suites), patch.object(build, "reusable_artifact") as reuse, \
                    patch.object(build.subprocess, "run") as docker, patch.object(build, "build") as builder, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    build.main(self.arguments("unused.json", suites))
                reuse.assert_not_called()
                docker.assert_not_called()
                builder.assert_not_called()

    def test_suite_plan_requires_explicit_matching_lines_and_supported_families(self):
        cases = [
            [LINE, "candidate:test", "--verify-suites", json.dumps({LINE: ["trust"]})],
            self.arguments("unused.json", {LINE: ["trust"]}, ["rust-dev/1.99-trixie"]),
            ["harness-live/trixie", "candidate:test", "--verify-lines", '["harness-live/trixie"]',
             "--verify-suites", '{"harness-live/trixie":["native"]}'],
            ["playwright-browser/1.58-trixie", "candidate:test", "--verify-lines", '["playwright-browser/1.58-trixie"]',
             "--verify-suites", '{"playwright-browser/1.58-trixie":["trust"]}'],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments), patch.object(build.subprocess, "run") as docker, \
                    patch.object(build, "build") as builder, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                docker.assert_not_called()
                builder.assert_not_called()

    def test_partial_uxor_does_not_prepare_or_grant_project_source_proof(self):
        with patch.object(build.subprocess, "run") as run, patch.object(build, "inspect") as inspect, \
                patch("xorder.downstream.observe_source_images", side_effect=AssertionError("Project fixture should not run")), \
                patch.dict(os.environ, {"XORDER_SOURCE_VALIDATION_PROOF": "/caller/proof"}):
            build.verify("uxor-dev/8.5-trixie", DIGEST, "inventory.json", suites=["trust"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-1], "trust")
        self.assertNotIn("XORDER_SOURCE_VALIDATION_PROOF", run.call_args.kwargs["env"])
        inspect.assert_called_once_with("uxor-dev/8.5-trixie", DIGEST, "inventory.json")

    def test_default_public_verifier_still_runs_full_readiness(self):
        with patch.object(build.subprocess, "run") as run, patch.object(build, "inspect") as inspect:
            build.verify(LINE, DIGEST, "inventory.json")
        self.assertEqual(run.call_args.args[0], ["bash", str(ROOT / "scripts/verify-image.sh"), LINE, DIGEST])
        inspect.assert_called_once_with(LINE, DIGEST, "inventory.json")


class ShellSuiteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="xorder-verification-suites-")
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.root = self.area / "repo"
        self.bin = self.area / "bin"
        self.bin.mkdir()
        self.log = self.area / "calls.jsonl"
        self.environment = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                                SUITE_LOG=str(self.log))
        self.environment.pop("CA_CERTIFICATE", None)
        self.write("scripts/verify-image.sh", (ROOT / "scripts/verify-image.sh").read_text())
        self.write("scripts/run-image.sh", (ROOT / "scripts/run-image.sh").read_text())
        self.write("tests/fixtures/native-check.c", "int main(void) {return 0;}\n")
        self.write("tests/fixtures/trust/run.sh", '''#!/bin/bash
set -eu
printf '%s\\n' trust >> "$SUITE_LOG"
exit "${SUITE_TRUST_EXIT:-0}"
''')
        # A project suite would fail visibly if partial dispatch reached it.
        self.write("tests/fixtures/uxor/run.sh", "#!/bin/bash\nexit 99\n")
        self.write("tests/fixtures/php-toolkit/run.sh", "#!/bin/bash\nexit 99\n")
        self.write("tests/fixtures/serena/check.py", "raise SystemExit(99)\n")
        docker = self.bin / "docker"
        docker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["SUITE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[0] == "run":
    for index, arg in enumerate(args[:-1]):
        if arg == "--mount" and args[index + 1].endswith("dst=/workspace"):
            source = args[index + 1].split("src=", 1)[1].split(",dst=", 1)[0]
            assert (pathlib.Path(source) / "native-check.c").is_file()
    assert args[-3:] == ["bash", "-c", "cc native-check.c -o native-proof && ./native-proof"]
    raise SystemExit(int(os.environ.get("SUITE_NATIVE_EXIT", "0")))
''')
        docker.chmod(0o755)

    def write(self, relative, contents):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def execute(self, family, *suites, **environment):
        return subprocess.run(["bash", str(self.root / "scripts/verify-image.sh"), family + "/fixture",
                               "candidate:test", *suites], env=dict(self.environment, **environment),
                              capture_output=True, text=True, timeout=20)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_independent_suites_skip_every_project_fixture(self):
        for family in ("uxor-dev", "php-toolkit", "php-serena"):
            with self.subTest(family=family):
                self.log.unlink(missing_ok=True)
                result = self.execute(family, "trust", "native")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = self.calls()
                self.assertEqual(calls[0], "trust")
                self.assertEqual(json.loads(calls[1])[0], "run")
                self.assertEqual(json.loads(calls[2])[:2], ["volume", "rm"])
                self.assertIn("trust native", result.stdout)

    def test_shell_and_python_agree_on_family_suite_support(self):
        families = ("php-dev", "php-browser", "php-toolkit", "php-serena", "php-frankenphp", "uxor-dev",
                    "python-dev", "rust-dev", "harness-live", "python-matrix", "playwright-browser", "future-family")
        for family in families:
            for suite in ("trust", "native"):
                with self.subTest(family=family, suite=suite):
                    self.log.unlink(missing_ok=True)
                    result = self.execute(family, suite)
                    if suite in supported_suites(family):
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertEqual(result.returncode, 64, result.stderr)
                        self.assertEqual(self.calls(), [])

    def test_invalid_request_is_rejected_before_even_an_earlier_valid_suite(self):
        for suites in (("trust", "invalid"), ("full", "trust"), ("trust", "full"), ("",)):
            with self.subTest(suites=suites):
                self.log.unlink(missing_ok=True)
                result = self.execute("uxor-dev", *suites)
                self.assertEqual(result.returncode, 64)
                self.assertEqual(self.calls(), [])

    def test_fixture_failures_propagate_and_native_cleanup_runs(self):
        for suite, environment in (("trust", {"SUITE_TRUST_EXIT": "37"}),
                                    ("native", {"SUITE_NATIVE_EXIT": "37"})):
            with self.subTest(suite=suite):
                self.log.unlink(missing_ok=True)
                result = self.execute("uxor-dev", suite, **environment)
                self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
                if suite == "native":
                    self.assertEqual(json.loads(self.calls()[-1])[:2], ["volume", "rm"])

    def test_verifier_does_not_inventory_a_failed_fixture(self):
        with patch.object(build, "ROOT", self.root), patch.object(build, "inspect") as inspect, \
                patch.dict(os.environ, dict(self.environment, SUITE_TRUST_EXIT="37"), clear=True):
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                build.verify(LINE, "candidate:test", "unused.json", suites=["trust"])
        self.assertEqual(raised.exception.returncode, 37)
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
