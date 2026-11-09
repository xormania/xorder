"""Independent build-routing and executable runtime contracts for the Mago images."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import artifact_identity
import library
from image_validation import affected_lines, matrix, prerequisites

MAGO = "php-mago-serena/8.4-trixie"
CHROME = "php-chrome-dev/8.4-trixie"
PARENT = "ghcr.io/xormania/php-browser@sha256:" + "a" * 64


def rpc_module():
    path = ROOT / "tests/fixtures/mago-serena/check.py"
    spec = importlib.util.spec_from_file_location("mago_image_rpc_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MagoChromeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.defs = library.definitions()
        self.assertIn(MAGO, self.defs)
        self.assertIn(CHROME, self.defs)

    def test_mago_payload_change_checks_both_consumers_with_only_required_ancestors(self):
        selected = affected_lines(["images/php-mago-serena/serena/uv.lock"], self.defs, ROOT)
        self.assertEqual(selected, [CHROME, MAGO])
        self.assertEqual(matrix(selected, self.defs), {"include": [{
            "line": "php-dev/8.4-trixie", "verify_lines": [CHROME, MAGO]}]})
        self.assertEqual(prerequisites("php-dev/8.4-trixie", selected, self.defs), {
            "php-dev/8.4-trixie", "php-browser/8.4-trixie", MAGO, CHROME})

    def test_browser_refresh_does_not_recheck_slow_parent_or_unrelated_php85(self):
        for path in ("images/php-chrome-dev/Dockerfile", "tests/fixtures/chrome-dev/check.py"):
            with self.subTest(path=path):
                self.assertEqual(affected_lines([path], self.defs, ROOT), [CHROME])
        self.assertEqual(affected_lines(["tests/fixtures/mago-serena/check.py"], self.defs, ROOT),
                         [CHROME, MAGO])

    def test_chrome_inherits_php_and_mago_contract_with_record_backed_availability(self):
        child = self.defs[CHROME]
        self.assertEqual(child["base"], {"parent": MAGO})
        self.assertEqual(self.defs[MAGO]["base"], {"parent": "php-browser/8.4-trixie"})
        self.assertTrue({"php", "composer", "panther", "mago", "serena-mago-adapter",
                         "chrome-for-testing", "chrome-devtools-mcp"} <= set(child["capabilities"]))
        catalog = json.loads((ROOT / "catalog.json").read_text())
        releases = library.records()
        published = {(item["line_id"], item["version"]): item for item in releases
                     if item["line_id"] in {MAGO, CHROME}}
        observed = {(item["line_id"], item["version"]): item for item in catalog["images"]
                    if item["line_id"] in {MAGO, CHROME}}
        self.assertEqual(set(observed), set(published))
        for identity, item in observed.items():
            record = published[identity]
            self.assertEqual(record["verification"]["status"], "passed")
            self.assertEqual(item["digest_reference"],
                             record["publication"]["repository"] + "@" + record["publication"]["digest"])
        unpublished = library.catalog([item for item in releases if item["line_id"] not in {MAGO, CHROME}])
        for line in (MAGO, CHROME):
            definition = self.defs[line]
            self.assertEqual(library.select(unpublished, {
                "family": definition["family"], "runtime_line": definition["runtime_line"],
            })["status"], "no_matching_image")

    def test_vendored_serena_bytes_and_parent_digest_participate_in_build_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "images", root / "images", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "schemas", root / "schemas")
            shutil.copyfile(ROOT / ".dockerignore", root / ".dockerignore")
            definition = self.defs[MAGO]
            initial = artifact_identity.build_key(definition, root, parent=PARENT)
            lock = root / "images/php-mago-serena/serena/uv.lock"
            lock.write_bytes(lock.read_bytes() + b"\n# changed locked payload\n")
            changed = artifact_identity.build_key(definition, root, parent=PARENT)
            self.assertNotEqual(initial, changed)
            self.assertNotEqual(changed, artifact_identity.build_key(
                definition, root, parent=PARENT.replace("a" * 64, "b" * 64)))
            # Packaging prose cannot allocate another copy of this expensive toolchain.
            prose = copy.deepcopy(definition)
            prose.update(purpose="Clarified description", revision="1.0.1", changes=["Editorial"])
            self.assertEqual(changed, artifact_identity.build_key(prose, root, parent=PARENT))


class MagoSeedTests(unittest.TestCase):
    def test_seed_executes_requested_command_and_preserves_owned_configuration(self):
        with tempfile.TemporaryDirectory(prefix="serena seed ") as directory:
            root = Path(directory)
            seed = root / "seed.yml"
            seed.write_text("web_dashboard: false\n")
            home = root / "mapped home"
            environment = dict(os.environ, SERENA_HOME=str(home), XORDER_SERENA_CONFIG=str(seed))
            command = ["sh", str(ROOT / "images/php-mago-serena/entrypoint"),
                       sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(23)", "quoted argument"]
            result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 23, result.stderr)
            self.assertEqual(result.stdout, "quoted argument\n")
            config = home / "serena_config.yml"
            self.assertEqual(config.read_bytes(), seed.read_bytes())
            self.assertEqual(config.stat().st_uid, os.getuid())
            config.write_text("consumer setting: retained\n")
            result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 23, result.stderr)
            self.assertEqual(config.read_text(), "consumer setting: retained\n")


    def test_custom_ca_reaches_uv_without_overriding_explicit_tls_choices(self):
        tls_names = ("UV_SYSTEM_CERTS", "UV_NATIVE_TLS", "SSL_CERT_FILE", "SSL_CERT_DIR")
        scenarios = (
            ("no custom CA", "", {}, None),
            ("installed custom CA", "/mounted/proxy-ca.pem", {}, "true"),
            ("explicit system roots", "/mounted/proxy-ca.pem", {"UV_SYSTEM_CERTS": "false"}, "false"),
            ("explicit empty system roots", "/mounted/proxy-ca.pem", {"UV_SYSTEM_CERTS": ""}, ""),
            ("legacy TLS choice", "/mounted/proxy-ca.pem", {"UV_NATIVE_TLS": "false"}, None),
            ("certificate file", "/mounted/proxy-ca.pem", {"SSL_CERT_FILE": "/consumer/ca.pem"}, None),
            ("certificate directory", "/mounted/proxy-ca.pem", {"SSL_CERT_DIR": "/consumer/roots"}, None),
            ("explicit empty certificate file", "/mounted/proxy-ca.pem", {"SSL_CERT_FILE": ""}, None),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.yml"
            seed.write_text("web_dashboard: false\n")
            clean_environment = {key: value for key, value in os.environ.items()
                                 if key not in {*tls_names, "LIBRARY_CA_FILE"}}
            command = ["sh", str(ROOT / "images/php-mago-serena/entrypoint"), sys.executable, "-c",
                       "import json, os; print(json.dumps({key: os.environ.get(key) for key in "
                       + repr(tls_names) + "}))"]
            for name, ca_file, overrides, expected_system in scenarios:
                with self.subTest(scenario=name):
                    environment = dict(clean_environment, SERENA_HOME=str(root / "home"),
                                       XORDER_SERENA_CONFIG=str(seed), LIBRARY_CA_FILE=ca_file, **overrides)
                    result = subprocess.run(command, env=environment, capture_output=True,
                                            text=True, check=True, timeout=5)
                    observed = json.loads(result.stdout)
                    self.assertEqual(observed["UV_SYSTEM_CERTS"], expected_system)
                    for key in tls_names[1:]:
                        self.assertEqual(observed[key], overrides.get(key))


class MagoAdapterIdentityTests(unittest.TestCase):
    def test_adapter_refuses_tampered_executable_before_launch(self):
        # SolidLSP is an image dependency. Stub only its base classes; the
        # dependency provider under test runs its real file and hash checks.
        modules = {
            "solidlsp.dependency_provider": SimpleNamespace(LanguageServerDependencyProvider=object),
            "solidlsp.ls": SimpleNamespace(SolidLanguageServer=object),
            "solidlsp.ls_process": SimpleNamespace(StdioLanguageServer=object),
        }
        source = ROOT / "images/php-mago-serena/serena/adapter/src/serena_mago/server.py"
        spec = importlib.util.spec_from_file_location("mago_adapter_identity_contract", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="mago executable ") as directory:
            root = Path(directory)
            executable = root / "mago"
            executable.write_bytes(b"original pinned executable")
            executable.chmod(0o755)
            identity = root / "identity.json"
            identity.write_text(json.dumps({"mago_binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}))
            with patch.dict(os.environ, MAGO_BINARY=str(executable), DEV_IMAGE_IDENTITY=str(identity)):
                provider = module.MagoDependency()
                self.assertEqual(provider.create_launch_command(), [str(executable), "language-server"])
                self.assertEqual(provider.create_launch_command_env(), {"MAGO_EXPERIMENTAL_SERVER": "1"})
                executable.write_bytes(b"replacement executable")
                with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                    provider.create_launch_command()


class SerenaSmokeSemanticsTests(unittest.TestCase):
    def client_type(self, represented_source):
        class SymbolCollection:
            # The pinned Serena collection has represent(), with the default
            # object __str__; string coercion cannot establish source content.
            def represent(self):
                return represented_source

        class FakeClient:
            def __init__(self, *_args, **_kwargs):
                self.scope = {"s": SimpleNamespace(lsp=SimpleNamespace(
                    find_symbol=lambda *_args, **_kwargs: SymbolCollection()))}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def notify(self, *_args):
                pass

            def call(self, method, params=None):
                if method == "initialize":
                    return {"serverInfo": {"name": "serena"}}
                if method == "tools/list":
                    return {"tools": [{"name": "initial_instructions"}, {"name": "serena_repl"}]}
                if method != "tools/call":
                    raise AssertionError(method)
                if params["name"] == "initial_instructions":
                    return {"content": [{"type": "text", "text": "Your Serena session id is `test-session`"}]}
                assert params["name"] == "serena_repl", params
                assert params["arguments"]["session"] == "test-session", params
                tree = ast.parse(params["arguments"]["code"])
                last = tree.body.pop() if isinstance(tree.body[-1], ast.Expr) else None
                try:
                    # Execute only this repository's authored smoke snippet.
                    # Pinned Serena returns the final expression, without stdout.
                    with contextlib.redirect_stdout(io.StringIO()):
                        exec(compile(tree, "<trusted-smoke>", "exec"), self.scope)  # nosec B102
                        value = eval(compile(ast.Expression(last.value), "<trusted-smoke>", "eval"), self.scope) if last else None  # nosec B307
                    output = "" if value is None else str(value)
                except Exception as error:
                    # REPL failures can be textual results with isError absent.
                    output = f"{type(error).__name__}: {error}"
                return {"content": [{"type": "text", "text": output}]}
        return FakeClient

    def test_symbol_smoke_uses_collection_representation_and_final_expression(self):
        module = rpc_module()
        with patch.object(module, "RpcClient", self.client_type("Example::answer() { return 42; }")):
            module.verify_serena(Path("/prepared/project"))

    def test_symbol_smoke_rejects_textual_repl_error_when_source_is_missing(self):
        module = rpc_module()
        with patch.object(module, "RpcClient", self.client_type("Example::answer()")):
            with self.assertRaises(AssertionError):
                module.verify_serena(Path("/prepared/project"))


class ChromeSmokeTextTests(unittest.TestCase):
    def verify_pages(self, text):
        module = rpc_module()
        class Client:
            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def notify(self, *_args):
                pass

            def call(self, method, params=None):
                if method == "initialize":
                    return {"serverInfo": {"name": "chrome-devtools-mcp"}}
                if method == "tools/list":
                    return {"tools": [{"name": name} for name in (
                        "list_pages", "list_3p_developer_tools", "execute_3p_developer_tool")]}
                if method == "tools/call" and params["name"] == "list_pages":
                    return {"content": [{"type": "text", "text": text}]}
                raise AssertionError((method, params))
        with patch.object(module, "RpcClient", Client), patch.object(module.subprocess, "run", return_value=SimpleNamespace(stdout="<html></html>")):
            module.verify_chrome()

    def test_multiline_mcp_page_listing_is_read_as_text(self):
        self.verify_pages("## Pages\n1: about:blank [selected]\n## Third-party developer tools\nNo third-party developer tools available.")

    def test_missing_page_or_inline_example_does_not_establish_a_page(self):
        for text in ("## Pages\nNo pages available.", "An example would be 1: about:blank"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                self.verify_pages(text)


class MagoRpcClientTests(unittest.TestCase):
    @staticmethod
    def echo_server():
        # This independent process validates the wire, including absent keys;
        # the client cannot satisfy these checks by changing Python defaults.
        return r"""
