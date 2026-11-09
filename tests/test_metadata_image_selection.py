"""Metadata planning avoids artifact hashing unless changed bytes are copied."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from image_validation import affected_suites


class MetadataImageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copyfile(ROOT / "schemas/component.schema.json", self.root / "schemas/component.schema.json")
        (self.root / ".dockerignore").write_text(".git\n")
        folder = self.root / "images/components/base"
        folder.mkdir(parents=True)
        (self.root / "images/tools.json").write_text("{}")
        (folder / "data").write_text("component payload")
        self.component_recipe = folder / "Dockerfile"
        self.component_recipe.write_text("FROM scratch\nCOPY images/components/base/data /data\n")
        (folder / "definition.json").write_text(json.dumps({
            "schema_version": 1, "id": "base", "purpose": "test input", "dockerfile": "images/components/base/Dockerfile",
            "platforms": ["linux/amd64"], "abi": "test", "verify": ["/bin/true"],
        }))
        app = self.root / "images/app"
        app.mkdir()
        self.image_recipe = app / "Dockerfile"
        self.image_recipe.write_text("FROM scratch\n")
        self.defs = {"app/line": {"family": "app", "line": "line", "base": {}, "platforms": ["linux/amd64"],
                                  "build_components": {"INPUT_IMAGE": "base"}}}

    def test_metadata_only_delta_does_not_hash_container_payloads(self):
        paths = ["README.md", "catalog.json", "docs/usage.md", "release-records/app/line/1.0.0.json",
                 "tests/test_example.py", "scripts/setup_checks.py", ".github/workflows/fast-checks.yml"]
        with patch("components._files_current", side_effect=AssertionError("Container payloads were hashed")):
            self.assertEqual(affected_suites(paths, self.defs, self.root), {})
            self.assertEqual(affected_suites([], self.defs, self.root), {})

    def test_component_copy_of_metadata_and_test_paths_still_checks_consumer(self):
        original = self.component_recipe.read_text()
        for name in ("README.md", "tests/test_example.py", "scripts/setup_checks.py"):
            with self.subTest(name=name):
                source = self.root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("copied payload")
                self.component_recipe.write_text(original + f"COPY {name} /extra\n")
                self.assertEqual(affected_suites([name], self.defs, self.root), {"app/line": ["full"]})

    def test_component_recipe_in_metadata_directory_still_checks_consumer(self):
        recipe = self.root / "docs/component.Dockerfile"
        recipe.parent.mkdir()
        recipe.write_text(self.component_recipe.read_text())
        manifest = self.root / "images/components/base/definition.json"
        data = json.loads(manifest.read_text())
        data["dockerfile"] = "docs/component.Dockerfile"
        manifest.write_text(json.dumps(data))
        self.assertEqual(affected_suites(["docs/component.Dockerfile"], self.defs, self.root), {"app/line": ["full"]})

    def test_image_copy_of_metadata_path_still_checks_consumer(self):
        for name in ("README.md", "tests/test_example.py", "scripts/setup_checks.py"):
            with self.subTest(name=name):
                source = self.root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("copied image payload")
                self.image_recipe.write_text(f"FROM scratch\nCOPY {name} /extra\n")
                self.assertEqual(affected_suites([name], self.defs, self.root), {"app/line": ["full"]})

    def test_partial_fixture_copied_by_component_requires_full_readiness(self):
        original = self.component_recipe.read_text()
        for family, name in (("playwright-browser", "tests/fixtures/trust/clients.sh"),
                             ("harness-live", "tests/fixtures/native-check.c")):
            with self.subTest(family=family):
                source = self.root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("copied fixture")
                self.component_recipe.write_text(original + f"COPY {name} /fixture\n")
                target = self.root / "images" / family
                target.mkdir()
                (target / "Dockerfile").write_text("FROM scratch\n")
                definition = {**self.defs["app/line"], "family": family}
                self.assertEqual(affected_suites([name], {family + "/line": definition}, self.root),
                                 {family + "/line": ["full"]})

    def test_shared_and_unknown_runtime_helpers_still_check_images(self):
        for path in ("scripts/artifact_identity.py", "scripts/components.py", "scripts/unknown-runtime.py",
                     "schemas/component.schema.json", ".github/workflows/validate.yml"):
            with self.subTest(path=path):
                self.assertEqual(affected_suites([path], self.defs, self.root), {"app/line": ["full"]})


if __name__ == "__main__":
    unittest.main()
