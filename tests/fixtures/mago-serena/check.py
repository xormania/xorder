#!/usr/bin/env python3
"""Offline acceptance for the prepared Mago/Serena and owned Chrome toolchains."""
import argparse
import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path


class RpcClient:
    """Deadline-bound stdio JSON-RPC, supporting MCP lines and LSP byte framing."""

    def __init__(self, command, *, framing="lines", timeout=90, cwd=None, env=None):
        if framing not in {"lines", "lsp"}:
            raise ValueError("Unsupported JSON-RPC framing")
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.framing = framing
        self.timeout = timeout
        self.serial = 0
        self.messages = queue.Queue()
        self.log = tempfile.TemporaryFile()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log, cwd=cwd, env=env, start_new_session=True)
        self.reader = threading.Thread(target=self._receive, daemon=True)
        self.reader.start()

    def _receive(self):
        try:
            while True:
                if self.framing == "lines":
                    payload = self.process.stdout.readline()
                    if not payload:
                        break
                else:
                    headers = {}
                    while True:
                        line = self.process.stdout.readline()
                        if not line:
                            raise EOFError("EOF in LSP headers")
                        if line in {b"\r\n", b"\n"}:
                            break
                        key, separator, value = line.partition(b":")
                        if not separator:
                            raise ValueError("Invalid LSP header")
                        headers[key.lower().strip()] = value.strip()
                    length = int(headers[b"content-length"])
                    if not 0 < length <= 16 * 1024 * 1024:
                        raise ValueError("Invalid LSP message size")
                    payload = self.process.stdout.read(length)
                    if len(payload) != length:
                        raise EOFError("Truncated LSP body")
                message = json.loads(payload)
                if not isinstance(message, dict):
                    raise ValueError("JSON-RPC stdout must contain objects")
                self.messages.put(message)
        except (ValueError, KeyError, EOFError, OSError) as error:
            self.messages.put(RuntimeError(f"Invalid JSON-RPC stdout: {error}"))
        finally:
            self.messages.put(RuntimeError("JSON-RPC process reached EOF"))

    def _send(self, message):
        payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
        if self.framing == "lsp":
            payload = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload
        else:
            payload += b"\n"
        self.process.stdin.write(payload)
        self.process.stdin.flush()

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def call(self, method, params=None):
        self.serial += 1
        self._send({"jsonrpc": "2.0", "id": self.serial, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"JSON-RPC deadline exceeded for {method}")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as error:
                raise RuntimeError(f"JSON-RPC deadline exceeded for {method}") from error
            if isinstance(message, Exception):
                self.log.seek(0)
                diagnostic = self.log.read()[-16000:].decode("utf-8", errors="replace")
                raise RuntimeError(f"{message}\n{diagnostic}")
            if message.get("id") == self.serial and "method" not in message:
                if "error" in message:
                    raise RuntimeError(f"JSON-RPC error for {method}: {message['error']}")
                if "result" not in message:
                    raise RuntimeError("JSON-RPC response has no result")
                return message["result"]
            if "id" in message and "method" in message:
                # Mago uses client/registerCapability during initialize. The fixture
                # implements registration as a no-op; reject unknown server requests.
                result = {"jsonrpc": "2.0", "id": message["id"]}
                if message["method"] == "client/registerCapability":
                    result["result"] = None
                else:
                    result["error"] = {"code": -32601, "message": "Fixture method not found"}
                self._send(result)

    def close(self):
        if not self.process.stdin.closed:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=5)
        self.reader.join(timeout=1)
        self.process.stdout.close()
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mcp_initialize(client):
    result = client.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                      "clientInfo": {"name": "xorder-image-acceptance", "version": "1.0.0"}})
    assert result.get("serverInfo"), result
    client.notify("notifications/initialized")
    return result


def tool(client, name, arguments=None):
    result = client.call("tools/call", {"name": name, "arguments": arguments or {}})
    assert not result.get("isError"), result
    return result


def verify_mago(project):
    environment = dict(os.environ, MAGO_EXPERIMENTAL_SERVER="1")
    with RpcClient(["mago", "language-server"], framing="lsp", cwd=project, env=environment) as client:
        result = client.call("initialize", {
            "processId": os.getpid(), "rootUri": project.as_uri(),
            "workspaceFolders": [{"uri": project.as_uri(), "name": "acceptance"}],
            "capabilities": {"general": {"positionEncodings": ["utf-16"]},
                             "textDocument": {"documentSymbol": {"hierarchicalDocumentSymbolSupport": True}}},
        })
        assert result.get("serverInfo", {}).get("name") == "mago-server", result
        assert result["capabilities"].get("experimental", {}).get("symbolReferencesProvider") is True, result
        client.notify("initialized")
        uri = (project / "Example.php").as_uri()
        client.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "php", "version": 1, "text": (project / "Example.php").read_text()}})
        references = client.call("mago/symbolReferences", {"textDocument": {"uri": uri},
                                                          "symbol": "Example", "member": ""})
        assert isinstance(references.get("references"), list), references
        client.call("shutdown")
        client.notify("exit")


