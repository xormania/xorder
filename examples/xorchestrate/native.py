#!/usr/bin/env python3
"""Observe native terminal communication and cleanup in a private runtime scope."""

import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time
import tty


def observe(tmux):
    deadline = time.monotonic() + 12
    evidence = {"status": "failed", "uid": os.geteuid(), "gid": os.getegid(),
                "pty": "not_executed", "unix_socket": "not_executed", "proc": "not_executed",
                "terminal_communication": "not_executed", "cleanup": "not_executed"}
    environment = dict(os.environ, ENV="", BASH_ENV="", PS1="", PS2="", TERM="xterm-256color")
    environment.pop("TMUX", None)
    environment.pop("TMUX_PANE", None)
    server, pane_pid, private = None, None, None

    def run(arguments, *, cleanup=False):
        remaining = 3 if cleanup else min(3, deadline - time.monotonic())
        if remaining <= 0:
            raise TimeoutError("Native communication observation exceeded its time budget")
        return subprocess.run([tmux, *arguments], env=environment, check=True,
                              capture_output=True, text=True, timeout=remaining).stdout

    try:
        evidence["tmux_version"] = run(["-V"]).strip()[:120]
        # Random private 0700 directory; short path stays below the Unix-socket limit.
        with tempfile.TemporaryDirectory(prefix="xorder-native-", dir="/tmp") as directory:  # nosec B108
            private = Path(directory)
            tmux_socket = private / "tmux.sock"
            try:
                master, slave = os.openpty()
                try:
                    tty.setraw(slave)
                    os.write(master, b"xorder-pty-ok\n")
                    if not select.select([slave], [], [], 2)[0] or os.read(slave, 128) != b"xorder-pty-ok\n":
                        raise ValueError("Private PTY did not transfer the expected bytes")
                    os.write(slave, b"xorder-pty-reply\n")
                    if not select.select([master], [], [], 2)[0] or os.read(master, 128) != b"xorder-pty-reply\n":
                        raise ValueError("Private PTY reply did not arrive")
                    evidence["pty"] = "passed"
                finally:
                    os.close(slave)
                    os.close(master)
                with socket.socket(socket.AF_UNIX) as listener, socket.socket(socket.AF_UNIX) as client:
                    listener.settimeout(2)
                    client.settimeout(2)
                    listener.bind(str(private / "socket.sock"))
                    listener.listen(1)
                    client.connect(str(private / "socket.sock"))
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        client.sendall(b"xorder-socket-ok")
                        if connection.recv(128) != b"xorder-socket-ok":
                            raise ValueError("Private Unix socket did not transfer the expected bytes")
                        connection.sendall(b"xorder-socket-reply")
                        if client.recv(128) != b"xorder-socket-reply":
                            raise ValueError("Private Unix socket reply did not arrive")
                    evidence["unix_socket"] = "passed"
                # Foreground server stays in the outer command's owned process group.
                server = subprocess.Popen([tmux, "-D", "-f", "/dev/null", "-S", str(tmux_socket)],
                                          env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                until = min(deadline, time.monotonic() + 3)
                while not tmux_socket.exists():
                    if server.poll() is not None or time.monotonic() >= until:
                        raise ValueError("Private foreground tmux server did not become available")
                    time.sleep(0.02)
                prefix = ["-S", str(tmux_socket)]
                run([*prefix, "new-session", "-d", "-s", "xorder-native", "-x", "80", "-y", "24", "/bin/sh"])
                target = "xorder-native:0.0"
                pane_pid = int(run([*prefix, "display-message", "-p", "-t", target, "#{pane_pid}"]).strip())
                if pane_pid <= 1 or not all((Path("/proc") / str(pid) / "stat").is_file()
                                            for pid in (os.getpid(), server.pid, pane_pid)):
                    raise ValueError("Private tmux processes are not visible through /proc")
                evidence.update(proc="passed", server_pid=server.pid, pane_pid=pane_pid)
                run([*prefix, "send-keys", "-t", target, "-l", "printf 'xorder-terminal-ok\\n'"])
                run([*prefix, "send-keys", "-t", target, "Enter"])
                until = min(deadline, time.monotonic() + 3)
                while "xorder-terminal-ok" not in run([*prefix, "capture-pane", "-p", "-t", target]).splitlines():
                    if time.monotonic() >= until:
                        raise ValueError("Private tmux session did not return the expected terminal output")
                    time.sleep(0.02)
                evidence["terminal_communication"] = "passed"
            finally:
                if server is not None:
                    try:
                        run(["-S", str(tmux_socket), "kill-server"], cleanup=True)
                    except (OSError, subprocess.SubprocessError):
                        server.terminate()
                    try:
                        server.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=1)
                    finally:
                        server.stderr.close()
                    # tmux may retain its socket pathname after the server exits.
                    # Remove only this probe's private, no-longer-served endpoint.
                    tmux_socket.unlink(missing_ok=True)
                    until = time.monotonic() + 1
                    while pane_pid and (Path("/proc") / str(pane_pid)).exists() and time.monotonic() < until:
                        time.sleep(0.02)
                    if tmux_socket.exists() or (pane_pid and (Path("/proc") / str(pane_pid)).exists()):
                        raise ValueError("Private tmux session/server cleanup could not be verified")
        evidence["cleanup"] = "passed"
        evidence["status"] = "passed"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        evidence["reason"] = str(error)
    finally:
        if (private is not None and not private.exists()
                and (server is None or server.poll() is not None)
                and (pane_pid is None or not (Path("/proc") / str(pane_pid)).exists())):
            evidence["cleanup"] = "passed"
    return evidence


if __name__ == "__main__":
    os.umask(0o077)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python native.py /path/to/tmux")
    result = observe(sys.argv[1])
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "passed" else 1)
