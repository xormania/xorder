"""Runtime workflow ownership keeps unrelated resource verification out of CI."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from xorder import model, verify


class ResourceWorkflowScopeTests(unittest.TestCase):
    def setUp(self):
        self.definitions = {
            "binary/composer": {"kind": "binary"},
            "configuration/editor": {"kind": "configuration"},
            "context/guidance": {"kind": "context"},
            "environment/devenv": {"kind": "environment"},
        }
        self.resources = ["binary/composer", "configuration/editor", "context/guidance"]

    def test_each_reusable_workflow_selects_only_its_resource_owner(self):
        expected = {
            "images": [], "resources": self.resources, "environments": ["environment/devenv"],
            "application": [], "xorchestrate": [],
        }
        for owner, selected in expected.items():
            with self.subTest(owner=owner):
                path = f".github/workflows/validate-{owner}.yml"
                self.assertEqual(verify.affected([path], self.definitions), selected)

    def test_workflow_ownership_is_exact_and_retains_existing_unknown_behavior(self):
        for path in (".github/workflows/unknown-runtime.yml", ".github/workflows/validate-resources-extra.yml",
                     ".github/workflows/validate-environments.yml.bak"):
            with self.subTest(path=path):
                self.assertEqual(verify.affected([path], self.definitions), [])

    def test_hub_and_shared_selection_helpers_keep_every_resource_selected(self):
        for path in (".github/workflows/validate.yml", ".github/workflows/publish.yml",
                     "scripts/xorder/verify.py", "scripts/xorder/model.py"):
            with self.subTest(path=path):
                self.assertEqual(verify.affected([path], self.definitions), sorted(self.definitions))

    def test_mixed_owner_and_resource_edits_combine_their_required_checks(self):
        for paths, selected in (
            ([".github/workflows/validate-resources.yml", ".github/workflows/validate-environments.yml"],
             sorted(self.definitions)),
            ([".github/workflows/validate-images.yml", "artifacts/environment/devenv/definition.json"],
             ["environment/devenv"]),
            ([".github/workflows/validate-application.yml", "artifacts/binary/composer/definition.json"],
             ["binary/composer"]),
            ([".github/workflows/validate-xorchestrate.yml", "tests/fixtures/artifacts/application/check.py"],
             ["configuration/editor", "context/guidance"]),
        ):
            with self.subTest(paths=paths):
                self.assertEqual(verify.affected(paths, self.definitions), selected)

    def matrix(self, root, *arguments):
        output = io.StringIO()
        with patch.object(verify, "ROOT", root), \
                patch.object(model, "definitions", return_value=self.definitions), \
                patch.object(sys, "argv", ["verify", "matrix", *arguments]), contextlib.redirect_stdout(output):
            verify.main()
        return json.loads(output.getvalue())

    def test_manual_full_selection_keeps_resources_and_environments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = {"resource": self.resources, "environment": ["environment/devenv"]}
            self.assertEqual(self.matrix(root, "--all"), expected)
            self.assertEqual(self.matrix(root), expected)

    def test_resource_matrix_uses_the_explicit_source_delta_and_reuses_unchanged_heads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.test",
                           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.test"}

            def git(*arguments):
                return subprocess.check_output(["git", *arguments], cwd=root, env=environment,
                                               text=True, stderr=subprocess.PIPE).strip()

            def commit(path):
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text("workflow input\n", encoding="utf-8")
                git("add", path)
                git("commit", "-qm", "Fixture input")
                return git("rev-parse", "HEAD")

            git("init", "-q")
            base = commit("README.md")
            resources = commit(".github/workflows/validate-resources.yml")
            environments = commit(".github/workflows/validate-environments.yml")
            self.assertEqual(self.matrix(root, "--base", base, "--head", resources),
                             {"resource": self.resources, "environment": []})
            self.assertEqual(self.matrix(root, "--base", resources, "--head", environments),
                             {"resource": [], "environment": ["environment/devenv"]})
            self.assertEqual(self.matrix(root, "--base", base, "--head", environments),
                             {"resource": self.resources, "environment": ["environment/devenv"]})
            self.assertEqual(self.matrix(root, "--base", environments, "--head", environments),
                             {"resource": [], "environment": []})


if __name__ == "__main__":
    unittest.main()
