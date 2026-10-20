"""Matrix identity, SQLite behavior and scoped consumer validation."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from image_validation import affected_lines, matrix
from library import ROOT, definitions, validate_inventory
from test_library import record


class PythonMatrixTests(unittest.TestCase):
    def test_matrix_recipe_and_fixture_have_exact_parent_prerequisite(self):
        defs = definitions()
        for path in ("images/python-matrix/Dockerfile", "images/python-matrix/versions.json",
                     "tests/fixtures/python-matrix/check.py", "tests/fixtures/python-matrix/consumer.json"):
            with self.subTest(path=path):
                selected = affected_lines([path], defs, ROOT)
                self.assertEqual(selected, ["python-matrix/trixie"])
                self.assertEqual(matrix(selected, defs), {"include": [{
                    "line": "python-dev/3.14-trixie", "verify_lines": ["python-matrix/trixie"]}]})

    def test_measured_inventory_requires_every_interpreter_sqlite_and_tmux(self):
        definition = definitions()["python-matrix/trixie"]
        inventory = record("python-matrix/trixie")["platforms"][0]["inventory"]
        validate_inventory(definition, inventory)
        for mutation in ("missing-interpreter", "wrong-python", "missing-sqlite", "wrong-tmux"):
            changed = copy.deepcopy(inventory)
            if mutation == "missing-interpreter":
                del changed["interpreters"]["3.10"]
            elif mutation == "wrong-python":
                changed["interpreters"]["3.12"]["version"] = "3.14.1"
            elif mutation == "missing-sqlite":
                changed["interpreters"]["3.14"]["sqlite_version"] = ""
            else:
                changed["tools"]["tmux"] = "tmux 2.9"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                validate_inventory(definition, changed)

    def test_sqlite_behavior_fixture_runs_on_host_interpreter(self):
        path = ROOT / "tests/fixtures/python-matrix/run.py"
        spec = importlib.util.spec_from_file_location("matrix_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        line = ".".join(map(str, sys.version_info[:2]))
        facts = module.sqlite_check(line)
        self.assertIn("uri-read-only-wal", facts["checks"])
        with self.assertRaises(RuntimeError):
            module.sqlite_check("0.0")


if __name__ == "__main__":
    unittest.main()
