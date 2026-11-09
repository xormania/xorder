"""Consumer pin agreement, idempotence and isolation across browser runtime lines."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from library import ROOT, definitions, fingerprint
from image_validation import affected_lines
import refresh_browser
import writeback


class BrowserRefreshTests(unittest.TestCase):
    @staticmethod
    def copy_build_inputs(root):
        for name in ("images", "schemas", "scripts", "examples"):
            shutil.copytree(ROOT / name, root / name)
        shutil.copyfile(ROOT / ".dockerignore", root / ".dockerignore")

    def accepted_catalog(self, path):
        catalog = json.loads(path.read_text())
        catalog["resources"].append({"id": "image/uxor-dev/8.5-trixie", "version": "1.0.0",
                                     "identity": "ghcr.io/xormania/uxor-dev@sha256:" + "c" * 64,
                                     "lifecycle": "available", "verification": {"status": "passed"},
                                     "targets": ["linux/amd64"]})
        path.write_text(json.dumps(catalog))

    def test_consumer_ref_is_resolved_to_commit_and_manifest_lock_must_agree(self):
        commit = {"sha": "a" * 40}
        package = {"devDependencies": {"@playwright/test": "1.58.2"}}
        lock = {"packages": {"node_modules/@playwright/test": {"version": "1.58.2"}}}
        with patch.object(refresh_browser, "fetch_json", side_effect=[commit, package, lock]) as fetch:
            pin = refresh_browser.consumer_pin("feature/browser-bump")
        self.assertEqual(pin["repository"], "https://github.com/xormania/uxor.git")
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [
            "https://api.github.com/repos/xormania/uxor/commits/feature%2Fbrowser-bump",
            "https://raw.githubusercontent.com/xormania/uxor/" + "a" * 40 + "/package.json",
            "https://raw.githubusercontent.com/xormania/uxor/" + "a" * 40 + "/package-lock.json",
        ])
        self.assertEqual(pin["commit"], "a" * 40)
        self.assertEqual(pin["playwright_version"], "1.58.2")
        for manifest_pin in ("^1.58.2", "1.58.3", None):
            bad = {"devDependencies": {"@playwright/test": manifest_pin}}
            with self.subTest(pin=manifest_pin), \
                    patch.object(refresh_browser, "fetch_json", side_effect=[commit, bad, lock]), \
                    self.assertRaises(ValueError):
                refresh_browser.consumer_pin("master")

    def test_new_line_does_not_change_existing_artifacts_or_select_other_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_build_inputs(root)
            shutil.copyfile(ROOT / "catalog-v2.json", root / "catalog-v2.json")
            self.accepted_catalog(root / "catalog-v2.json")
            before = {line: fingerprint(d, root) for line, d in definitions(root).items()}
            path = "images/playwright-browser/definition.json"
            old_definition = json.loads((root / path).read_text())
            old_lock = (root / "images/playwright-browser/lines/1.58-trixie/package-lock.json").read_bytes()
            pin = {"repository": "https://github.com/xormania/uxor.git",
                   "commit": "b" * 40, "playwright_version": "1.64.0"}
            def resolve(_argv, cwd, **_kwargs):
                lock = {"packages": {"node_modules/" + name: {"version": "1.64.0", "integrity": "sha512-fixture"}
                                      for name in ("playwright", "playwright-core")}}
                (cwd / "package-lock.json").write_text(json.dumps(lock))
            with patch.object(refresh_browser.subprocess, "run", side_effect=resolve) as npm:
                self.assertTrue(refresh_browser.prepare(pin, root))
                npm.assert_called_once()
                fixture = root / "tests/fixtures/playwright/consumers/1.64-trixie.json"
                prepared = fixture.read_bytes()
                self.assertRegex(json.loads(prepared)["application_image"], r"@sha256:[a-f0-9]{64}$")
                catalog = json.loads((root / "catalog-v2.json").read_text())
                entry = dict(next(item for item in catalog["resources"] if item["identity"] == json.loads(prepared)["application_image"]))
                entry.update(version="99.0.0", identity="ghcr.io/xormania/uxor-dev@sha256:" + "a" * 64)
                catalog["resources"].append(entry)
                (root / "catalog-v2.json").write_text(json.dumps(catalog))
                self.assertFalse(refresh_browser.prepare(pin, root))
                npm.assert_called_once()
                self.assertEqual(fixture.read_bytes(), prepared)
            current = definitions(root)
            for line in before:
                self.assertEqual(fingerprint(current[line], root), before[line], line)
            self.assertEqual((root / "images/playwright-browser/lines/1.58-trixie/package-lock.json").read_bytes(), old_lock)
            self.assertEqual(current["playwright-browser/1.64-trixie"]["revision"], "1.0.0")
            payload_id = current["playwright-browser/1.64-trixie"]["build_components"]["PLAYWRIGHT_IMAGE"]
            self.assertEqual(payload_id, "playwright-1-64-payload")
            payload = json.loads((root / "images/components" / payload_id / "definition.json").read_text())
            recipe = (root / payload["dockerfile"]).read_text()
            self.assertIn("images/playwright-browser/lines/1.64-trixie/package-lock.json", recipe)
            self.assertNotIn("images/playwright-browser/lines/1.58-trixie/", recipe)
            changes = [path, "images/playwright-browser/lines/1.64-trixie/package-lock.json",
                       "tests/fixtures/playwright/consumers/1.64-trixie.json"]
            self.assertEqual(affected_lines(changes, current, root, previous_definitions={path: old_definition}),
                             ["playwright-browser/1.64-trixie"])

    def test_lock_version_mismatch_does_not_publish_a_definition_or_parity_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_build_inputs(root)
            shutil.copyfile(ROOT / "catalog-v2.json", root / "catalog-v2.json")
            self.accepted_catalog(root / "catalog-v2.json")
            definition = root / "images/playwright-browser/definition.json"
            original = definition.read_bytes()
            pin = {"repository": "https://github.com/xormania/uxor.git",
                   "commit": "b" * 40, "playwright_version": "1.64.0"}
            def wrong_lock(_argv, cwd, **_kwargs):
                (cwd / "package-lock.json").write_text(json.dumps({"packages": {
                    "node_modules/playwright": {"version": "1.58.2", "integrity": "sha512-fixture"}}}))
            with patch.object(refresh_browser.subprocess, "run", side_effect=wrong_lock), \
                    self.assertRaisesRegex(ValueError, "exact version"):
                refresh_browser.prepare(pin, root)
            self.assertEqual(definition.read_bytes(), original)
            self.assertFalse((root / "tests/fixtures/playwright/consumers/1.64-trixie.json").exists())

    def test_pr_writeback_commits_the_new_payload_closure_without_unrelated_components(self):
        real_run = subprocess.run
        real_prepare = refresh_browser.prepare
        pin = {"repository": "https://github.com/xormania/uxor.git",
               "commit": "b" * 40, "playwright_version": "1.64.0"}
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root, remote, checkout = (temporary / name for name in ("writer", "origin.git", "consumer"))

            def git(*arguments, cwd=root):
                completed = real_run(["git", *arguments], cwd=cwd, text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return completed.stdout

            git("clone", "--bare", "--shared", str(ROOT), str(remote), cwd=temporary)
            git("update-ref", "refs/heads/master", "HEAD", cwd=remote)
            git("symbolic-ref", "HEAD", "refs/heads/master", cwd=remote)
            git("clone", "--shared", str(remote), str(root), cwd=temporary)
            unrelated = root / "images/components/unrelated-canary"
            unrelated.mkdir()
            (unrelated / "Dockerfile").write_text("FROM scratch\n")
            (unrelated / "definition.json").write_text(json.dumps({
                "schema_version": 1, "id": "unrelated-canary", "purpose": "Unrelated pending input",
                "dockerfile": "images/components/unrelated-canary/Dockerfile",
                "platforms": ["linux/amd64"], "abi": "linux-amd64-trixie"}))

            def execute(argv, **kwargs):
                if argv[0] == "npm":
                    lock = {"packages": {"node_modules/" + name: {
                        "version": pin["playwright_version"], "integrity": "sha512-fixture"}
                        for name in ("playwright", "playwright-core")}}
                    (kwargs["cwd"] / "package-lock.json").write_text(json.dumps(lock))
                    return subprocess.CompletedProcess(argv, 0)
                return real_run(argv, **kwargs)

            with patch.object(refresh_browser, "ROOT", root), patch.object(writeback, "ROOT", root), \
                    patch.object(refresh_browser, "consumer_pin", return_value=pin), \
                    patch.object(refresh_browser, "prepare", side_effect=lambda value: real_prepare(value, root)), \
                    patch.object(refresh_browser.subprocess, "run", side_effect=execute), \
                    patch.object(writeback, "upsert_pr") as proposal, \
                    patch.object(sys, "argv", ["refresh_browser.py", "--pr"]), \
                    patch.dict(os.environ, {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}):
                refresh_browser.main()
            proposal.assert_called_once()
            git("clone", "--branch", "automation/browser-1.64.0", str(remote), str(checkout), cwd=temporary)
            checked = real_run([sys.executable, "scripts/library.py", "check"], cwd=checkout,
                               capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            line = definitions(checkout)["playwright-browser/1.64-trixie"]
            payload_id = line["build_components"]["PLAYWRIGHT_IMAGE"]
            payload = checkout / "images/components" / payload_id
            self.assertTrue((payload / "definition.json").is_file())
            self.assertTrue((payload / "Dockerfile").is_file())
            self.assertTrue(fingerprint(line, checkout))
            self.assertEqual(git("status", "--porcelain", cwd=checkout), "")
            self.assertFalse((checkout / "images/components/unrelated-canary").exists())
            self.assertEqual(git("status", "--porcelain").strip(), "?? images/components/unrelated-canary/")


if __name__ == "__main__":
    unittest.main()
