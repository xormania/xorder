"""Execute readiness wrappers with disposable fixtures and an observed Docker CLI.

Docker alone is replaced: these tests check the host/container boundary without
requiring an engine. Real PEM parsing and HTTPS clients have separate fixtures.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

DOCKER = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
files = []
if args and args[0] == "compose":
    for index, arg in enumerate(args[:-1]):
        if arg == "-f":
            path = pathlib.Path(args[index + 1])
            files.append({"path": str(path), "contents": path.read_text()})
    if "run" in args:
        (pathlib.Path(os.environ["WORKSPACE"]) / "workspace-proof.txt").touch()
with open(os.environ["TEST_DOCKER_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "files": files, "env": dict(os.environ)}) + "\n")
if args and args[0] == "run":
    raise SystemExit(int(os.environ.get("TEST_DOCKER_RUN_EXIT", "0")))
'''


class ReadinessNetworkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="xorder-readiness-network-")
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.root = self.area / "repo"
        self.bin = self.area / "bin"
        self.bin.mkdir()
        self.log = self.area / "docker.jsonl"
        self.environment = {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "HOME": str(self.area),
            "TEST_DOCKER_LOG": str(self.log),
        }
        self.write("scripts/verify-image.sh", (ROOT / "scripts/verify-image.sh").read_text())
        self.write("scripts/run-image.sh", (ROOT / "scripts/run-image.sh").read_text())
        self.write("examples/php/compose.yaml", (ROOT / "examples/php/compose.yaml").read_text())
        for kind in ("python", "php", "mutation"):
            self.write(f"tests/fixtures/{kind}/run.sh", "#!/bin/bash\nexit 0\n")
        self.write("tests/fixtures/native-check.c", "int main(void) { return 0; }\n")
        self.write("tests/fixtures/trust/run.sh", "#!/bin/bash\nexit 0\n")
        (self.bin / "docker").write_text(DOCKER)
        (self.bin / "docker").chmod(0o755)
        # Deliberate spaces and interpolation syntax must survive shell and
        # Compose processing as one literal host path.
        self.ca = self.area / "proxy $UNSET ${ALSO_UNSET} certificate.pem"
        self.ca.write_text("host path fixture; PEM validation is tested separately\n")

    def write(self, relative, contents):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def captured(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def execute(self, script, *arguments, **environment):
        return subprocess.run(["bash", str(self.root / script), *arguments],
                              env=dict(self.environment, **environment),
                              cwd=self.root, capture_output=True, text=True, timeout=20)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_python_and_php_compose_call_gets_the_conditional_ca(self):
        for family in ("python-dev", "php-dev"):
            with self.subTest(family=family):
                self.log.unlink(missing_ok=True)
                result = self.execute("scripts/verify-image.sh", family + "/fixture", "candidate:test",
                                      CA_CERTIFICATE=str(self.ca))
                self.assert_success(result)
                compose = [call for call in self.captured() if call["args"][0] == "compose"]
                self.assertGreaterEqual(len(compose), 3)
                self.assertTrue(any("down" in call["args"] for call in compose))
                for call in compose:
                    self.assertEqual(len(call["files"]), 2, call["args"])
                    # Containers can write the workspace, and Compose rereads overrides on each call.
                    override_path = Path(call["files"][1]["path"])
                    self.assertFalse(override_path.is_relative_to(call["env"]["WORKSPACE"]), override_path)
                    override = json.loads(call["files"][1]["contents"])["services"]["dev"]
                    self.assertEqual(override["environment"]["LIBRARY_CA_FILE"], "/run/library-proxy.pem")
                    mounts = [mount for mount in override["volumes"]
                              if mount["target"] == "/run/library-proxy.pem"]
                    self.assertEqual(len(mounts), 1)
                    mount = mounts[0]
                    # Compose interprets $$ as one literal $ in a value.
                    self.assertEqual(mount["source"].replace("$$", "$"), str(self.ca))
                    self.assertNotIn("$UNSET", mount["source"].replace("$$", ""))
                    self.assertNotIn("${ALSO_UNSET}", mount["source"].replace("$$", ""))
                    self.assertEqual(mount["type"], "bind")
                    self.assertTrue(mount["read_only"])
                    self.assertFalse(mount["bind"]["create_host_path"])
                self.assertFalse(override_path.parent.exists())
                direct = [call for call in self.captured() if call["args"][0] == "run"]
                self.assertEqual(len(direct), 1)
                self.assertIn("type=bind,src=" + str(self.ca) + ",dst=/run/library-proxy.pem,readonly",
                              direct[0]["args"])

    def test_no_ca_retains_the_base_compose_and_unmodified_run_recipe(self):
        for family in ("python-dev", "php-dev"):
            with self.subTest(family=family):
                self.log.unlink(missing_ok=True)
                self.assert_success(self.execute("scripts/verify-image.sh", family + "/fixture", "candidate:test"))
                compose = [call for call in self.captured() if call["args"][0] == "compose"]
                self.assertGreaterEqual(len(compose), 3)
                for call in compose:
                    self.assertEqual([item["path"] for item in call["files"]],
                                     [str(self.root / "examples/php/compose.yaml")])
                for call in self.captured():
                    self.assertFalse(any("LIBRARY_CA_FILE" in arg for arg in call["args"]))
                    self.assertFalse(any("library-proxy.pem" in arg for arg in call["args"]))

    def test_invalid_ca_paths_stop_both_wrappers_before_docker(self):
        for script, arguments in (
            ("scripts/verify-image.sh", ["python-dev/fixture", "candidate:test"]),
            ("scripts/verify-image.sh", ["playwright-browser/fixture", "candidate:test"]),
            ("scripts/run-image.sh", ["candidate:test", "true"]),
        ):
            for invalid in ("relative.pem", str(self.area / "missing.pem"), str(self.area)):
                with self.subTest(script=script, arguments=arguments, invalid=invalid):
                    self.log.unlink(missing_ok=True)
                    result = self.execute(script, *arguments, CA_CERTIFICATE=invalid)
                    self.assertEqual(result.returncode, 64, result.stderr)
                    self.assertIn("readable absolute PEM file", result.stderr)
                    self.assertEqual(self.captured(), [])

    def test_run_image_preserves_proxy_settings_and_mounts_the_exact_ca_readonly(self):
        proxies = {"HTTP_PROXY": "http://reachable.test:3128", "HTTPS_PROXY": "http://reachable.test:3129",
                   "NO_PROXY": "localhost,internal.test"}
        self.assert_success(self.execute("scripts/run-image.sh", "candidate:test", "printf", "%s", "literal argument",
                                         CA_CERTIFICATE=str(self.ca), **proxies))
        call, = self.captured()
        self.assertIn("type=bind,src=" + str(self.ca) + ",dst=/run/library-proxy.pem,readonly", call["args"])
        self.assertIn("LIBRARY_CA_FILE=/run/library-proxy.pem", call["args"])
        self.assertEqual(call["args"][-4:], ["candidate:test", "printf", "%s", "literal argument"])
        for name, value in proxies.items():
            self.assertIn(name, call["args"])
            self.assertEqual(call["env"][name], value)

    def prepare_parity(self):
        self.write("tests/fixtures/playwright/parity.sh", (ROOT / "tests/fixtures/playwright/parity.sh").read_text())
        self.write("scripts/playwright_fixture.py", "print('https://fixture.invalid/repo.git\\n' + 'a' * 40 + '\\n1.58.2\\napplication:test')\n")
        git = self.bin / "git"
        git.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
if sys.argv[1] == "init":
    root = pathlib.Path(sys.argv[2]); root.mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"devDependencies": {"@playwright/test": "1.58.2"}}))
    (root / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/@playwright/test": {"version": "1.58.2"}}}))
''')
        git.chmod(0o755)
        self.parity_log = self.area / "parity.jsonl"
        self.write("examples/uxor/run.sh", "#!/bin/bash\npython3 - \"$@\" <<'PY'\n"
                   "import json, os, sys\n"
                   f"with open({str(self.parity_log)!r}, 'a') as log:\n"
                   "    log.write(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ)}) + '\\n')\n"
                   "PY\n")

    def test_browser_parity_forwards_network_configuration_without_caller_credentials(self):
        self.prepare_parity()
        proxies = {"HTTP_PROXY": "http://reachable.test:3128", "HTTPS_PROXY": "http://reachable.test:3129",
                   "NO_PROXY": "localhost,internal.test", "CA_CERTIFICATE": str(self.ca)}
        credentials = {"GH_TOKEN": "must-not-forward", "GITHUB_TOKEN": "must-not-forward",
                       "DOCKER_AUTH_CONFIG": "must-not-forward", "AWS_SECRET_ACCESS_KEY": "must-not-forward",
                       "UNRELATED_SETTING": "must-not-forward"}
        self.assert_success(self.execute("tests/fixtures/playwright/parity.sh", "browser:test", "playwright-browser/fixture",
                                         DOCKER_CONFIG="/caller/credential/config", **proxies, **credentials))
        calls = [json.loads(line) for line in self.parity_log.read_text().splitlines()]
        self.assertEqual([call["args"][0] for call in calls], ["up", "sync", "exec", "down"])
        for call in calls:
            for name, value in proxies.items():
                self.assertEqual(call["env"].get(name), value)
            for name in (*credentials, "TEST_DOCKER_LOG", "XORDER_PARITY_LOCAL_APPLICATION"):
                self.assertNotIn(name, call["env"])
            self.assertEqual(call["env"]["IMAGE"], "application:test")
            self.assertEqual(call["env"]["BROWSER_IMAGE"], "browser:test")
            self.assertEqual(call["env"]["XORDER_PARITY_FIXTURE"], "1")
            self.assertNotEqual(call["env"]["DOCKER_CONFIG"], "/caller/credential/config")

    def test_browser_parity_leaves_unspecified_network_settings_absent(self):
        self.prepare_parity()
        self.assert_success(self.execute("tests/fixtures/playwright/parity.sh", "browser:test", "playwright-browser/fixture"))
        for line in self.parity_log.read_text().splitlines():
            environment = json.loads(line)["env"]
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "CA_CERTIFICATE"):
                self.assertNotIn(name, environment)

    def test_browser_parity_rejects_proxy_credentials_before_consumer_execution(self):
        self.prepare_parity()
        for name in ("HTTP_PROXY", "HTTPS_PROXY"):
            for proxy in ("http://user:secret-password-canary@reachable.test:3128",
                          "user:secret-password-canary@reachable.test:3128",
                          "http://user@reachable.test:3128", "http://@reachable.test:3128",
                          "http:/user:secret-password-canary@reachable.test:3128",
                          "http:///user:secret-password-canary@reachable.test:3128",
                          "http:////user:secret-password-canary@reachable.test:3128"):
                with self.subTest(name=name, proxy=proxy):
                    result = self.execute("tests/fixtures/playwright/parity.sh", "browser:test", "playwright-browser/fixture",
                                          **{name: proxy})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(name + " credentials cannot enter anonymous browser parity", result.stderr)
                    self.assertNotIn("secret-password-canary", result.stderr)
                    self.assertFalse(self.parity_log.exists())
                    self.assertEqual(self.captured(), [])

    def test_browser_parity_rejects_ambiguous_proxy_structure(self):
        self.prepare_parity()
        for proxy in ("http:///reachable.test:3128", "http:/reachable.test:3128",
                      "http://reachable.test:invalid", "http://reachable.test:3128/path",
                      "http://reachable.test:3128?query", "http://reachable.test:3128#fragment",
                      " http://reachable.test:3128"):
            with self.subTest(proxy=proxy):
                result = self.execute("tests/fixtures/playwright/parity.sh", "browser:test", "playwright-browser/fixture",
                                      HTTPS_PROXY=proxy)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("valid credential-free proxy URL", result.stderr)
                self.assertFalse(self.parity_log.exists())
                self.assertEqual(self.captured(), [])

    def test_serena_installs_through_public_wrapper_and_cleans_its_cache_even_on_failure(self):
        spec = importlib.util.spec_from_file_location("readiness_serena_fixture", ROOT / "tests/fixtures/serena/check.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        checkout = self.area / "checkout"
        checkout.mkdir()
        for exit_status in (0, 37):
            with self.subTest(exit_status=exit_status):
                self.log.unlink(missing_ok=True)
                env = dict(self.environment, CA_CERTIFICATE=str(self.ca), HTTPS_PROXY="http://reachable.test:3128",
                           TEST_DOCKER_RUN_EXIT=str(exit_status))
                with patch.object(fixture, "ROOT", self.root), patch.dict(os.environ, env, clear=True):
                    if exit_status:
                        with self.assertRaises(subprocess.CalledProcessError) as raised:
                            fixture.install_consumer("candidate:test", checkout)
                        self.assertEqual(raised.exception.returncode, exit_status)
                    else:
                        fixture.install_consumer("candidate:test", checkout)
                install, cleanup = self.captured()
                self.assertEqual(install["args"][0], "run")
                self.assertIn("type=bind,src=" + str(checkout) + ",dst=/workspace", install["args"])
                self.assertIn("type=bind,src=" + str(self.ca) + ",dst=/run/library-proxy.pem,readonly", install["args"])
                self.assertIn("LIBRARY_CA_FILE=/run/library-proxy.pem", install["args"])
                self.assertIn("HTTPS_PROXY", install["args"])
                self.assertEqual(install["env"]["HTTPS_PROXY"], env["HTTPS_PROXY"])
                command = install["args"][install["args"].index("candidate:test") + 1:]
                self.assertEqual(command[:3], ["composer", "install", "--working-dir=/workspace/demo"])
                self.assertIn("--no-scripts", command)
                self.assertIn("--no-plugins", command)
                self.assertEqual(cleanup["args"], ["volume", "rm", "xorder-serena-fixture-" + checkout.parent.name])


if __name__ == "__main__":
    unittest.main()
