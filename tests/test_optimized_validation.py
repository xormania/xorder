"""Production validation must survive Python optimization."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OptimizedValidationTests(unittest.TestCase):
    def run_modes(self, source):
        program = "import sys\nsys.path.insert(0, 'scripts')\n" + textwrap.dedent(source)
        for flags, optimization in (([], None), (["-O"], None), ([], "1")):
            with self.subTest(flags=flags, PYTHONOPTIMIZE=optimization):
                environment = dict(os.environ)
                environment.pop("PYTHONOPTIMIZE", None)
                if optimization is not None:
                    environment["PYTHONOPTIMIZE"] = optimization
                result = subprocess.run([sys.executable, *flags, "-c", program], cwd=ROOT,
                                        env=environment, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("check enforced", result.stdout)

    def test_inventory_accepts_valid_inputs_and_rejects_wrong_platform(self):
        self.run_modes("""
            import library
            definition = {"platforms": ["linux/amd64"], "extensions": ["needed"],
                          "tools": ["php"], "runtime_line": "8.5", "family": "php-dev",
                          "capabilities": []}
            inventory = {"platform": "linux/amd64", "os": {"VERSION_CODENAME": "trixie"},
                         "extensions": {"needed": "1"}, "tools": {"php": "8.5.1"},
                         "runtime_version": "8.5.1"}
            library.validate_inventory(definition, inventory)
            inventory["platform"] = "linux/arm64"
            try:
                library.validate_inventory(definition, inventory)
            except AssertionError:
                print("check enforced")
            else:
                raise RuntimeError("Incorrect platform passed inventory validation")
        """)

    def test_release_record_requires_passed_verification(self):
        self.run_modes("""
            import library
            path = next((library.ROOT / "release-records/php-dev/8.4-trixie").glob("*.json"))
            record = library.read(path)
            library.validate_record(record)
            record["verification"]["status"] = "failed"
            try:
                library.validate_record(record)
            except AssertionError:
                print("check enforced")
            else:
                raise RuntimeError("Failed verification was accepted as release evidence")
        """)

    def test_cache_probe_rejects_wrong_layers_or_revision_before_cleanup(self):
        self.run_modes("""
            from unittest.mock import patch
            import build
            before = {"RootFS": {"Layers": ["original"]}}
            after = [
                {"RootFS": {"Layers": ["different"]},
                 "Config": {"Labels": {"org.opencontainers.image.revision": "source-cache-probe"}}},
                {"RootFS": {"Layers": ["original"]},
                 "Config": {"Labels": {"org.opencontainers.image.revision": "wrong"}}},
            ]
            for observed in after:
                with patch.object(build, "image_facts", side_effect=[before, observed]), \
                        patch.object(build, "build"), patch.object(build.subprocess, "run") as command:
                    try:
                        build.cache_probe("example", "image", "source")
                    except AssertionError:
                        command.assert_not_called()
                    else:
                        raise RuntimeError("Invalid cache probe was accepted")
            print("check enforced")
        """)

    def test_refresh_requires_complete_sha256_for_both_upstream_assets_before_writing_pins(self):
        self.run_modes("""
            import contextlib
            import io
            import json
            from pathlib import Path
            import tempfile
            from unittest.mock import patch
            import refresh
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "images").mkdir()
                path = root / "images/tools.json"
                original = json.dumps({name: {"tag": "example", "digest": "old"}
                                       for name in ("composer", "uv", "node")})
                path.write_text(original)
                valid = "sha256:" + "a" * 64
                def releases(first, second):
                    return [{"tag_name": "v1.0.0", "assets": [{"name": name,
                             "browser_download_url": "https://example.test/asset", "digest": digest}]}
                            for name, digest in (("symfony-cli_linux_amd64.tar.gz", first), ("infection.phar", second))]
                for invalid in (None, 1, "", "sha256:", "sha256:a", "sha256:" + "a" * 63, "sha256:" + "z" * 64):
                    for pair in ((invalid, valid), (valid, invalid)):
                        with patch.object(refresh, "ROOT", root), \
                                patch.object(refresh, "resolve", return_value={"digest": valid}), \
                                patch.object(refresh, "fetch_json", side_effect=releases(*pair)), \
                                patch.object(refresh, "apt_indexes", return_value={}), \
                                patch.object(refresh.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(b"1.0.0")):
                            try:
                                refresh.refresh()
                            except AssertionError as error:
                                if "checksum" not in str(error):
                                    raise
                            else:
                                raise RuntimeError("An invalid checksum was accepted")
                        if path.read_text() != original:
                            raise RuntimeError("Unverified pins were written")
                with patch.object(refresh, "ROOT", root), \
                        patch.object(refresh, "resolve", return_value={"digest": valid}), \
                        patch.object(refresh, "fetch_json", side_effect=releases(valid, valid)), \
                        patch.object(refresh, "apt_indexes", return_value={}), \
                        patch.object(refresh.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(b"1.0.0")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    refresh.refresh()
                pins = json.loads(path.read_text())
                if pins["symfony"]["sha256"] != "a" * 64 or pins["infection"]["sha256"] != "a" * 64:
                    raise RuntimeError("Valid upstream checksums were not retained")
            print("check enforced")
        """)


if __name__ == "__main__":
    unittest.main()
