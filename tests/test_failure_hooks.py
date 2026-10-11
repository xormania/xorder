import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("failure_hooks", ROOT / "examples/shared/failure_hooks.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)


class FailureHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.receipt = self.root / "receipt.json"
        self.data = {"exit_code": 7, "diagnostic_context": {"test_output": "assertion failed", "server_logs": "request 500"}}
        self.receipt.write_text(json.dumps(self.data))
        self.env = dict(os.environ, WORKSPACE=str(self.root))

    def test_opt_in_receives_exact_receipt_with_literal_arguments(self):
        planted = self.root / "must-not-exist"
        argument = "$(touch " + str(planted) + ")"
        program = "import json,os,sys; print(json.dumps({'receipt':json.load(sys.stdin),'arg':sys.argv[1],'cwd':os.getcwd()}))"
        self.env["XORDER_TEST_FAILURE_HOOK"] = json.dumps([sys.executable, "-c", program, argument])
        before = self.receipt.read_bytes()
        result = hooks.run_failure_hook(self.receipt, self.env)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["output"], {"receipt": self.data, "arg": argument, "cwd": str(self.root)})
        self.assertFalse(planted.exists())
        self.assertEqual(self.receipt.read_bytes(), before)

    def test_disabled_invalid_failed_unavailable_and_timeout_are_advisory(self):
        with patch.object(hooks, "_run_bounded") as run:
            self.assertEqual(hooks.run_failure_hook(self.receipt, self.env), {"status": "disabled"})
            for value in ("not JSON", '"shell command"', "[]", '[1]'):
                self.env["XORDER_TEST_FAILURE_HOOK"] = value
                self.assertEqual(hooks.run_failure_hook(self.receipt, self.env)["status"], "invalid")
            run.assert_not_called()
            self.env["XORDER_TEST_FAILURE_HOOK"] = '["fixture"]'
            for timeout in ("nan", "0", "301"):
                self.env["XORDER_TEST_FAILURE_HOOK_TIMEOUT"] = timeout
                self.assertEqual(hooks.run_failure_hook(self.receipt, self.env)["status"], "invalid")
            self.env.pop("XORDER_TEST_FAILURE_HOOK_TIMEOUT")
            run.return_value = (99, b"", 0)
            self.assertEqual(hooks.run_failure_hook(self.receipt, self.env), {"status": "failed", "exit_code": 99})
            run.side_effect = OSError("sensitive diagnostic")
            self.assertEqual(hooks.run_failure_hook(self.receipt, self.env)["status"], "unavailable")
            run.side_effect = subprocess.TimeoutExpired(["fixture"], 30)
            self.assertEqual(hooks.run_failure_hook(self.receipt, self.env), {"status": "timeout"})

    def test_output_tail_is_bounded_and_input_size_is_checked(self):
        self.env["XORDER_TEST_FAILURE_HOOK"] = json.dumps([sys.executable, "-c", "print('x' * 20000)"])
        result = hooks.run_failure_hook(self.receipt, self.env)
        self.assertTrue(result["output_truncated"])
        self.assertLessEqual(len(result["output"].encode()), hooks.MAX_OUTPUT_BYTES)
        self.receipt.write_bytes(b"x" * (hooks.MAX_RECEIPT_BYTES + 1))
        with patch.object(hooks, "_run_bounded") as run:
            self.assertEqual(hooks.run_failure_hook(self.receipt, self.env)["status"], "invalid")
            run.assert_not_called()

    def test_large_input_and_concurrent_output_cannot_deadlock_or_grow_capture(self):
        self.receipt.write_text(json.dumps({"exit_code": 7, "test_output": "x" * 900000}))
        # Write before reading stdin: a blocking input write would deadlock
        # against this output, even though the receipt fits its public limit.
        program = ("import json,sys; sys.stdout.write('y'*200000); sys.stdout.flush(); "
                   "value=json.load(sys.stdin); print('RECEIVED:'+str(value['exit_code']))")
        self.env["XORDER_TEST_FAILURE_HOOK"] = json.dumps([sys.executable, "-c", program])
        self.env["XORDER_TEST_FAILURE_HOOK_TIMEOUT"] = "5"
        result = hooks.run_failure_hook(self.receipt, self.env)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["output_truncated"])
        self.assertLessEqual(len(result["output"].encode()), hooks.MAX_OUTPUT_BYTES)
        self.assertTrue(result["output"].endswith("RECEIVED:7"))

    def test_timeout_stops_descendants_and_original_receipt_survives(self):
        pidfile = self.root / "child.pid"
        child = "import time; time.sleep(30)"
        program = ("import subprocess,sys,time; from pathlib import Path; "
                   "child=subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); "
                   "Path(" + repr(str(pidfile)) + ").write_text(str(child.pid)); time.sleep(30)")
        self.env["XORDER_TEST_FAILURE_HOOK"] = json.dumps([sys.executable, "-c", program])
        self.env["XORDER_TEST_FAILURE_HOOK_TIMEOUT"] = "1"
        before = self.receipt.read_bytes()
        result = hooks.run_failure_hook(self.receipt, self.env)
        self.assertEqual(result, {"status": "timeout"})
        self.assertEqual(self.receipt.read_bytes(), before)
        pid = int(pidfile.read_text())
        stat = Path(f"/proc/{pid}/stat")
        # A killed orphan may briefly be a zombie until its adopter reaps it;
        # it must not remain a runnable/sleeping advisory worker.
        try:
            contents = stat.read_text()
        except FileNotFoundError:
            pass  # Already reaped; the process is gone.
        else:
            self.assertIn(contents.split(") ", 1)[1].split()[0], ("Z", "X"))

    def test_successful_hook_cannot_leave_background_output_writer(self):
        pidfile = self.root / "child.pid"
        program = ("import subprocess,sys,json; from pathlib import Path; "
                   "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                   "Path(" + repr(str(pidfile)) + ").write_text(str(child.pid)); print(json.dumps({'advice':'inspect failure'}))")
        self.env["XORDER_TEST_FAILURE_HOOK"] = json.dumps([sys.executable, "-c", program])
        self.env["XORDER_TEST_FAILURE_HOOK_TIMEOUT"] = "2"
        result = hooks.run_failure_hook(self.receipt, self.env)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["output"], {"advice": "inspect failure"})
        stat = Path(f"/proc/{int(pidfile.read_text())}/stat")
        try:
            contents = stat.read_text()
        except FileNotFoundError:
            pass  # Already reaped; the process is gone.
        else:
            self.assertIn(contents.split(") ", 1)[1].split()[0], ("Z", "X"))