import json, sys
framing = sys.argv[1]
def receive():
    if framing == 'lines':
        body = sys.stdin.buffer.readline()
    else:
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in (b'\r\n', b'\n'):
                break
            key, value = line.decode().split(':', 1)
            headers[key.lower()] = value.strip()
        body = sys.stdin.buffer.read(int(headers['content-length']))
    return json.loads(body) if body else None

def respond(message):
    body = json.dumps(message).encode()
    if framing == 'lsp':
        sys.stdout.buffer.write(('Content-Length: %d\r\n\r\n' % len(body)).encode() + body)
    else:
        sys.stdout.buffer.write(body + b'\n')
    sys.stdout.buffer.flush()

last_notification = None
while True:
    request = receive()
    if request is None:
        break
    if request['method'] == 'exit':
        sys.exit(23 if 'params' in request else 0)
    if 'id' not in request:
        last_notification = request
        continue
    response = {'jsonrpc': '2.0', 'id': request['id']}
    if request['method'] == 'shutdown':
        if 'params' in request:
            response['error'] = {'code': -32602, 'message': 'shutdown takes no parameters'}
        else:
            response['result'] = None
    else:
        response['result'] = last_notification if request['method'] == 'last-notification' else request
    respond(response)
"""

    def test_parameterless_shutdown_and_exit_work_with_strict_servers(self):
        module = rpc_module()
        for framing in ('lines', 'lsp'):
            with self.subTest(framing=framing):
                with module.RpcClient([sys.executable, '-u', '-c', self.echo_server(), framing],
                                      framing=framing, timeout=3) as client:
                    self.assertIsNone(client.call('shutdown'))
                    client.notify('exit')
                    self.assertEqual(client.process.wait(timeout=3), 0)

    def test_parameterless_exit_notification_has_no_params_member(self):
        module = rpc_module()
        for framing in ('lines', 'lsp'):
            with self.subTest(framing=framing):
                with module.RpcClient([sys.executable, '-u', '-c', self.echo_server(), framing],
                                      framing=framing, timeout=3) as client:
                    client.notify('exit')
                    self.assertEqual(client.process.wait(timeout=3), 0)

    def test_explicit_falsey_call_parameters_retain_json_value_and_type(self):
        module = rpc_module()
        for framing in ('lines', 'lsp'):
            with module.RpcClient([sys.executable, '-u', '-c', self.echo_server(), framing],
                                  framing=framing, timeout=3) as client:
                for params in ({}, [], 0, False, '', None):
                    with self.subTest(framing=framing, params=params):
                        observed = client.call('echo', params)
                        self.assertIn('params', observed)
                        self.assertEqual(json.dumps(observed['params']), json.dumps(params))

    def test_explicit_falsey_notification_parameters_retain_json_value_and_type(self):
        module = rpc_module()
        for framing in ('lines', 'lsp'):
            with module.RpcClient([sys.executable, '-u', '-c', self.echo_server(), framing],
                                  framing=framing, timeout=3) as client:
                for params in ({}, [], 0, False, '', None):
                    with self.subTest(framing=framing, params=params):
                        client.notify('notifications/echo', params)
                        observed = client.call('last-notification')
                        self.assertNotIn('id', observed)
                        self.assertIn('params', observed)
                        self.assertEqual(json.dumps(observed['params']), json.dumps(params))

    def test_newline_mcp_ignores_notifications_and_matches_response_id(self):
        module = rpc_module()
        program = """
