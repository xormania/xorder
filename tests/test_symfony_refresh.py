"""Independent prerelease selection and component invalidation boundaries."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import components
import refresh_symfony


class SymfonyRefreshTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "images/php-mago-serena/toolchain.lock.json").read_text())
        self.observed = {
            "mago": [{"tag_name": "1.60.0-beta1", "prerelease": False, "assets": [{
                "name": "mago-1.60.0-beta1-x86_64-unknown-linux-gnu.tar.gz", "digest": "sha256:" + "a" * 64,
                "browser_download_url": "https://github.com/carthage-software/mago/releases/download/1.60.0-beta1/mago-1.60.0-beta1-x86_64-unknown-linux-gnu.tar.gz"}]}],
            "serena": {"commit": {"sha": "b" * 40}},
            "symfony": [{"tag_name": "v8.2.0-BETA1", "prerelease": False}, {"tag_name": "v8.1.99"}],
            "mate": [{"tag_name": "v1.0.0-BETA1", "prerelease": False}, {"tag_name": "v0.99.0"}],
        }

    def test_beta_syntax_selects_newer_tuple_despite_false_github_prerelease_flag(self):
        before = copy.deepcopy(self.lock)
        plan = refresh_symfony.propose(self.lock, self.observed)
        candidate = plan["candidate"]
        self.assertEqual(plan["status"], "qualification-required")
        self.assertEqual(candidate["targets"]["symfony"], "8.2.0-BETA1")
        self.assertEqual(candidate["mate"]["version"], "1.0.0-BETA1")
        self.assertEqual(candidate["native_mago"]["version"], "1.60.0-beta1")
        self.assertEqual(candidate["serena"]["source_rev"], "b" * 40)
        self.assertEqual(candidate["mago"], before["mago"])
        self.assertEqual(plan["previous"], before)
        self.assertEqual(self.lock, before)

    def test_draft_and_invalid_tags_cannot_displace_the_latest_usable_version(self):
        releases = [{"tag_name": "v99.0.0", "draft": True}, {"tag_name": "nightly"},
                    {"tag_name": "v8.2.0-RC1"}, {"tag_name": "v8.2.0-BETA9"}]
        self.assertEqual(refresh_symfony.newest(releases)["tag_name"], "v8.2.0-RC1")

    def test_latest_release_without_checksum_cannot_silently_use_an_older_artifact(self):
        self.observed["mago"][0]["assets"][0].pop("digest")
        with self.assertRaisesRegex(ValueError, "hash-identified"):
            refresh_symfony.propose(self.lock, self.observed)

    def test_mismatched_backend_sdk_cannot_become_a_refresh_proposal(self):
        self.lock["mago"]["sdk"]["source_rev"] = "e" * 40
        with self.assertRaisesRegex(ValueError, "SDK"):
            refresh_symfony.propose(self.lock, self.observed)


class SymfonyComponentBoundaryTests(unittest.TestCase):
    def test_config_and_adapter_edits_reuse_dependency_payload_while_lock_edits_invalidate_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "images", root / "images", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "schemas", root / "schemas")
            shutil.copyfile(ROOT / ".dockerignore", root / ".dockerignore")
            before = components.build_key("serena-deps", root)
            (root / "images/php-mago-serena/serena/config/serena_config.yml").write_text("agent_interface: REPL\n")
            adapter = root / "images/php-mago-serena/serena/adapter/src/serena_mago/server.py"
            adapter.write_text(adapter.read_text() + "\n# overlay-only change\n")
            self.assertEqual(before, components.build_key("serena-deps", root))
            lock = root / "images/php-mago-serena/serena/uv.lock"
            lock.write_text(lock.read_text() + "\n# changed dependency lock\n")
            self.assertNotEqual(before, components.build_key("serena-deps", root))


if __name__ == "__main__":
    unittest.main()
