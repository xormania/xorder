"""Protect incremental CI behavior at the workflow's event boundary."""
import re
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validation_base
from validation_base import select_context
from xorder import model, verify as resource_verify


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/validate.yml"


def concurrency_cancels(event):
    """Evaluate the workflow's simple event expression against webhook fixtures."""
    source = WORKFLOW.read_text()
    expression = re.search(r"^  cancel-in-progress: \$\{\{ (.+) \}\}$", source, re.M)[1]

    def value(match):
        current = {"github": {"event": event}}
        for name in match[0].split("."):
            current = current.get(name, "") if isinstance(current, dict) else ""
        return repr(current)

    expression = re.sub(r"github(?:\.[a-zA-Z_][a-zA-Z_0-9]*)+", value, expression)
    return eval(expression.replace("||", " or ").replace("&&", " and "), {"__builtins__": {}})


class ValidationWorkflowTests(unittest.TestCase):
    def test_title_and_body_edits_preserve_running_behavior_checks(self):
        for changes in ({"body": {"from": "before"}}, {"title": {"from": "before"}},
                        {"title": {"from": "before"}, "body": {"from": "before"}}):
            with self.subTest(changes=changes):
                self.assertFalse(concurrency_cancels({"action": "edited", "changes": changes}))

    def test_target_branch_edits_supersede_checks_for_the_previous_target(self):
        changes = {"base": {"ref": {"from": "dev"}, "sha": {"from": "a" * 40}}}
        self.assertTrue(concurrency_cancels({"action": "edited", "changes": changes}))

    def test_new_commits_and_full_runs_supersede_obsolete_work(self):
        for event in ({"action": "synchronize"}, {"action": "opened"},
                      {"action": "reopened"}, {}):
            with self.subTest(event=event):
                self.assertTrue(concurrency_cancels(event))

    def test_all_runtime_surfaces_share_the_validated_incremental_baseline(self):
        source = WORKFLOW.read_text()
        for step in ("matrix", "resources", "application"):
            with self.subTest(step=step):
                block = re.search(r"^      - id: " + step + r"\n(.*?)(?=^      - |^  [a-z]|\Z)",
                                  source, re.M | re.S)[1]
                self.assertIn("BASE_SHA: ${{ steps.validation-base.outputs.sha }}", block)
                self.assertIn("COMPARE_HEAD: ${{ steps.validation-base.outputs.head }}", block)

    def test_repeated_metadata_is_skipped_only_for_an_identical_successful_head(self):
        source = WORKFLOW.read_text()
        lookup = source.index("      - id: validation-base\n")
        for name in ("Unit tests", "Python syntax", "Shell syntax"):
            block = re.search(r"^      - name: " + name + r"\n(.*?)(?=^      - |^  [a-z]|\Z)",
                              source, re.M | re.S)[1]
            self.assertIn("if: steps.validation-base.outputs.same_head != 'true'", block)
            self.assertLess(lookup, source.index("      - name: " + name + "\n"))
        catalog = re.search(r"^      - name: Validate catalog and immutable support policy\n(.*?)(?=^      - )",
                            source, re.M | re.S)[1]
        self.assertNotIn("\n        if:", catalog)