import json, sys
request = json.loads(sys.stdin.readline())
print(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/message', 'params': {'level': 'info'}}), flush=True)
print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': {'echo': request['params']}}), flush=True)
"""
        with module.RpcClient([sys.executable, "-u", "-c", program], timeout=3) as client:
            self.assertEqual(client.call("echo", {"value": "λ"}), {"echo": {"value": "λ"}})
        self.assertIsNotNone(client.process.poll())

    def test_lsp_content_length_counts_utf8_bytes_and_accepts_fragmented_frames(self):
        module = rpc_module()
        program = """
import json, sys
headers = {}
while True:
    line = sys.stdin.buffer.readline()
    if line in (b'\\r\\n', b'\\n'):
        break
    name, value = line.decode().split(':', 1)
    headers[name.lower()] = value.strip()
request = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
body = json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': {'symbol': 'λ'}}, ensure_ascii=False).encode()
frame = ('Content-Length: %d\\r\\n\\r\\n' % len(body)).encode() + body
for byte in frame:
    sys.stdout.buffer.write(bytes([byte]))
    sys.stdout.buffer.flush()
"""
        with module.RpcClient([sys.executable, "-u", "-c", program], framing="lsp", timeout=3) as client:
            self.assertEqual(client.call("initialize", {"rootUri": "file:///tmp/λ"}), {"symbol": "λ"})

    def test_json_rpc_error_cannot_count_as_successful_handshake(self):
        module = rpc_module()
        program = """
import json, sys
request = json.loads(sys.stdin.readline())
print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32603, 'message': 'initialization refused'}}), flush=True)
"""
        with module.RpcClient([sys.executable, "-u", "-c", program], timeout=3) as client:
            with self.assertRaisesRegex(RuntimeError, "initialization refused"):
                client.call("initialize")

    def test_silent_server_has_deadline_and_is_reaped(self):
        module = rpc_module()
        with self.assertRaisesRegex(RuntimeError, "deadline"):
            with module.RpcClient([sys.executable, "-u", "-c", "import time; time.sleep(30)"],
                                  timeout=0.15) as client:
                client.call("initialize")
        self.assertIsNotNone(client.process.poll())


if __name__ == "__main__":
    unittest.main()
