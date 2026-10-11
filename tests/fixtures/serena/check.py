#!/usr/bin/env python3
"""Exercise the public offline MCP runner on a disposable, pinned uxor checkout."""
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class Client:
    def __init__(self, command, log):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=log, text=True, bufsize=1)
        self.responses = queue.Queue()
        self.serial = 0
        def receive():
            for line in self.process.stdout:
                try:
                    self.responses.put(json.loads(line))
                except ValueError:
                    self.responses.put({"invalid_stdout": line})
            self.responses.put({"eof": True})
        threading.Thread(target=receive, daemon=True).start()
        try:
            self.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "xorder-serena-acceptance", "version": "1.0.0"}})
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            instructions = self.call("tools/call", {"name": "initial_instructions", "arguments": {}})
            assert not instructions.get("isError"), instructions
            text = "\n".join(item["text"] for item in instructions.get("content", []) if item["type"] == "text")
            session = re.search(r"Your Serena session id is `([^`]+)`", text)
            assert session, "Serena did not issue a session id"
            self.session = session.group(1)
        except BaseException:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def call(self, method, params=None):
        self.serial += 1
        self.send({"jsonrpc": "2.0", "id": self.serial, "method": method, "params": params or {}})
        deadline = time.monotonic() + 120
        while True:
            reply = self.responses.get(timeout=max(0, deadline - time.monotonic()))
            if "invalid_stdout" in reply or "eof" in reply:
                raise AssertionError(reply)
            if reply.get("id") == self.serial:
                if "error" in reply:
                    raise AssertionError(reply)
                return reply["result"]

    def repl(self, code, expected_error=False):
        reply = self.call("tools/call", {"name": "serena_repl", "arguments": {"session": self.session, "code": code}})
        text = "\n".join(item["text"] for item in reply.get("content", []) if item["type"] == "text")
        if not expected_error:
            assert not reply.get("isError"), reply
            # Serena can encode execution errors inside a successful MCP reply.
            assert not re.match(r"^(?:[\w.]*Error|[\w.]*Exception):", text), text
        return text

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    image = sys.argv[1]
    fixture = json.loads(Path(__file__).with_name("consumer.json").read_text())
    with tempfile.TemporaryDirectory(prefix="xorder-serena-proof-") as directory:
        checkout = Path(directory) / "uxor"
        run("git", "init", "-q", str(checkout))
        run("git", "-C", str(checkout), "fetch", "--depth=1", fixture["repository"], fixture["commit"])
        run("git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD")
        # Install the application's own lock, separately from the image's LSP.
        # No asset downloads, application scripts, browser, or server are needed.
        run("docker", "run", "--rm", "--mount", f"type=bind,src={checkout},dst=/workspace",
            "-e", f"PUID={os.getuid()}", "-e", f"PGID={os.getgid()}",
            "-w", "/workspace/demo", image, "composer", "install", "--no-interaction", "--prefer-dist",
            "--no-progress", "--no-scripts", "--no-plugins")
        command = [sys.executable, str(ROOT / "examples/serena/run.py"), str(checkout),
                   "--image", image, "--project", fixture["project"], "--request-timeout", "180",
                   "--cache-dir", str(Path(directory) / "index-cache")]
        source = checkout / fixture["project"] / fixture["file"]
        original = source.read_text()
        settings = checkout / fixture["project"] / ".serena/project.yml"
        settings.parent.mkdir()
        settings.write_text(json.dumps({
            "activation_command": "touch /workspace/xorder-activation-canary",
            "ls_specific_settings": {"php_phpactor": {"ignore_vendor": False}},
        }))
        original_settings = settings.read_bytes()
        evidence = {"consumer": fixture, "image": image, "checks": []}
        log_path = Path(directory) / "mcp.log"
        client = None
        try:
            with log_path.open("w") as log:
                # The first session must be read-only, with no earlier writable
                # session available to answer PHPactor's configuration prompts.
                assert not (checkout / fixture["project"] / ".phpactor.json").exists()
                client = Client(command, log)
                fresh = client.repl("s.lsp.find_symbol('LabController', relative_path='src/Controller/LabController.php', include_body=True)")
                assert "LabController" in fresh, fresh
                client.repl("s.lsp.find_referencing_symbols('LabController', 'src/Controller/LabController.php')")
                assert "CspNonce" in client.repl(f"s.lsp.find_symbol({fixture['symbol']!r}, relative_path={fixture['file']!r})")
                assert not (checkout / fixture["project"] / ".phpactor.json").exists()
                evidence["checks"].append("clean-first-readonly-symbols-references-server-remains-alive")
                instructions = client.call("tools/call", {"name": "initial_instructions", "arguments": {}})
                assert instructions["structuredContent"]["session_id"]
                evidence["checks"].append("structured-session-identity")
                client.close()
                client = Client(command + ["--write"], log)
                assert "serena_repl" in {tool["name"] for tool in client.call("tools/list")["tools"]}
                assert "42" in client.repl("xorder_answer = 42; xorder_answer")
                assert "42" in client.repl("xorder_answer")
                evidence["checks"].append("persistent-repl-state")
                overview = client.repl(f"s.lsp.get_symbols_overview({fixture['file']!r}, depth=1)")
                assert fixture["symbol"] in overview and "__toString" in overview, overview
                found = client.repl(f"s.lsp.find_symbol({fixture['symbol']!r}, relative_path={fixture['file']!r}, include_body=True)")
                assert "RequestStack" in found, found
                references = client.repl(f"s.lsp.find_referencing_symbols({fixture['symbol']!r}, {fixture['file']!r})")
                assert fixture["referencing_file"] in references, references
                evidence["checks"].append("php-symbols-and-cross-file-references")
                assert source.read_text() == original
                assert not (checkout / "xorder-activation-canary").exists(), "Startup executed project configuration"
                assert settings.read_bytes() == original_settings
                assert list(settings.parent.iterdir()) == [settings], "Startup wrote project state into the checkout"
                evidence["checks"].append("untrusted-project-configuration-cannot-execute-on-activation")
                client.repl(f"s.edit.replace_content({fixture['file']!r}, \"return '';\", \"return 'xorder-proof';\", 'literal')")
                assert "return 'xorder-proof';" in source.read_text()
                reread = client.repl(f"s.lsp.find_symbol('CspNonce/__toString', relative_path={fixture['file']!r}, include_body=True)")
                assert "xorder-proof" in reread, reread
                error = client.repl(f"s.edit.replace_content({fixture['file']!r}, 'xorder-proof', 'xorder-partial', 'literal')\nraise RuntimeError('xorder-expected-error')", expected_error=True)
                assert "xorder-expected-error" in error, error
                assert "xorder-partial" in source.read_text(), "Edit before error was lost"
                evidence["checks"].append("edit-read-and-partial-error")
                client.close()
                client = Client(command, log)  # the public runner defaults to a read-only mount
                assert "False" in client.repl("'xorder_answer' in globals()")
                assert "xorder-partial" in client.repl(f"s.lsp.find_symbol('CspNonce/__toString', relative_path={fixture['file']!r}, include_body=True)")
                blocked = client.repl("from pathlib import Path\nblocked = False\ntry:\n Path('/workspace/demo/src/Security/CspNonce.php').write_text('wrong')\nexcept OSError:\n blocked = True\nblocked")
                assert "True" in blocked, blocked
                assert "xorder-partial" in source.read_text()
                evidence["checks"].append("restart-loses-repl-state-preserves-source-and-readonly-mount")
                client.close()
                client = None
                # Exercise the shell entry point against the same prepared
                # service, including source changes made without MCP registration.
                cli = [sys.executable, str(ROOT / "examples/serena/client.py"), "query",
                       "--workspace", str(checkout), "--project", fixture["project"], "--image", image,
                       "--cache-dir", str(Path(directory) / "index-cache"), "--write"]
                reply = run(*cli, "--code", f"s.edit.replace_content({fixture['file']!r}, 'xorder-partial', 'xorder-shell', 'literal')",
                            capture_output=True, text=True)
                assert json.loads(reply.stdout)["ok"], reply.stdout
                assert "xorder-shell" in source.read_text()
                evidence["checks"].append("shell-query-trusted-source-edit")
                # Recipe-generated controllers are intentionally gitignored by
                # this consumer; exercise source files eligible for navigation.
                js = checkout / fixture["project"] / "assets/xorder_navigation.js"
                usage = js.with_name("xorder_usage.js")
                js.write_text("export class XorderNavigation { navigate() { return 42; } }\n")
                usage.write_text("import { XorderNavigation } from './xorder_navigation.js';\nexport const xorderResult = new XorderNavigation().navigate();\n")
                client = Client(command + ["--write", "--languages", "php_phpactor,typescript"], log)
                symbols = client.repl("s.lsp.get_symbols_overview('assets/xorder_navigation.js', depth=1)")
                assert "XorderNavigation" in symbols and "navigate" in symbols, symbols
                refs = client.repl("s.lsp.find_referencing_symbols('XorderNavigation', 'assets/xorder_navigation.js')")
                assert "xorder_usage.js" in refs, refs
                client.repl("s.edit.replace_content('assets/xorder_navigation.js', 'return 42', 'return 43', 'literal')")
                assert "return 43" in js.read_text()
                evidence["checks"].append("javascript-symbols-cross-file-references-and-edit")
                client.close()
                client = None
                js.unlink(); usage.unlink()
        except BaseException:
            print(log_path.read_text()[-16000:], file=sys.stderr)
            raise
        finally:
            if client:
                client.close()
        source.write_text(original)
        settings.unlink()
        settings.parent.rmdir()
        run("git", "-C", str(checkout), "diff", "--exit-code")
        output = ROOT / "out/serena"
        output.mkdir(parents=True, exist_ok=True)
        (output / "acceptance.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence))


if __name__ == "__main__":
    main()
