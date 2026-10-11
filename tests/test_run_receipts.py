"""Actual reporter events, preserved reporting, attempt isolation and exit status."""
import http.server
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
import test_receipts as receipts


class ReceiptTests(unittest.TestCase):
    def test_every_explicit_worker_form_is_capped_and_filters_are_preserved(self):
        for workers in (["--workers=6"], ["--workers", "6"], ["-j", "6"], ["-j6"], ["-j=6"], ["--workers=100%"]):
            with self.subTest(workers=workers):
                self.assertEqual(receipts.capped_workers(["spec.ts", *workers, "--grep", "small", "--", "-j8"], 2, 8),
                                 ["--workers=2", "spec.ts", "--grep", "small", "--", "-j8"])
        self.assertEqual(receipts.capped_workers(["--workers=1"], 2, 8), ["--workers=1"])
        self.assertEqual(receipts.capped_workers(["-j8", "--workers=1"], 2, 8), ["--workers=1"])
        for value in ("0", "-1", "nan%", "inf%", "bad"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Worker setting"):
                receipts.capped_workers(["--workers=" + value], 2, 8)

    @unittest.skipUnless(__import__('shutil').which('node'), "Node is required to verify actual process signal status")
    def test_launcher_preserves_signal_specific_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "npx"
            executable.write_text("#!/usr/bin/env python3\nimport os,signal\nos.kill(os.getpid(),getattr(signal,os.environ['PAYLOAD_SIGNAL']))\n")
            executable.chmod(0o755)
            for signal_name, expected in (("SIGINT", 130), ("SIGTERM", 143), ("SIGKILL", 137)):
                with self.subTest(signal=signal_name):
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                               XORDER_TEST_CONTROL_DIR=str(root / signal_name), PAYLOAD_SIGNAL=signal_name)
                    result = subprocess.run(["node", str(ROOT / "examples/flowbite-xor/receipt-launcher.cjs")],
                                            env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, expected, result.stderr)

    def test_runner_options_leave_consumer_filters_and_explicit_workers_intact(self):
        env = {}
        self.assertEqual(receipts.parse_test_options(["--wait", "--measure", "one.spec.ts", "--grep", "hello", "-j", "3"], env),
                         ["one.spec.ts", "--grep", "hello", "-j", "3"])
        self.assertEqual(env, {"XORDER_TEST_WAIT_SECONDS": "600", "XORDER_TEST_MEASURE": "1"})
        self.assertEqual(receipts.parse_test_options(["--wait", "0.25", "--", "--measure"], env), ["--", "--measure"])
        self.assertEqual(env["XORDER_TEST_WAIT_SECONDS"], "0.25")
        self.assertEqual(receipts.parse_test_options(["--attest-server", "spec.ts"], env), ["spec.ts"])
        self.assertEqual(env["XORDER_TEST_ATTEST_SERVER"], "1")
        for value in ("-1", "nan", "inf", "nope"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                receipts.parse_test_options(["--wait=" + value], {})

    def test_receipt_uses_observed_cases_retains_original_failure_and_attempt_history(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            source = workspace / "actual.spec.ts"
            source.write_text("test bytes before\n")
            env = dict(os.environ, XDG_CACHE_HOME=str(Path(directory) / "cache"), PUID="1000", PGID="1000",
                       IMAGE="app@sha256:accepted", BROWSER_IMAGE="browser@sha256:accepted")
            env.pop("XORDER_TEST_FAILURE_HOOK", None)
            events = [
                {"event": "begin", "projects": [{"name": "chromium", "base_url": "https://resolved.test:444"}],
                 "demo_url": "https://localhost", "selected_test_count": 2},
                {"event": "test_begin", "id": "actual", "retry": 0, "title": "actual test", "location": {"file": "actual.spec.ts"}},
                {"event": "test_end", "id": "actual", "retry": 0, "title": "actual test", "status": "failed",
                 "location": {"file": "actual.spec.ts"}},
                {"event": "end", "status": "failed"}]
            text = "\n".join(json.dumps(event) for event in events)
            commands = []
            real_popen = subprocess.Popen
            def execute(command, **kwargs):
                commands.append(command)
                return real_popen([sys.executable, "-c", "print('original test output'); raise SystemExit(17)"], **kwargs)
            def observe(command, _env):
                commands.append(command)
                if "cat" in command:
                    return text
                if "logs" in command:
                    return "server same window\n"
                return json.dumps({"demo_url": "https://localhost", "cwd": "/app", "extension_reporter": None})
            with patch.object(receipts, "stack_snapshot", return_value={"configuration_sha256": "a", "containers": []}), \
                    patch.object(receipts, "observe", side_effect=observe), \
                    patch.object(receipts.subprocess, "Popen", side_effect=execute):
                self.assertEqual(receipts.run_test(["docker", "compose"], env, workspace, "stack", ["requested.spec.ts"], workers=2), 17)
                first_path = next((Path(directory) / "cache/xorder/test-attempts").glob("*/receipt.json"))
                first_bytes = first_path.read_bytes()
                first = json.loads(first_bytes)
                source.write_text("test bytes changed\n")
                self.assertEqual(receipts.run_test(["docker", "compose"], env, workspace, "stack", ["requested.spec.ts"], workers=2), 17)
            all_paths = list((Path(directory) / "cache/xorder/test-attempts").glob("*/receipt.json"))
            self.assertEqual(len(all_paths), 2)
            second = json.loads(next(path for path in all_paths if path != first_path).read_text())
            self.assertEqual(first_path.read_bytes(), first_bytes)
            self.assertNotEqual(first["run_id"], second["run_id"])
            self.assertNotEqual(first["input_sha256"], second["input_sha256"])
            self.assertEqual(first["observed_test_attempts"][0]["location"]["file"], "actual.spec.ts")
            self.assertEqual(first["requested_arguments"], ["requested.spec.ts"])
            self.assertEqual(first["effective_arguments"], ["--workers=2", "requested.spec.ts"])
            self.assertEqual(first["resolved_projects"][0]["base_url"], "https://resolved.test:444")
            self.assertEqual(first["actual_navigation_urls"]["status"], "unknown")
            self.assertIn("original test output", first["diagnostic_context"]["test_output"])
            self.assertIn("original test output", Path(first["artifacts"]["test_output"]).read_text())
            self.assertTrue(any("npm_config_update_notifier=false" in command for command in commands))
            self.assertIn("server same window", first["diagnostic_context"]["server_logs"])
            self.assertIn("host_start", first)
            self.assertIn("host_end", first)
            log_command = next(command for command in commands if "logs" in command)
            self.assertIn(first["started_at"], log_command)
            self.assertIn(first["ended_at"], log_command)

    def test_selected_tests_are_never_fabricated_as_executed_and_partial_run_stays_partial(self):
        self.assertEqual(receipts.evidence([{"event": "begin", "selected_test_count": 100}])["observed_test_attempts"], [])
        facts = receipts.evidence([{"event": "test_begin", "id": "one", "retry": 0}])
        self.assertEqual(facts["observer_status"], "incomplete")
        self.assertEqual(facts["observed_test_attempts"][0]["status"], "interrupted_or_unknown")
        with self.assertRaises(ValueError):
            receipts.parse_events('[]')

    def test_receipt_cannot_be_reassigned_and_context_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            receipts.write_once(path, {"exit_code": 1})
            with self.assertRaises(FileExistsError):
                receipts.write_once(path, {"exit_code": 0})
            output = Path(directory) / "output.log"
            output.write_text("x" * (receipts.LIMIT * 2))
            self.assertEqual(len(receipts.tail(output)), receipts.LIMIT)

    def test_trace_observations_ignore_requested_goto_arguments(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("test.trace", json.dumps({"type": "before", "apiName": "page.goto", "params": {"url": "https://never-observed.test"}}) + "\n" +
                             json.dumps({"type": "frame-snapshot", "snapshot": {"frameUrl": "https://actually-observed.test/frame"}}))
            archive.writestr("test.network", json.dumps({"type": "resource-snapshot", "snapshot": {"request": {"url": "https://actually-observed.test/request"}}}))
        facts = receipts.trace_urls(content.getvalue())
        self.assertEqual(facts, {"request_urls": ["https://actually-observed.test/request"], "frame_urls": ["https://actually-observed.test/frame"]})
        with self.assertRaises(ValueError):
            receipts.run_test([], {"XORDER_TEST_ATTEST_SERVER": "1"}, Path("."), "stack", ["--trace=off"])

    def test_full_disk_reporting_failure_keeps_test_exit_and_unconfirmed_cancel_blocks_plant_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            env = dict(os.environ, XDG_CACHE_HOME=directory, PUID="1000", PGID="1000")
            env.pop("XORDER_TEST_ATTEST_SERVER", None)
            real_popen = subprocess.Popen
            with patch.object(receipts, "stack_snapshot", return_value={}), \
                    patch.object(receipts, "observe", return_value='{"extension_reporter":null}'), \
                    patch.object(receipts, "finalize_attempt", side_effect=OSError("full disk")), \
                    patch.object(receipts.subprocess, "Popen", side_effect=lambda command, **kwargs: real_popen([sys.executable, "-c", "raise SystemExit(17)"], **kwargs)):
                self.assertEqual(receipts.run_test([], env, workspace, "stack", []), 17)
            def observe(command, _env):
                if "--stop" in command:
                    raise ValueError("stop could not be confirmed")
                return '{"extension_reporter":null}'
            with patch.object(receipts, "stack_snapshot", return_value={}), \
                    patch.object(receipts, "observe", side_effect=observe), \
                    patch.object(receipts, "finalize_attempt", side_effect=OSError("full disk")), \
                    patch.object(receipts.subprocess, "Popen", side_effect=KeyboardInterrupt), \
                    self.assertRaises(receipts.UnsafeTestCancellation) as raised:
                receipts.run_test([], env, workspace, "stack", [])
            self.assertFalse(raised.exception.plant_cleanup_safe)
            self.assertEqual(raised.exception.returncode, 130)

    def test_launcher_stops_the_container_payload_before_cleanup(self):
        if not Path("/proc/self/stat").exists():
            self.skipTest("Linux process-group lifecycle test")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            npx = workspace / "npx"
            npx.write_text("#!/usr/bin/env node\nsetInterval(()=>{},1000);\n")
            npx.chmod(0o755)
            control = workspace / "control"
            env = dict(os.environ, PATH=str(workspace) + os.pathsep + os.environ["PATH"], XORDER_TEST_CONTROL_DIR=str(control))
            launcher = ROOT / "examples/flowbite-xor/receipt-launcher.cjs"
            process = subprocess.Popen(["node", str(launcher), "one.spec.ts"], env=env)
            try:
                deadline = time.monotonic() + 5
                while not (control / "process.json").exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue((control / "process.json").exists())
                identity = json.loads((control / "process.json").read_text())
                if identity["start_time"] is None:
                    self.skipTest("Installed Node executes in a separate runtime PID namespace; direct /proc attestation unavailable")
                child = identity["pid"]
                stopped = subprocess.run(["node", str(launcher), "--stop", str(control)], env=env, timeout=15)
                self.assertEqual(stopped.returncode, 0)
                self.assertEqual(process.wait(timeout=5), 143)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)


class ActualPlaywrightReporterTests(unittest.TestCase):
    def test_real_suite_reports_observed_results_and_preserves_project_reporter(self):
        modules = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE_MODULES")
        package = Path(modules or "/nonexistent") / "playwright"
        if not (package / "cli.js").is_file():
            self.skipTest("Optional installed Playwright runtime is unavailable; CI still runs receipt/runner protocol tests")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            own_report = workspace / "original-report.json"
            events = workspace / "events.jsonl"
            (workspace / "own-reporter.cjs").write_text("const fs=require('fs');module.exports=class {onEnd(result){fs.writeFileSync(process.env.ORIGINAL_REPORT,JSON.stringify(result));}printsToStdio(){return false;}}")
            test_module = json.dumps(str(package / "test.js"))
            (workspace / "sample.spec.cjs").write_text(f"const {{test,expect}}=require({test_module});test('actually passed',()=>expect(1).toBe(1));test.skip('actually skipped',()=>{{throw Error('skip must not run')}});")
            (workspace / "playwright.config.cjs").write_text("module.exports={testMatch:'*.spec.cjs',reporter:[['./own-reporter.cjs']],projects:[{name:'one',use:{baseURL:'https://resolved.test:444'}},{name:'two',use:{baseURL:'http://other.test:4321'}}]};")
            env = dict(os.environ, PW_TEST_REPORTER=str(ROOT / "examples/flowbite-xor/receipt-reporter.cjs"),
                       XORDER_TEST_EVENT_FILE=str(events), ORIGINAL_REPORT=str(own_report), DEMO_URL="https://localhost")
            completed = subprocess.run(["node", str(package / "cli.js"), "test", "--workers=1"], cwd=workspace, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=45)
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(json.loads(own_report.read_text())["status"], "passed")
            facts = receipts.evidence(receipts.parse_events(events.read_text()))
            self.assertEqual(facts["observer_status"], "complete")
            self.assertEqual(facts["selected_test_count"], 4)
            self.assertEqual({item["base_url"] for item in facts["resolved_projects"]},
                             {"https://resolved.test:444", "http://other.test:4321"})
            self.assertEqual({item["status"] for item in facts["observed_test_attempts"]}, {"passed", "skipped"})
            self.assertTrue(all(item["location"]["file"].endswith("sample.spec.cjs") for item in facts["observed_test_attempts"]))

    def test_real_api_request_trace_establishes_the_url_actually_served(self):
        package = Path(os.environ.get("CODEX_PRIMARY_RUNTIME_NODE_MODULES", "/nonexistent")) / "playwright"
        if not (package / "cli.js").is_file():
            self.skipTest("Optional installed Playwright runtime unavailable")
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"attested")
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                base_url = "http://127.0.0.1:" + str(server.server_port)
                events = workspace / "events.jsonl"
                test_module = json.dumps(str(package / "test.js"))
                (workspace / "sample.spec.cjs").write_text(f"const {{test,expect}}=require({test_module});test('actual network',async ({{request}})=>{{const response=await request.get('/attested');expect(response.status()).toBe(200);}});")
                (workspace / "playwright.config.cjs").write_text("module.exports={testMatch:'*.spec.cjs',reporter:'null',use:{baseURL:" + json.dumps(base_url) + "}};")
                env = dict(os.environ, PW_TEST_REPORTER=str(ROOT / "examples/flowbite-xor/receipt-reporter.cjs"), XORDER_TEST_EVENT_FILE=str(events))
                completed = subprocess.run(["node", str(package / "cli.js"), "test", "--trace=on", "--workers=1"], cwd=workspace, env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=45)
                self.assertEqual(completed.returncode, 0, completed.stdout)
                facts = receipts.evidence(receipts.parse_events(events.read_text()))
                traces = [item for attempt in facts["observed_test_attempts"] for item in attempt["trace_attachments"]]
                self.assertTrue(traces, completed.stdout)
                urls = [url for attachment in traces for url in receipts.trace_urls(Path(attachment["path"]).read_bytes())["request_urls"]]
                self.assertIn(base_url + "/attested", urls)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
