"""Verify the scoped adapter's environment and exact entrypoint delegation."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TLS_SETTINGS = ("UV_SYSTEM_CERTS", "UV_NATIVE_TLS", "SSL_CERT_FILE", "SSL_CERT_DIR")


class UVEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.adapter = self.directory / "library-uv-entrypoint"
        shutil.copyfile(ROOT / "images/shared/uv-entrypoint.sh", self.adapter)
        # The actual system trust/UID operations are covered by
        # test_entrypoint_trust.py and the container trust fixture. Here the
        # delegated entrypoint records exactly what the adapter forwards.
        (self.directory / "library-entrypoint").write_text(
            "exec python3 -c 'import json,os,sys; "
            "print(json.dumps({\"argv\":sys.argv[1:],\"env\":dict(os.environ)}))' \"$@\"\n")

    def invoke(self, settings, *arguments):
        env = {key: value for key, value in os.environ.items()
               if key not in (*TLS_SETTINGS, "LIBRARY_CA_FILE", "PUID", "PGID")}
        env.update(settings)
        result = subprocess.run(["bash", str(self.adapter), *arguments], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_ca_uses_system_roots_and_preserves_command_arguments_and_identity(self):
        settings = {"LIBRARY_CA_FILE": "/run/private.pem", "PUID": "0", "PGID": "0"}
        arguments = ("python3", "-c", "print('spaces ; $ and quotes')", "", "two words")
        actual = self.invoke(settings, *arguments)
        self.assertEqual(actual["argv"], list(arguments))
        self.assertEqual(actual["env"]["UV_SYSTEM_CERTS"], "true")
        for key, value in settings.items():
            self.assertEqual(actual["env"][key], value)
        for key in TLS_SETTINGS[1:]:
            self.assertNotIn(key, actual["env"])

    def test_no_ca_or_empty_ca_preserves_uv_defaults_and_identity(self):
        for settings in ({}, {"LIBRARY_CA_FILE": ""}, {"PUID": "1234", "PGID": "2345"}):
            with self.subTest(settings=settings):
                actual = self.invoke(settings, "bash")
                self.assertEqual(actual["argv"], ["bash"])
                for key in TLS_SETTINGS:
                    self.assertNotIn(key, actual["env"])
                for key, value in settings.items():
                    self.assertEqual(actual["env"][key], value)

    def test_every_explicit_tls_setting_has_precedence_including_empty_values(self):
        for key in TLS_SETTINGS:
            for value in ("false", "true", "", "/project/private-trust"):
                with self.subTest(key=key, value=value):
                    actual = self.invoke({"LIBRARY_CA_FILE": "/run/private.pem", key: value}, "true")
                    self.assertEqual(actual["env"][key], value)
                    if key != "UV_SYSTEM_CERTS":
                        self.assertNotIn("UV_SYSTEM_CERTS", actual["env"])

    def test_explicit_settings_are_unchanged_without_a_ca(self):
        settings = {"UV_SYSTEM_CERTS": "false", "UV_NATIVE_TLS": "false",
                    "SSL_CERT_FILE": "/project/roots.pem", "SSL_CERT_DIR": "/project/roots"}
        actual = self.invoke(settings, "true")
        for key, value in settings.items():
            self.assertEqual(actual["env"][key], value)

    def test_delegated_failure_status_is_preserved(self):
        (self.directory / "library-entrypoint").write_text("exit 37\n")
        result = subprocess.run(["bash", str(self.adapter), "true"], capture_output=True)
        self.assertEqual(result.returncode, 37)


if __name__ == "__main__":
    unittest.main()
