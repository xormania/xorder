"""Project-owned, optional advisory commands receive one immutable run receipt."""
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

MAX_RECEIPT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_bounded(argv, payload, env, timeout):
    """Multiplex input and output without spooling unlimited hook bytes to disk."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=env, cwd=env.get("WORKSPACE"),
                               start_new_session=True)
    deadline = time.monotonic() + timeout
    tail, total, offset = bytearray(), 0, 0
    descendants_stopped = False
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdin, process.stdout):
                os.set_blocking(stream.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                if process.poll() is not None and not descendants_stopped:
                    # A completed hook must not leave descendants holding its
                    # stdout open or consuming the run's host/disk budget.
                    _kill_group(process)
                    descendants_stopped = True
                for key, events in selector.select(min(remaining, 0.1)):
                    stream = key.fileobj
                    if stream is process.stdin:
                        try:
                            offset += os.write(stream.fileno(), payload[offset:offset + 65536])
                        except BrokenPipeError:
                            offset = len(payload)
                        except BlockingIOError:
                            continue
                        if offset == len(payload):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        try:
                            content = os.read(stream.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not content:
                            selector.unregister(stream)
                            stream.close()
                        else:
                            total += len(content)
                            tail.extend(content)
                            if len(tail) > MAX_OUTPUT_BYTES:
                                del tail[:-MAX_OUTPUT_BYTES]
        returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
        return returncode, bytes(tail), total
    finally:
        # subprocess.run only kills its immediate child on timeout. The new
        # session gives this runner one complete hook group to stop and reap.
        try:
            _kill_group(process)
            process.wait(timeout=5)
        finally:
            for stream in (process.stdin, process.stdout):
                if not stream.closed:
                    stream.close()


def run_failure_hook(receipt_path, env):
    """Return advisory status; a hook cannot replace the failed test's exit code."""
    command = env.get("XORDER_TEST_FAILURE_HOOK")
    if not command:
        return {"status": "disabled"}
    try:
        argv = json.loads(command)
        if not isinstance(argv, list) or not argv or not argv[0] or any(
                not isinstance(arg, str) or "\0" in arg for arg in argv):
            return {"status": "invalid", "reason": "XORDER_TEST_FAILURE_HOOK must be a JSON argument array"}
        timeout = float(env.get("XORDER_TEST_FAILURE_HOOK_TIMEOUT", "30"))
        if not math.isfinite(timeout) or not 1 <= timeout <= 300:
            return {"status": "invalid", "reason": "Failure hook timeout must be between 1 and 300 seconds"}
        with Path(receipt_path).open("rb") as source:
            receipt_bytes = source.read(MAX_RECEIPT_BYTES + 1)
        if len(receipt_bytes) > MAX_RECEIPT_BYTES:
            return {"status": "invalid", "reason": "Run receipt exceeds the 1 MiB hook input limit"}
        receipt = json.loads(receipt_bytes)
        if not isinstance(receipt, dict):
            return {"status": "invalid", "reason": "Run receipt must be a JSON object"}
        returncode, output, length = _run_bounded(argv, json.dumps(receipt).encode(), env, timeout)
        text = output.decode("utf-8", errors="replace").strip()
        if returncode:
            return {"status": "failed", "exit_code": returncode}
        try:
            advisory = json.loads(text)
        except ValueError:
            advisory = text
        return {"status": "passed", "output": advisory,
                "output_truncated": length > MAX_OUTPUT_BYTES}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    except (OSError, subprocess.SubprocessError):
        return {"status": "unavailable", "reason": "Failure hook could not run or read the receipt"}
    except (ValueError, TypeError, RecursionError):
        return {"status": "invalid", "reason": "Invalid failure hook configuration or receipt JSON"}
