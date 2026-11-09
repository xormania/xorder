"""Matrix identity, SQLite behavior and scoped consumer validation."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from image_validation import affected_lines, matrix
from library import ROOT, definitions, validate_inventory
from test_library import record


class PythonMatrixTests(unittest.TestCase):
    def test_matrix_recipe_and_fixture_have_exact_parent_prerequisite(self):
        defs = definitions()
        for path in ("images/python-matrix/Dockerfile", "images/python-matrix/versions.json",
                     "images/python-matrix/pip-bootstrap.json", "images/python-matrix/install.py",
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


class PipBootstrapTests(unittest.TestCase):
    def test_verified_replacement_preserves_other_bootstrap_packages(self):
        self.exercise()

    def test_tampered_replacement_is_rejected_before_any_bootstrap_change(self):
        self.exercise(tamper="replacement")

    def test_unexpected_upstream_bootstrap_is_rejected_before_any_change(self):
        for target in ("module", "original"):
            with self.subTest(target=target):
                self.exercise(tamper=target)

    def exercise(self, tamper=None):
        path = ROOT / "images/python-matrix/install.py"
        spec = importlib.util.spec_from_file_location("matrix_installer", path)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        digest = lambda value: hashlib.sha256(value).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "ensurepip/_bundled"
            bundle.mkdir(parents=True)
            module = bundle.parent / "__init__.py"
            module_bytes = b'_PIP_VERSION = "1.0"\n# preserve other distributor code\n'
            module.write_bytes(module_bytes)
            old = bundle / "pip-1.0-py3-none-any.whl"
            old.write_bytes(b"original pip wheel")
            other = bundle / "setuptools-1.0-py3-none-any.whl"
            other.write_bytes(b"preserved setuptools")
            wheel = root / "pip-2.0-py3-none-any.whl"
            wheel.write_bytes(b"verified replacement")
            pin = {"version": "2.0", "sha256": digest(wheel.read_bytes())}
            original = {"version": "1.0", "module_sha256": digest(module_bytes),
                        "wheel_sha256": digest(old.read_bytes())}
            targets = {"replacement": wheel, "module": module, "original": old}
            if tamper:
                targets[tamper].write_bytes(targets[tamper].read_bytes() + b"tampered")
                before = {p: p.read_bytes() for p in (module, old, other)}
                with self.assertRaisesRegex(RuntimeError, "Unexpected Python bootstrap input"):
                    installer.replace_pip_bootstrap(module, wheel, pin, original)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertFalse((bundle / wheel.name).exists())
            else:
                installer.replace_pip_bootstrap(module, wheel, pin, original)
                self.assertEqual(module.read_bytes(), module_bytes.replace(b'"1.0"', b'"2.0"'))
                self.assertEqual((bundle / wheel.name).read_bytes(), wheel.read_bytes())
                self.assertFalse(old.exists())
                self.assertEqual(other.read_bytes(), b"preserved setuptools")


if __name__ == "__main__":
    unittest.main()
