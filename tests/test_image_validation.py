"""Image CI selection and orchestration against independent dependency scenarios."""
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_library import record
import build
from library import ROOT, definitions, fingerprint
from image_validation import affected_lines, descendants, matrix


class ImageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.defs = definitions()

    def selected(self, *paths, **kwargs):
        return affected_lines(paths, self.defs, ROOT, **kwargs)

    def test_group_support_and_retention_metadata_do_not_select_image_builds(self):
        self.assertEqual(self.selected('lifecycle/release-groups.json',
                                       'lifecycle/bootstrap-group.json',
                                       'scripts/release_groups.py',
                                       'scripts/group_writeback.py',
                                       'scripts/retention.py',
                                       'scripts/publication_attempt.py',
                                       'schemas/release-groups.schema.json',
                                       '.github/workflows/release-groups.yml'), [])

    def test_child_recipe_and_fixture_skip_parent_and_siblings(self):
        for path in ("images/php-toolkit/Dockerfile", "tests/fixtures/php-toolkit/run.sh",
                     "examples/php-toolkit/validator/composer.lock"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), ["php-toolkit/8.4-trixie", "php-toolkit/8.5-trixie"])
        self.assertEqual(matrix(self.selected("tests/fixtures/php-toolkit/run.sh"), self.defs), {
            "include": [
                {"line": "php-dev/8.4-trixie", "verify_lines": ["php-toolkit/8.4-trixie"]},
                {"line": "php-dev/8.5-trixie", "verify_lines": ["php-toolkit/8.5-trixie"]},
            ]})

    def test_parent_recipe_checks_all_consuming_descendants(self):
        expected = ["php-browser/8.4-trixie", "php-browser/8.5-trixie",
                    "php-dev/8.4-trixie", "php-dev/8.5-trixie",
                    "php-serena/8.5-trixie",
                    "php-toolkit/8.4-trixie", "php-toolkit/8.5-trixie"]
        self.assertEqual(self.selected("images/php-dev/Dockerfile"), expected)
        self.assertEqual(self.selected("images/shared/php-tests.py"), sorted(expected + [
            "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie",
            "uxor-dev/8.4-trixie", "uxor-dev/8.5-trixie"]))

    def test_serena_inputs_check_only_serena_with_php85_as_a_prerequisite(self):
        for path in ("images/php-serena/Dockerfile", "images/php-serena/requirements-build.txt",
                     "images/php-serena/launch.py", "examples/serena/run.py",
                     "tests/fixtures/serena/check.py", "tests/fixtures/serena/consumer.json"):
            with self.subTest(path=path):
                selected = self.selected(path)
                self.assertEqual(selected, ["php-serena/8.5-trixie"])
                self.assertEqual(matrix(selected, self.defs), {"include": [
                    {"line": "php-dev/8.5-trixie", "verify_lines": ["php-serena/8.5-trixie"]}]})

    def test_shared_php_behavior_includes_serena(self):
        expected = sorted(line for line, d in self.defs.items()
                          if d["family"].startswith("php-") or d["family"] == "uxor-dev")
        for path in ("tests/fixtures/php/run.sh", "tests/fixtures/mutation/run.sh"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)
        self.assertEqual(self.selected("examples/php/compose.yaml"), sorted(expected + ["python-dev/3.14-trixie"]))

    def test_behavior_change_does_not_propagate_as_an_artifact_change(self):
        defs = copy.deepcopy(self.defs)
        defs["extra-profile/8.5-trixie"] = {
            "family": "extra-profile", "base": {"parent": "uxor-dev/8.5-trixie"}}
        # The added node has no Dockerfile, so inspect COPY consumers only for real families.
        with patch("image_validation.consumes", return_value=False):
            selected = affected_lines(["tests/fixtures/uxor/run.sh"], defs, ROOT)
        self.assertEqual(selected, ["uxor-dev/8.4-trixie", "uxor-dev/8.5-trixie"])
        self.assertEqual(descendants(["php-frankenphp/8.5-trixie"], defs), [
            "extra-profile/8.5-trixie", "php-frankenphp/8.5-trixie", "uxor-dev/8.5-trixie"])

    def test_one_definition_line_change_and_new_line_are_scoped(self):
        path = "images/php-dev/definition.json"
        previous = json.loads((ROOT / path).read_text())
        previous["lines"]["8.5-trixie"]["revision"] = "0.9.0"
        expected = ["php-browser/8.5-trixie", "php-dev/8.5-trixie", "php-serena/8.5-trixie", "php-toolkit/8.5-trixie"]
        self.assertEqual(self.selected(path, previous_definitions={path: previous}), expected)
        del previous["lines"]["8.5-trixie"]
        self.assertEqual(self.selected(path, previous_definitions={path: previous}), expected)
        previous["purpose"] = "A changed common contract"
        self.assertEqual(len(self.selected(path, previous_definitions={path: previous})), 7)
        # An entirely new definition has no prior value: check every authored line.
        self.assertEqual(len(self.selected(path, previous_definitions={})), 7)

    def test_tool_pins_check_exact_consumers_and_their_descendants(self):
        previous = json.loads((ROOT / "images/tools.json").read_text())
        previous["tailwind"]["sha256"] = "0" * 64
        self.assertEqual(self.selected("images/tools.json", previous_tools=previous), [
            "uxor-dev/8.4-trixie", "uxor-dev/8.5-trixie"])
        previous = json.loads((ROOT / "images/tools.json").read_text())
        previous["uv"]["digest"] = "sha256:" + "0" * 64
        self.assertEqual(self.selected("images/tools.json", previous_tools=previous), ["python-dev/3.14-trixie", "python-matrix/trixie"])

    def test_deleted_definition_has_no_current_image_target(self):
        path = "images/rust-dev/definition.json"
        previous = json.loads((ROOT / path).read_text())
        defs = {line: d for line, d in self.defs.items() if d["family"] != "rust-dev"}
        with tempfile.TemporaryDirectory() as tmp:
            selected = affected_lines([path], defs, tmp, previous_definitions={path: previous})
        self.assertEqual(matrix(selected, defs), {"include": []})

    def test_renamed_definition_checks_the_added_family(self):
        old_path, new_path = "images/rust-dev/definition.json", "images/rust-next/definition.json"
        previous = json.loads((ROOT / old_path).read_text())
        current = copy.deepcopy(previous)
        current["family"] = "rust-next"
        defs = {line: d for line, d in self.defs.items() if d["family"] != "rust-dev"}
        renamed = copy.deepcopy(self.defs["rust-dev/1.99-trixie"])
        renamed["family"] = "rust-next"
        defs["rust-next/1.99-trixie"] = renamed
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / new_path
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(current))
            selected = affected_lines([old_path, new_path], defs, tmp,
                                      previous_definitions={old_path: previous})
        self.assertEqual(matrix(selected, defs), {"include": [
            {"line": "rust-next/1.99-trixie", "verify_lines": ["rust-next/1.99-trixie"]}]})

    def test_metadata_runs_without_images_and_shared_runtime_checks_all(self):
        self.assertEqual(self.selected("README.md", "catalog.json", "scripts/release.py",
                                       "scripts/claude_prompt_clock.py",
                                       "examples/shared/failure_hooks.py", "examples/jev/failure_triage.py",
                                       "examples/jev/failure-questions.json",
                                       "tests/test_library.py", "schemas/catalog.schema.json",
                                       "schemas/definition.schema.json"), [])
        for path in ("scripts/build.py", "scripts/image_validation.py", "scripts/inventory.py",
                     "scripts/verify-image.sh", ".github/workflows/validate.yml",
                     "tests/fixtures/trust/run.sh", "tests/fixtures/native-check.c",
                     "scripts/unknown-runtime-helper.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), sorted(self.defs))
        self.assertEqual(matrix([], self.defs), {"include": []})

    def test_full_matrix_tests_each_line_once(self):
        plan = matrix(self.defs, self.defs)["include"]
        lines = [line for item in plan for line in item["verify_lines"]]
        self.assertEqual(sorted(lines), sorted(self.defs))
        self.assertEqual(len(lines), len(set(lines)))


class ImageExecutionTests(unittest.TestCase):
    parent = "php-dev/8.5-trixie"
    child = "php-toolkit/8.5-trixie"
    digest = "ghcr.io/xormania/php-dev@sha256:" + "a" * 64

    def args(self, inventory, selected=None):
        args = [self.parent, "image-library-check:dev", "--children", "--reuse-accepted",
                "--source", "candidate", "--inventory", str(inventory)]
        if selected is not None:
            args += ["--verify-lines", json.dumps(selected)]
        return args

    def test_child_check_pulls_parent_without_testing_parent_or_sibling(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(build, "reusable_artifact", side_effect=lambda line, parent: self.digest if line == self.parent else None), \
                patch.object(build.subprocess, "run") as run, patch.object(build, "build") as builder, \
                patch.object(build, "verify") as verify, \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
            build.main(self.args(Path(tmp) / "out/parent.json", [self.child]))
            run.assert_called_once_with(["docker", "pull", "--platform", "linux/amd64", self.digest], check=True)
            builder.assert_called_once_with(self.child, "image-library-check:php-toolkit", "candidate", self.digest, None)
            self.assertEqual([call.args[0] for call in verify.call_args_list], [self.child])
            parent_metrics = json.loads((Path(tmp) / "out/parent.metrics.json").read_text())
            self.assertEqual(parent_metrics["verification_status"], "prerequisite")
            self.assertNotIn("verify_seconds", parent_metrics)

    def test_missing_parent_builds_before_child_and_uses_exact_local_parent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, "reusable_artifact", return_value=None), \
                patch.object(build, "build") as builder, patch.object(build, "verify") as verify, \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
            build.main(self.args(Path(tmp) / "parent.json", [self.child]))
            self.assertEqual([call.args[0] for call in builder.call_args_list], [self.parent, self.child])
            self.assertEqual(builder.call_args_list[1].args[3], "image-library-check:dev")
            self.assertEqual([call.args[0] for call in verify.call_args_list], [self.child])

    def test_default_children_behavior_still_verifies_the_complete_tree(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, "reusable_artifact", return_value=None), \
                patch.object(build, "build"), patch.object(build, "verify") as verify, \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
            build.main(self.args(Path(tmp) / "parent.json"))
            self.assertEqual([call.args[0] for call in verify.call_args_list], [
                self.parent, "php-browser/8.5-trixie", "php-serena/8.5-trixie", self.child])

    def test_deep_descendant_prepares_only_its_ancestor_path(self):
        defs = copy.deepcopy(definitions())
        grandchild = "extra-profile/8.5-trixie"
        defs[grandchild] = {"family": "extra-profile", "base": {"parent": self.child}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, "definitions", return_value=defs), \
                patch.object(build, "reusable_artifact", return_value=None), \
                patch.object(build, "build") as builder, patch.object(build, "verify") as verify, \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
            build.main(self.args(Path(tmp) / "parent.json", [grandchild]))
            self.assertEqual([call.args[0] for call in builder.call_args_list], [self.parent, self.child, grandchild])
            self.assertEqual(builder.call_args_list[2].args[3], "image-library-check:php-toolkit")
            self.assertEqual([call.args[0] for call in verify.call_args_list], [grandchild])

    def test_selected_failure_propagates(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, "reusable_artifact", return_value=None), \
                patch.object(build, "build"), \
                patch.object(build, "verify", side_effect=subprocess.CalledProcessError(1, "verify")), \
                patch.object(build, "image_measurements", return_value={"image_size_bytes": 100}):
            with self.assertRaises(subprocess.CalledProcessError):
                build.main(self.args(Path(tmp) / "parent.json", [self.child]))

    def test_invalid_plan_fails_before_any_docker_action(self):
        for selected in ([], ["missing/line"], ["rust-dev/1.99-trixie"], [1], {}):
            with self.subTest(selected=selected), patch.object(build.subprocess, "run") as run, \
                    patch.object(build, "build") as builder:
                with self.assertRaises(SystemExit):
                    build.main(self.args("out/parent.json", selected))
                run.assert_not_called()
                builder.assert_not_called()

    def test_child_reuse_binds_the_exact_parent_and_rejects_withdrawn_records(self):
        d = definitions()[self.child]
        accepted = record(self.child, d["revision"])
        accepted["input_fingerprint"] = hashlib.sha256((fingerprint(d) + self.digest).encode()).hexdigest()
        with patch.object(build, "records", return_value=[accepted]):
            self.assertIsNotNone(build.reusable_artifact(self.child, self.digest))
            self.assertIsNone(build.reusable_artifact(self.child, "different-parent"))
            accepted["lifecycle"] = "withdrawn"
            self.assertIsNone(build.reusable_artifact(self.child, self.digest))


if __name__ == "__main__":
    unittest.main()
