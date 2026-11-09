"""Runtime component identities follow capability inputs, not sibling tools."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import library


class RuntimeComponentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "images", self.root / "images", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "schemas", self.root / "schemas")
        shutil.copyfile(ROOT / ".dockerignore", self.root / ".dockerignore")
        import components
        self.components = components

    def keys(self):
        return {name: self.components.build_key(name, root=self.root)
                for name in ("python-foundation", "python-matrix-interpreters", "rust-toolchain")}

    def tool_change(self, name):
        path = self.root / "images/tools.json"
        tools = json.loads(path.read_text())
        if name == "apt_indexes":
            first = next(iter(tools[name]))
            tools[name][first] = "f" * 64
        else:
            tools[name]["digest"] = "sha256:" + "f" * 64
        path.write_text(json.dumps(tools))

    def test_python_and_harness_share_the_same_actual_foundation(self):
        definitions = library.definitions(self.root)
        expected = self.components.build_key("python-foundation", root=self.root)
        for line in ("python-dev/3.14-trixie", "harness-live/trixie"):
            with self.subTest(line=line):
                inputs = self.components.image_inputs(definitions[line], root=self.root)
                self.assertEqual(inputs["PYTHON_FOUNDATION_IMAGE"]["id"], "python-foundation")
                self.assertEqual(inputs["PYTHON_FOUNDATION_IMAGE"]["key"], expected)
                recipe = (self.root / "images" / definitions[line]["family"] / "Dockerfile").read_text()
                stages = [instruction.split()[1] for instruction in recipe.splitlines()
                          if instruction.startswith("FROM ")]
                self.assertEqual(stages[-1], "${PYTHON_FOUNDATION_IMAGE}")

    def test_shared_foundation_rejects_an_independently_changed_harness_base(self):
        proof_path = ROOT / "images/components/python-foundation/verify_upstream.py"
        spec = importlib.util.spec_from_file_location("foundation_upstream_proof", proof_path)
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        foundation = self.components.build_inputs("python-foundation", root=self.root)
        actual = foundation["build_arguments"]["BASE_IMAGE"]
        marker = self.root / "upstream-image"
        marker.write_text(actual + "\n")
        current = library.definitions(self.root)["harness-live/trixie"]["base"]
        proof.verify(current["tag"] + "@" + current["digest"], marker)
        proof.verify(actual.replace(":3.14-slim-trixie@", ":descriptive-alias@"), marker)
        path = self.root / "images/harness-live/definition.json"
        changed = json.loads(path.read_text())
        changed["lines"]["trixie"]["base"]["digest"] = "sha256:" + "f" * 64
        path.write_text(json.dumps(changed))
        new_pin = library.definitions(self.root)["harness-live/trixie"]["base"]
        # A cached foundation still has the previous actual upstream. Assembly
        # must reject the independent consumer pin rather than misreport it.
        with self.assertRaisesRegex(ValueError, "upstream differs"):
            proof.verify(new_pin["tag"] + "@" + new_pin["digest"], marker)
        for family in ("python-dev", "harness-live"):
            recipe = (self.root / "images" / family / "Dockerfile").read_text()
            self.assertIn('RUN python3 /opt/xorder/components/python-foundation/verify_upstream.py "$BASE_IMAGE"', recipe)

    def test_uv_and_node_refresh_do_not_rebuild_the_python_foundation(self):
        initial = self.keys()
        self.tool_change("uv")
        changed = self.keys()
        self.assertEqual(initial["python-foundation"], changed["python-foundation"])
        self.assertEqual(initial["rust-toolchain"], changed["rust-toolchain"])
        self.assertNotEqual(initial["python-matrix-interpreters"], changed["python-matrix-interpreters"])
        self.tool_change("node")
        self.assertEqual(changed, self.keys())

    def test_debian_refresh_does_not_redownload_fixed_rust_or_matrix_tools(self):
        initial = self.keys()
        self.tool_change("apt_indexes")
        changed = self.keys()
        self.assertNotEqual(initial["python-foundation"], changed["python-foundation"])
        self.assertEqual(initial["rust-toolchain"], changed["rust-toolchain"])
        self.assertEqual(initial["python-matrix-interpreters"], changed["python-matrix-interpreters"])

    def test_matrix_pins_select_only_the_managed_interpreter_component_and_consumer(self):
        initial = self.keys()
        path = self.root / "images/python-matrix/versions.json"
        versions = json.loads(path.read_text())
        versions["3.10"] = "3.10.999"
        path.write_text(json.dumps(versions))
        changed = self.keys()
        self.assertNotEqual(initial["python-matrix-interpreters"], changed["python-matrix-interpreters"])
        self.assertEqual(initial["python-foundation"], changed["python-foundation"])
        self.assertEqual(initial["rust-toolchain"], changed["rust-toolchain"])
        paths = ["images/python-matrix/versions.json"]
        self.assertEqual(self.components.affected_components(paths, root=self.root), ["python-matrix-interpreters"])
        self.assertEqual(self.components.affected_images(paths, library.definitions(self.root), root=self.root),
                         {"python-matrix/trixie"})

    def test_harness_launch_changes_do_not_rebuild_any_runtime_component(self):
        initial = self.keys()
        path = self.root / "images/harness-live/session.sh"
        path.write_text(path.read_text() + "\n# changed launch policy\n")
        self.assertEqual(initial, self.keys())
        self.assertEqual(self.components.affected_components(["images/harness-live/session.sh"], root=self.root), [])


class RuntimeComponentProofTests(unittest.TestCase):
    def load(self, name):
        path = ROOT / "images/components" / name / "verify.py"
        spec = importlib.util.spec_from_file_location(name.replace("-", "_") + "_proof", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_foundation_verifier_rejects_missing_advertised_tool(self):
        proof = self.load("python-foundation")
        with patch.object(proof.shutil, "which", side_effect=lambda name: None if name == "psql" else "/bin/" + name):
            with self.assertRaisesRegex(RuntimeError, "omitted psql"):
                proof.main()

    def test_interpreter_verifier_rejects_wrong_version_and_missing_sqlite(self):
        proof = self.load("python-matrix-interpreters")
        for output in ("3.12.1\n3.50.0\n", "3.10.22\n"):
            with self.subTest(output=output), patch.object(proof.Path, "read_text", return_value='{"3.10":"3.10.22"}'), \
                    patch.object(proof.subprocess, "check_output", return_value=output):
                with self.assertRaisesRegex(RuntimeError, "differs from its pinned"):
                    proof.main()


if __name__ == "__main__":
    unittest.main()