def verify_serena(project):
    with RpcClient(["serena", "start-mcp-server", "--project", str(project), "--transport", "stdio",
                    "--agent-interface", "REPL", "--enable-web-dashboard", "false",
                    "--open-web-dashboard", "false", "--enable-gui-log-window", "false"], cwd=project) as client:
        mcp_initialize(client)
        assert "initial_instructions" in {entry["name"] for entry in client.call("tools/list")["tools"]}
        instructions = tool(client, "initial_instructions")
        text = "\n".join(entry.get("text", "") for entry in instructions.get("content", []))
        session = instructions.get("structuredContent", {}).get("session_id")
        if not session:
            match = re.search(r"Your Serena session id is `([^`]+)`", text)
            assert match, instructions
            session = match.group(1)
        found = tool(client, "serena_repl", {"session": session, "code":
                     "symbols = s.lsp.find_symbol('Example', relative_path='Example.php', include_body=True)\n"
                     "assert symbols, 'Symbol query returned no matches'\n"
                     "assert 'return 42' in symbols.represent(), 'Symbol query omitted source body'\n"
                     "'XORDER_SYMBOL_OK'"})
        output = "\n".join(entry.get("text", "") for entry in found.get("content", []))
        # Serena can encode Python execution errors inside successful MCP replies.
        # Only the final expression evaluated after both assertions is a passing result.
        assert output.strip() == "XORDER_SYMBOL_OK", found


def verify_chrome(chrome_binary="/usr/local/bin/chrome", mcp_binary="chrome-devtools-mcp"):
    completed = subprocess.run([chrome_binary, "--headless=new", "--no-sandbox", "--disable-gpu",
                                "--disable-dev-shm-usage", "--dump-dom", "about:blank"],
                               capture_output=True, text=True, check=True, timeout=45)
    assert "<html" in completed.stdout.lower(), completed.stdout
    environment = dict(os.environ, CI="1")
    with RpcClient([mcp_binary, "--headless", "--isolated", "--executablePath", chrome_binary,
                    "--chromeArg=--no-sandbox", "--chromeArg=--disable-dev-shm-usage",
                    "--categoryExperimentalThirdParty"], env=environment) as client:
        mcp_initialize(client)
        names = {entry["name"] for entry in client.call("tools/list")["tools"]}
        assert {"list_pages", "list_3p_developer_tools", "execute_3p_developer_tool"} <= names, names
        pages = tool(client, "list_pages")
        assert re.search(r"\b\d+:.*(?:about:blank|https?://)", json.dumps(pages)), pages


def inside(chrome):
    assert os.getuid() == 1001 and os.getgid() == 1001, (os.getuid(), os.getgid())
    home = Path(os.environ["SERENA_HOME"])
    assert home.is_dir() and home.stat().st_uid == 1001
    assert (home / "serena_config.yml").stat().st_uid == 1001
    identity = json.loads(Path("/opt/xorder/image-identity.json").read_text())
    assert identity["mago"] == "mago 1.58.2" and identity["mago_baseline"] == "mago 1.58.2"
    assert identity["mago_binary_sha256"] == digest("/usr/local/bin/mago")
    assert identity["mago_baseline_binary_sha256"] == digest("/usr/local/bin/mago-baseline")
    assert subprocess.check_output(["python3", "--version"], text=True).strip() == "Python 3.12.12"
    subprocess.run(["/opt/venv/bin/python", "-c", "import serena_mago"], check=True)
    subprocess.run(["serena", "--version"], stdout=sys.stderr, check=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix="xorder-mago-") as temporary:
        project = Path(temporary)
        (project / "Example.php").write_text("<?php\nclass Example { public function answer(): int { return 42; } }\n")
        (project / "mago.toml").write_text('[source]\npaths = ["."]\n')
        (project / ".serena").mkdir()
        (project / ".serena/project.yml").write_text(
            "project_name: xorder-acceptance\nlanguage_servers: [mago]\nencoding: utf-8\n"
            "ignore_all_files_in_gitignore: false\nignored_paths: []\nread_only: false\n")
        verify_mago(project)
        verify_serena(project)
    if chrome:
        assert identity["chrome_binary_sha256"] == digest("/opt/chrome-linux64/chrome")
        assert "157.0.8103.38" in identity["chrome_for_testing"]
        assert identity["chrome_devtools_mcp"] == "1.12.0"
        verify_chrome()
    print(json.dumps({"status": "passed", "mapped_uid": os.getuid(), "image_identity": identity,
                      "checks": ["mapped-home-seed", "installed-binary-hashes", "mago-initialize-symbol-references",
                                 "serena-mcp-find-symbol"] + (["chrome-headless", "chrome-mcp-third-party-pages"] if chrome else [])}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?")
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--chrome", action="store_true")
    args = parser.parse_args()
    if args.inside:
        inside(args.chrome)
    elif args.image:
        root = Path(__file__).resolve().parents[3]
        evidence = root / "out" / ("chrome-dev" if args.chrome else "mago-serena")
        evidence.mkdir(parents=True, exist_ok=True)
        container = "xorder-mago-acceptance-" + uuid.uuid4().hex
        command = ["docker", "run", "--name", container, "--rm", "--network=none", "--init", "--shm-size=1g",
                   "-e", "PUID=1001", "-e", "PGID=1001", "-e", "CI=1",
                   "-v", f"{Path(__file__).resolve()}:/proof/check.py:ro", args.image,
                   "python3", "/proof/check.py", "--inside"]
        if args.chrome:
            command.append("--chrome")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=420, check=False)
        finally:
            subprocess.run(["docker", "rm", "-f", container], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        (evidence / "acceptance.stderr").write_text(result.stderr)
        if result.returncode:
            print(result.stderr[-20000:], file=sys.stderr)
            raise SystemExit(result.returncode)
        # Fail if a subprocess contaminates stdout; evidence must be one record.
        record = json.loads(result.stdout)
        (evidence / "acceptance.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2))
    else:
        parser.error("Supply IMAGE or --inside")


if __name__ == "__main__":
    main()
