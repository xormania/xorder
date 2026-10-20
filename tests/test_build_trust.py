"""Build-only trust, secret argument boundaries, and derived-line diagnostics."""
import contextlib
import csv
import http.server
import importlib.util
import io
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build

spec = importlib.util.spec_from_file_location("matrix_installer", ROOT / "images/python-matrix/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class BuildTrustTests(unittest.TestCase):
    def test_ca_is_a_buildkit_file_secret_and_never_a_build_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            ca = Path(temporary) / 'CA, with "quotes" and spaces.pem'
            ca.write_text("private CA bytes")
            with patch.dict(os.environ, {"CA_CERTIFICATE": str(ca)}), patch.object(build.subprocess, "run") as run:
                build.build("python-matrix/trixie", "local:test", "local", parent="parent@sha256:" + "a" * 64)
            command = run.call_args.args[0]
            secret = command[command.index("--secret") + 1]
            self.assertEqual(next(csv.reader([secret])), ["id=xorder_ca", "src=" + str(ca)])
            arguments = [command[i + 1] for i, item in enumerate(command) if item == "--build-arg"]
            self.assertFalse(any(str(ca) in item or "private CA bytes" in item for item in arguments))
            self.assertNotIn("private CA bytes", " ".join(command))

    def test_no_ca_does_not_add_a_secret_and_invalid_paths_fail_before_docker(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            with patch.object(build.subprocess, "run") as run:
                build.build("python-dev/3.14-trixie", "local:test", "local")
                self.assertNotIn("--secret", run.call_args.args[0])
            for value in ("relative.pem", temporary, str(Path(temporary) / "missing.pem")):
                with self.subTest(value=value), patch.dict(os.environ, {"CA_CERTIFICATE": value}), \
                        patch.object(build.subprocess, "run") as run:
                    with self.assertRaisesRegex(ValueError, "readable absolute PEM"):
                        build.build("python-dev/3.14-trixie", "local:test", "local")
                    run.assert_not_called()

    def test_missing_parent_is_an_actionable_cli_error_without_docker_or_traceback(self):
        with patch.object(build.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as raised:
                build.main(["python-matrix/trixie", "local:test"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("python-dev/3.14-trixie", error.getvalue())
        self.assertIn("--parent", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())
        run.assert_not_called()

    def test_private_https_works_only_with_the_scoped_combined_trust_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ca, key = root / "ca.pem", root / "ca.key"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(key), "-out", str(ca), "-days", "1", "-subj", "/CN=localhost",
                            "-addext", "basicConstraints=critical,CA:TRUE",
                            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            system_ca = Path(ssl.get_default_verify_paths().cafile)
            before = system_ca.read_bytes()
            with patch.dict(os.environ, {}, clear=True):
                without = installer.install_environment(root / "absent", root, system_ca)
                self.assertNotIn("SSL_CERT_FILE", without)
                self.assertFalse((root / "ca-bundle.pem").exists())
                environment = installer.install_environment(ca, root, system_ca)
                self.assertNotIn("SSL_CERT_FILE", os.environ)
            self.assertEqual(environment["UV_SYSTEM_CERTS"], "1")
            self.assertEqual(system_ca.read_bytes(), before)
            self.assertEqual(Path(environment["SSL_CERT_FILE"]).read_bytes(), before + b"\n" + ca.read_bytes())

            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"private download")

                def log_message(self, *_args):
                    pass

            server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(ca, key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"https://127.0.0.1:{server.server_port}/"
                def download(context):
                    client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                         urllib.request.HTTPSHandler(context=context))
                    with client.open(url, timeout=3) as response:
                        return response.read()
                with self.assertRaises(urllib.error.URLError):
                    download(ssl.create_default_context(cafile=str(system_ca)))
                self.assertEqual(download(ssl.create_default_context(cafile=environment["SSL_CERT_FILE"])),
                                 b"private download")
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
