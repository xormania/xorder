import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
import network
import proxy_relay

spec = importlib.util.spec_from_file_location("proxy_fixture", ROOT / "tests/fixtures/network/check.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        while data := self.request.recv(65536):
            self.server.received.append(data)
            self.request.sendall(data)


class ProxyNetworkTests(unittest.TestCase):
    def setUp(self):
        self.owner = "test:" + uuid.uuid4().hex
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.docker_path = Path(temporary.name)
        self.docker_env = fixture.mock_docker(self.docker_path, [fixture.peer(self.owner, "127.0.0.1")])
        environment = patch.dict(os.environ, self.docker_env)
        environment.start()
        self.addCleanup(environment.stop)
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Echo)
        self.server.received = []
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(proxy_relay.stop, self.owner)
        self.target = self.server.server_address

    def roundtrip(self, port, source="127.0.0.1"):
        with socket.create_connection(("127.0.0.2", port), timeout=2, source_address=(source, 0)) as stream:
            payload = b"CONNECT permitted.example:443 HTTP/1.1\r\n\r\n"
            stream.sendall(payload)
            stream.shutdown(socket.SHUT_WR)
            self.assertEqual(stream.makefile("rb").read(), payload)

    def test_reuse_restart_and_parallel_owner_cleanup(self):
        def ensure():
            return proxy_relay.ensure(self.owner, "127.0.0.2", [self.target])[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            ports = list(pool.map(lambda _: ensure(), range(4)))
        self.assertEqual(len(set(ports)), 1)
        self.roundtrip(ports[0])
        # A graceful relay exit without deleting its receipt simulates a restart.
        proxy_relay.halt(proxy_relay.directory(self.owner))
        self.assertEqual(ensure(), ports[0])
        self.roundtrip(ports[0])
        other = self.owner + ":other"
        self.addCleanup(proxy_relay.stop, other)
        (self.docker_path / "peers.json").write_text(json.dumps([
            fixture.peer(self.owner, "127.0.0.1"), fixture.peer(other, "127.0.0.3")]))
        second = proxy_relay.ensure(other, "127.0.0.2", [self.target])[0]
        proxy_relay.stop(self.owner)
        self.roundtrip(second, source="127.0.0.3")
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.2", ports[0]), timeout=1)

    def test_mapping_preserves_credentials_host_environment_and_no_proxy(self):
        env = dict(self.docker_env, HTTPS_PROXY=f"http://name:p%40ss@127.0.0.1:{self.target[1]}", NO_PROXY="internal.example", HTTP_PROXY="http://remote:80")
        original = dict(env)
        with patch.object(network, "bridge_address", return_value="127.0.0.2"):
            result = network.container_environment(env, self.owner, services=("php", "redis"))
        self.assertEqual(env, original)
        self.assertTrue(result["HTTPS_PROXY"].startswith("http://name:p%40ss@127.0.0.2:"))
        self.assertEqual(result["HTTP_PROXY"], env["HTTP_PROXY"])
        self.assertEqual(result["NO_PROXY"], "internal.example,localhost,127.0.0.1,::1,php,redis")
        self.assertNotIn("p%40ss", (proxy_relay.directory(self.owner) / "state.json").read_text())

    def test_loopback_spellings(self):
        for value in ("127.9.0.1:3128", "http://LOCALHOST.:3128", "http://[::1]:3128", "http://[::ffff:127.0.0.1]:3128"):
            self.assertIsNotNone(network.loopback_proxy(value, "HTTP_PROXY"))
        self.assertIsNone(network.loopback_proxy("http://remote:3128", "HTTP_PROXY"))

    def test_no_proxy_remote_proxy_and_explicit_modes_need_no_relay(self):
        with patch.object(network, "bridge_address", side_effect=AssertionError("Unexpected bridge lookup")):
            self.assertEqual(network.container_environment({}, self.owner)["HTTP_PROXY"], "")
            self.assertEqual(network.container_environment({"HTTP_PROXY": "http://remote:80"}, self.owner)["HTTP_PROXY"], "http://remote:80")
            self.assertEqual(network.container_environment({"HTTP_PROXY": "http://localhost:80", "PROXY_PASSTHROUGH": "0"}, self.owner)["HTTP_PROXY"], "")
            self.assertEqual(network.container_environment({"HTTP_PROXY": "http://localhost:80", "PROXY_PASSTHROUGH": "1"}, self.owner)["HTTP_PROXY"], "http://localhost:80")

    def test_changed_target_needs_up_and_unbindable_bridge_fails(self):
        proxy_relay.ensure(self.owner, "127.0.0.2", [self.target])
        with self.assertRaisesRegex(ValueError, "run up"):
            proxy_relay.ensure(self.owner, "127.0.0.3", [self.target])
        with self.assertRaisesRegex(ValueError, "Cannot bind"):
            proxy_relay.ensure(self.owner, "192.0.2.123", [self.target], reconfigure=True)

    def test_ephemeral_command_keeps_host_proxy_and_cleans_up_its_relay(self):
        upstream = f"http://127.0.0.1:{self.target[1]}"
        ports = []
        def command(arguments, env):
            self.assertEqual(env["HTTPS_PROXY"], upstream)
            label = arguments[arguments.index("--label") + 1]
            self.assertTrue(label.startswith(proxy_relay.OWNER_LABEL + "="))
            container = fixture.peer(self.owner, "127.0.0.1")
            container["Config"]["Labels"][proxy_relay.OWNER_LABEL] = label.split("=", 1)[1]
            (self.docker_path / "peers.json").write_text(json.dumps([container]))
            proxy_file = Path(arguments[arguments.index("--env-file") + 1])
            forwarded = next(value for value in proxy_file.read_text().splitlines()
                             if value.startswith("HTTPS_PROXY=http://127.0.0.2:"))
            ports.append(int(forwarded.rsplit(":", 1)[1]))
            self.roundtrip(ports[0])
            self.assertEqual(arguments[-3:], ["application", "-e", "HTTPS_PROXY"])
            return 7
        with patch.dict(os.environ, dict(self.docker_env, HTTPS_PROXY=upstream), clear=True), \
             patch.object(network, "bridge_address", return_value="127.0.0.2"), \
             patch.object(network.subprocess, "call", side_effect=command):
            self.assertEqual(network.main(["docker", "run", "fixture", "application", "-e", "HTTPS_PROXY"]), 7)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.2", ports[0]), timeout=1)

    def test_real_tls_and_policy_rejection(self):
        fixture.verify()

    def rejected(self, port, source):
        before = list(self.server.received)
        with socket.create_connection(("127.0.0.2", port), timeout=2, source_address=(source, 0)) as stream:
            stream.sendall(b"CONNECT forbidden.example:443 HTTP/1.1\r\n\r\n")
            try:
                self.assertEqual(stream.recv(1024), b"")
            except ConnectionResetError:
                pass
        self.assertEqual(self.server.received, before, "Rejected bytes reached the upstream proxy")

    def test_connections_require_current_container_ownership(self):
        port = proxy_relay.ensure(self.owner, "127.0.0.2", [self.target])[0]
        self.roundtrip(port)
        # A different owner and an unlabeled source are denied.
        (self.docker_path / "peers.json").write_text(json.dumps([
            fixture.peer(self.owner, "127.0.0.1"), fixture.peer("other", "127.0.0.3")]))
        self.rejected(port, "127.0.0.3")
        self.rejected(port, "127.0.0.4")
        # Container replacement must admit the new address and immediately
        # stop admitting the old one, even if another container reuses it.
        (self.docker_path / "peers.json").write_text(json.dumps([
            fixture.peer("other", "127.0.0.1"), fixture.peer(self.owner, "127.0.0.3")]))
        self.rejected(port, "127.0.0.1")
        self.roundtrip(port, source="127.0.0.3")
        # Missing Docker evidence must fail closed, never restore open access.
        (self.docker_path / "peers.json").unlink()
        self.rejected(port, "127.0.0.3")

    def test_stopped_host_network_and_malformed_inspection_are_denied(self):
        container = fixture.peer(self.owner, "127.0.0.1")
        label = proxy_relay.owner_label(self.owner)
        def allowed(evidence):
            with patch.object(proxy_relay.subprocess, "check_output", side_effect=["id", json.dumps(evidence)]):
                return proxy_relay.source_allowed("127.0.0.1", label)
        self.assertTrue(allowed([container]))
        container["State"]["Running"] = False
        self.assertFalse(allowed([container]))
        container["State"]["Running"] = True
        container["HostConfig"]["NetworkMode"] = "host"
        self.assertFalse(allowed([container]))
        container["HostConfig"]["NetworkMode"] = "bridge"
        container["Config"]["Labels"] = {}
        self.assertFalse(allowed([container]))
        self.assertFalse(allowed([{}]))


class NetworkCommandPrivacyTests(unittest.TestCase):
    def test_authenticated_proxies_stay_out_of_argv_and_private_file_is_removed(self):
        credential = "probe-" + uuid.uuid4().hex
        proxy = f"http://user:{credential}@bridge.test:3128"
        for outcome in (0, 37, OSError("synthetic Docker failure")):
            with self.subTest(outcome=outcome):
                files = []

                def command(arguments, env):
                    self.assertNotIn(credential, " ".join(arguments))
                    self.assertEqual(env["HTTPS_PROXY"], proxy)
                    self.assertEqual(arguments[-3:], ["image", "application", "argument"])
                    path = Path(arguments[arguments.index("--env-file") + 1])
                    files.append(path)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
                    self.assertEqual(values["HTTPS_PROXY"], proxy)
                    self.assertEqual(values["ALL_PROXY"], proxy)
                    self.assertEqual(values["NO_PROXY"], "internal.example,localhost,127.0.0.1,::1")
                    if isinstance(outcome, OSError):
                        raise outcome
                    return outcome

                with patch.dict(os.environ, {"HTTPS_PROXY": proxy, "ALL_PROXY": proxy,
                                             "NO_PROXY": "internal.example"}, clear=True), \
                        patch.object(network.subprocess, "call", side_effect=command), \
                        patch.object(network, "stop") as stop:
                    if isinstance(outcome, OSError):
                        with self.assertRaisesRegex(OSError, "synthetic Docker failure"):
                            network.main(["docker", "run", "image", "application", "argument"])
                    else:
                        self.assertEqual(network.main(["docker", "run", "image", "application", "argument"]), outcome)
                    stop.assert_called_once()
                self.assertEqual(len(files), 1)
                self.assertFalse(files[0].exists())

    def test_newlines_cannot_add_container_environment_or_leak_values(self):
        for key in (*network.PROXIES, "NO_PROXY", "no_proxy"):
            for newline in ("\n", "\r"):
                with self.subTest(key=key, newline=newline), \
                        patch.object(network, "bridge_address") as bridge, \
                        patch.object(network.subprocess, "call") as command, \
                        patch.object(network, "stop"), \
                        patch.dict(os.environ, {key: "proxy.example" + newline + "INJECTED=private-value"}, clear=True):
                    with self.assertRaisesRegex(ValueError, "single line") as error:
                        network.main(["docker", "run", "image"])
                    self.assertNotIn("private-value", str(error.exception))
                    command.assert_not_called()
                    bridge.assert_not_called()
