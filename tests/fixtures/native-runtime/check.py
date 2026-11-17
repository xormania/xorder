#!/usr/bin/env python3
"""Prove image-owned Linux terminal, socket and tmux capabilities."""
import json
import os
from pathlib import Path
import select
import shlex
import socket
import subprocess
import tempfile
import time
import tty


def command(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=15)


def proc_check():
    status = Path("/proc/self/status").read_text()
    pid = next(line.split()[1] for line in status.splitlines() if line.startswith("Pid:"))
    if int(pid) != os.getpid():
        raise RuntimeError("/proc/self/status did not identify the current process")
    return {"self_status": True}


def mounts_check():
    result = {}
    for path in ("/workspace", "/home/dev"):
        with tempfile.NamedTemporaryFile(mode="w+", prefix=".xorder-proof-", dir=path) as stream:
            stream.write("xorder-mount-proof")
            stream.flush()
            stream.seek(0)
            if stream.read() != "xorder-mount-proof" or os.fstat(stream.fileno()).st_uid != os.getuid():
                raise RuntimeError("Runtime mount did not preserve configured-user writes: " + path)
        result[path] = {"read_write": True, "uid": os.getuid()}
    return result


def pty_check():
    master, slave = os.openpty()
    try:
        tty.setraw(slave)
        for source, destination, payload in ((slave, master, b"xorder-output"),
                                             (master, slave, b"xorder-input")):
            os.write(source, payload)
            received = b""
            deadline = time.monotonic() + 5
            while len(received) < len(payload):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([destination], [], [], remaining)[0]:
                    raise RuntimeError("PTY communication timed out")
                chunk = os.read(destination, len(payload) - len(received))
                if not chunk:
                    raise RuntimeError("PTY closed before receiving the payload")
                received += chunk
            if received != payload:
                raise RuntimeError("PTY communication changed the payload")
        if not os.isatty(slave):
            raise RuntimeError("PTY slave is not a terminal")
    finally:
        os.close(slave)
        os.close(master)
    return {"bidirectional": True, "terminal": True}


def socket_check():
    def receive(connection, expected):
        received = b""
        while len(received) < len(expected):
            chunk = connection.recv(len(expected) - len(received))
            if not chunk:
                raise RuntimeError("Unix socket closed before receiving the payload")
            received += chunk
        if received != expected:
            raise RuntimeError("Unix socket changed the payload")

    with tempfile.TemporaryDirectory(prefix="xo-socket-") as directory:
        address = str(Path(directory) / "proof.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.settimeout(5)
            listener.bind(address)
            listener.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(5)
                client.connect(address)
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    client.sendall(b"xorder-request")
                    receive(connection, b"xorder-request")
                    connection.sendall(b"xorder-response")
                    receive(client, b"xorder-response")
    return {"request_response": True}


def tmux_check():
    version = command("tmux", "-V").stdout.strip()
    if not version.startswith("tmux 3."):
        raise RuntimeError("Expected tmux 3.x, observed " + version)
    with tempfile.TemporaryDirectory(prefix="xo-tmux-") as directory:
        address = str(Path(directory) / "server.sock")
        prefix = ("tmux", "-S", address, "-f", "/dev/null")
        try:
            command(*prefix, "new-session", "-d", "-s", "proof", "-x", "100", "-y", "24",
                    "bash --noprofile --norc")
            command(*prefix, "has-session", "-t", "proof")
            # The complete output token never occurs in the submitted command;
            # an echoed input line alone cannot satisfy the pane observation.
            script = ("printf 'xorder-%s\\n' 'terminal-proof'; "
                      + shlex.join(prefix + ("wait-for", "-S", "ready")))
            command(*prefix, "send-keys", "-t", "proof:0.0", "-l", script)
            command(*prefix, "send-keys", "-t", "proof:0.0", "Enter")
            command(*prefix, "wait-for", "ready")
            pane = command(*prefix, "capture-pane", "-p", "-t", "proof:0.0").stdout
            if "xorder-terminal-proof" not in pane.splitlines():
                raise RuntimeError("tmux did not execute and render terminal input")
            command(*prefix, "kill-session", "-t", "proof")
            if command(*prefix, "has-session", "-t", "proof", check=False).returncode == 0:
                raise RuntimeError("tmux session survived cleanup")
        finally:
            command(*prefix, "kill-server", check=False)
    return {"version": version, "checks": ["private-socket", "create-session", "send-keys",
                                            "capture-pane", "session-cleanup"]}


def main():
    return {"mounts": mounts_check(), "proc": proc_check(), "pty": pty_check(), "unix_socket": socket_check(),
            "tmux": tmux_check()}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