class IncrementalComparisonTests(unittest.TestCase):
    """Exercise real source and merge trees when the PR branch trails its base."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "image-library automation",
                    "GIT_AUTHOR_EMAIL": "image-library@users.noreply.github.com",
                    "GIT_COMMITTER_NAME": "image-library automation",
                    "GIT_COMMITTER_EMAIL": "image-library@users.noreply.github.com"}
        self.git("init", "-q")
        initial = self.commit("README.md", "example\n")
        self.git("checkout", "-q", "-b", "source")
        self.source = self.commit("images/harness-live/example.py", "source = 1\n")
        self.git("checkout", "-q", "-b", "target", initial)
        self.base = self.commit("scripts/xorder/apply.py", "base = 1\n")
        self.git("merge", "-q", "--no-ff", "source", "-m", "Test merge")
        self.merge = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env,
                                       text=True, stderr=subprocess.PIPE).strip()

    def commit(self, path, content):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        self.git("add", path)
        self.git("commit", "-q", "-m", "Test input")
        return self.git("rev-parse", "HEAD")

    def context(self, good, current, base=None):
        candidate = {"id": 123, "run_attempt": 1, "status": "completed", "head_sha": good, "conclusion": "success", "event": "pull_request",
                     "pull_requests": [{"number": 22, "base": {"sha": self.base}}]}

        def ancestor(old, new):
            return subprocess.run(["git", "merge-base", "--is-ancestor", old, new], cwd=self.root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

        tree = lambda commit: self.git("rev-parse", f"{commit}^{{tree}}")
        tested_tree = tree(good) if ancestor(self.base, good) else tree(self.merge)
        proof = {"schema_version": 1, "repository": "example/repository", "run_id": 123, "run_attempt": 1,
                 "number": 22, "event": "pull_request", "head_sha": good, "base_sha": self.base,
                 "checkout_sha": self.merge, "checkout_tree": tested_tree, "checkout_parents": [self.base, good]}
        return select_context([candidate], 22, current, base or self.base, ancestor,
                              evidence=lambda _: proof, repository="example/repository",
                              checkout_tree=tree("HEAD"), get_tree=tree)

    def resources(self, base, head=None):
        argv = ["verify", "matrix", "--base", base]
        if head is not None:
            argv += ["--head", head]
        output = io.StringIO()
        with patch.object(resource_verify, "ROOT", self.root), \
                patch.object(model, "definitions", return_value={"configuration/example": {"kind": "configuration"}}), \
                patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            resource_verify.main()
        return json.loads(output.getvalue())

    def application(self, base, head=None):
        source = WORKFLOW.read_text()
        block = re.search(r"^      - id: application\n(.*?)(?=^  application:)", source, re.M | re.S)[1]
        script = re.search(r"^          python - <<'PY'.*?\n(.*?)^          PY$", block, re.M | re.S)[1]
        env = {**self.env, "BASE_SHA": base}
        env.pop("COMPARE_HEAD", None)
        if head is not None:
            env["COMPARE_HEAD"] = head
        return subprocess.check_output([sys.executable, "-c", textwrap.dedent(script)],
                                       cwd=self.root, env=env, text=True).strip()

    def test_same_source_head_behind_the_base_ignores_already_tested_merge_inputs(self):
        context = self.context(self.source, self.source)
        self.assertEqual(context, {"sha": self.source, "head": self.source, "reused": True, "same_head": True})
        # Comparing the old source against the merge checkout wrongly includes
        # the target branch's application helper as new work.
        self.assertEqual(self.resources(context["sha"])["resource"], ["configuration/example"])
        self.assertEqual(self.application(context["sha"]), "enabled=true")
        self.assertEqual(self.resources(context["sha"], context["head"]), {"resource": [], "environment": []})
        self.assertEqual(self.application(context["sha"], context["head"]), "enabled=false")

    def test_no_tree_change_merge_cannot_hide_dropped_base_inputs(self):
        self.git("checkout", "-q", "-b", "drop-base", self.source)
        self.git("merge", "-q", "--no-ff", "-s", "ours", self.base, "-m", "Keep source tree")
        current = self.git("rev-parse", "HEAD")
        self.assertEqual(self.git("diff", "--name-only", self.source, current), "")
        context = self.context(self.source, current)
        self.assertEqual(context, {"sha": self.base, "head": "HEAD", "reused": False, "same_head": False})
        self.assertEqual(self.resources(context["sha"], context["head"])["resource"], ["configuration/example"])
        self.assertEqual(self.application(context["sha"], context["head"]), "enabled=true")

    def test_new_source_reuses_a_successful_source_that_contains_the_base(self):
        current = self.commit("images/harness-live/example.py", "source = 2\n")
        context = self.context(self.merge, current)
        self.assertEqual(context, {"sha": self.merge, "head": current, "reused": True, "same_head": False})
        self.assertEqual(self.resources(context["sha"], context["head"]), {"resource": [], "environment": []})
        self.assertEqual(self.application(context["sha"], context["head"]), "enabled=false")

    def test_recorded_merge_inputs_use_actual_parents_instead_of_the_event_base(self):
        env = {"GITHUB_REPOSITORY": "example/repository", "GITHUB_RUN_ID": "123",
               "GITHUB_RUN_ATTEMPT": "2", "PR_NUMBER": "22", "GITHUB_EVENT_NAME": "pull_request",
               "HEAD_SHA": self.source, "BASE_SHA": "a" * 40}
        with contextlib.chdir(self.root), patch.dict(os.environ, env):
            checkout = validation_base.observed_checkout(self.source)
            self.assertEqual(checkout["base_sha"], self.base)
            self.assertEqual(checkout["checkout_parents"], [self.base, self.source])
            destination = self.root / "validation-context.json"
            validation_base.record_context(destination, checkout)
        proof = json.loads(destination.read_text())
        self.assertEqual(proof["base_sha"], self.base)
        self.assertEqual(proof["event_base_sha"], "a" * 40)
        self.assertEqual(proof["checkout_sha"], self.merge)
        self.assertEqual(proof["checkout_tree"], self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(proof["run_attempt"], 2)

    def test_unexpected_checkout_parents_do_not_prove_reusable_coverage(self):
        with contextlib.chdir(self.root):
            self.assertIsNone(validation_base.observed_checkout("a" * 40)["base_sha"])
        self.git("checkout", "-q", "source")
        with contextlib.chdir(self.root):
            self.assertIsNone(validation_base.observed_checkout(self.source)["base_sha"])

    def test_malformed_archive_response_falls_back_to_full_pr_validation(self):
        candidate = {"id": 123, "run_attempt": 1, "status": "completed", "conclusion": "success",
                     "head_sha": self.source, "event": "pull_request"}
        listing = {"artifacts": [{"id": 456, "name": "validation-context-1", "expired": False, "size_in_bytes": 10}]}
        env = {"GITHUB_REPOSITORY": "example/repository", "PR_NUMBER": "22",
               "HEAD_SHA": self.source, "BASE_SHA": "a" * 40, "GITHUB_TOKEN": "test-token"}
        output = io.StringIO()
        with contextlib.chdir(self.root), patch.dict(os.environ, env), \
                patch.object(sys, "argv", ["validation_base.py", "--github-output"]), \
                patch("validation_base.api_bytes", side_effect=[
                    json.dumps({"workflow_runs": [candidate]}).encode(), json.dumps(listing).encode(), b"invalid zip"]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            validation_base.main()
        result = dict(line.split("=", 1) for line in output.getvalue().splitlines())
        self.assertEqual(result, {"sha": self.base, "head": "HEAD", "reused": "false", "same_head": "false"})


if __name__ == "__main__":
    unittest.main()
