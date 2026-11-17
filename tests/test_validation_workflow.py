"""Protect incremental CI behavior at the workflow's event boundary."""
import re
import contextlib
import io
import importlib.util
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


class NativeAcceptanceProcessTests(unittest.TestCase):
    def test_timeout_allows_runner_to_clean_up_its_separate_child_session(self):
        helper = WORKFLOW.parents[2] / "tests/fixtures/xorchestrate-runner/acceptance.py"
        specification = importlib.util.spec_from_file_location("native_acceptance", helper)
        acceptance = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(acceptance)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker, child_id = root / "cleaned", root / "child.pid"
            program = root / "runner.py"
            program.write_text(textwrap.dedent("""\
                import os,signal,subprocess,sys,time
                from pathlib import Path
                child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
                def stop(_signum,_frame):
                    os.killpg(child.pid,signal.SIGTERM)
                    child.wait(timeout=2)
                    Path(sys.argv[1]).write_text('cleaned')
                    print('cleanup complete',flush=True)
                    raise SystemExit(0)
                signal.signal(signal.SIGTERM,stop)
                Path(sys.argv[2]).write_text(str(child.pid))
                while True:
                    time.sleep(1)
                """))
            evidence = {}
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    acceptance.bounded_command([sys.executable, str(program), str(marker), str(child_id)],
                                               os.environ.copy(), evidence, timeout=1)
                self.assertEqual(marker.read_text(), "cleaned")
                self.assertFalse((Path("/proc") / child_id.read_text()).exists())
                self.assertEqual(evidence["cleanup"], "passed")
                self.assertIn("cleanup complete", evidence["stdout_tail"])
            finally:
                if child_id.exists():
                    try:
                        os.kill(int(child_id.read_text()), 9)
                    except ProcessLookupError:
                        pass


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
        for step in ("matrix", "resources", "application", "xorchestrate"):
            with self.subTest(step=step):
                block = re.search(r"^      - id: " + step + r"\n(.*?)(?=^      - |^  [a-z]|\Z)",
                                  source, re.M | re.S)[1]
                self.assertIn("BASE_SHA: ${{ steps.validation-base.outputs.sha }}", block)
                self.assertIn("COMPARE_HEAD: ${{ steps.validation-base.outputs.head }}", block)

    def test_repeated_metadata_is_skipped_only_for_an_identical_successful_head(self):
        source = WORKFLOW.read_text()
        # The job-level proof now covers the unit and both syntax checks together.
        units = re.search(r"^  unit-tests:\n(.*?)(?=^  [a-z]|\Z)", source, re.M | re.S)[1]
        self.assertIn("needs: [metadata, fast-checks]", units)
        self.assertIn("if: needs.metadata.outputs.same_head != 'true'", units)
        self.assertIn("same_head: ${{ steps.validation-base.outputs.same_head }}", source)
        for name in ("Unit tests", "Python syntax", "Shell syntax"):
            with self.subTest(step=name):
                block = re.search(r"^      - name: " + name + r"\n(.*?)(?=^      - |\Z)", units, re.M | re.S)[1]
                self.assertNotRegex(block, r"(?m)^        if:")
        catalog = re.search(r"^      - name: Validate catalog and immutable support policy\n(.*?)(?=^      - )",
                            source, re.M | re.S)[1]
        self.assertNotIn("\n        if:", catalog)

    def test_native_consumer_is_read_only_and_required_when_selected(self):
        source = WORKFLOW.read_text()
        caller = re.search(r"^  native-xorchestrate:\n(.*?)(?=^  [a-z]|\Z)", source, re.M | re.S)[1]
        self.assertIn("if: needs.metadata.outputs.has_xorchestrate == 'true'", caller)
        self.assertIn("uses: ./.github/workflows/validate-xorchestrate.yml", caller)
        runtime = WORKFLOW.with_name("validate-xorchestrate.yml").read_text()
        self.assertIn("persist-credentials: false", runtime)
        self.assertIn("permissions:\n  contents: read", runtime)
        self.assertNotIn("github.token", runtime)
        self.assertIn("steps.consumer-baseline.outputs.python", runtime)
        self.assertIn("steps.consumer-baseline.outputs.uv", runtime)
        aggregate = source.split("  checks:\n", 1)[1]
        self.assertIn("needs.native-xorchestrate.result", aggregate)
        self.assertIn('"$XORCHESTRATE" == skipped && "$XORCHESTRATE_SELECTED" == false', aggregate)

    def test_native_consumer_passes_the_managed_interpreter_to_preparation(self):
        source = WORKFLOW.with_name("validate-xorchestrate.yml").read_text()
        job = re.search(r"^  native-xorchestrate:\n(.*?)(?=^  [a-z]|\Z)", source, re.M | re.S)[1]
        managed = re.search(r"^      - id: consumer-python\n(.*?)(?=^      - )", job, re.M | re.S)[1]
        exercise = re.search(r"^      - name: Exercise online preparation.*?\n(.*?)(?=^      - )", job, re.M | re.S)[1]
        self.assertIn("BASELINE_PYTHON: ${{ steps.consumer-baseline.outputs.python }}", managed)
        self.assertIn("uv python install --no-bin", managed)
        self.assertIn("uv python find --managed-python --no-project", managed)
        self.assertNotIn("--upgrade", managed)
        self.assertIn("ACCEPTANCE_PYTHON: ${{ steps.consumer-python.outputs.python }}", exercise)
        script = textwrap.dedent(exercise.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "python"
            output = root / "args.json"
            executable.write_text("#!" + sys.executable + "\nimport json,os,sys\n"
                                  "open(os.environ['CAPTURE_ARGS'],'w').write(json.dumps(sys.argv[1:]))\n")
            executable.chmod(0o755)
            managed_python = str(root / "owned-python/bin/python3.12")
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "CAPTURE_ARGS": str(output), "ACCEPTANCE_PYTHON": managed_python,
                   "CONSUMER_PATH": str(root / "consumer"), "CONSUMER_REVISION": "a" * 40,
                   "ACCEPTANCE_RUNTIME": str(root / "runtime")}
            subprocess.run(["bash", "-e", "-c", script], env=env, check=True)
            arguments = json.loads(output.read_text())
            self.assertEqual(arguments[arguments.index("--python") + 1], managed_python)


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

    def native_xorchestrate(self, base, head):
        source = WORKFLOW.read_text()
        block = re.search(r"^      - id: xorchestrate\n(.*?)(?=^      - |^  [a-z]|\Z)", source, re.M | re.S)[1]
        script = re.search(r"^          python - <<'PY'.*?\n(.*?)^          PY$", block, re.M | re.S)[1]
        return subprocess.check_output([sys.executable, "-c", textwrap.dedent(script)], cwd=self.root,
                                       env={**self.env, "BASE_SHA": base, "COMPARE_HEAD": head}, text=True).strip()

    def test_native_consumer_runs_for_its_inputs_without_docs_only_reruns(self):
        previous = self.merge
        for path, expected in (("docs/xorchestrate.md", False),
                               ("examples/xorchestrate/runner.py", True),
                               ("examples/xorchestrate/native.py", True),
                               ("tests/fixtures/xorchestrate-runner/acceptance.py", True),
                               ("tests/test_xorchestrate_runner.py", True),
                               (".github/workflows/validate.yml", True),
                               (".github/workflows/validate-xorchestrate.yml", True),
                               (".github/workflows/validate-images.yml", False),
                               ("examples/other/runner.py", False)):
            with self.subTest(path=path):
                current = self.commit(path, "changed input\n")
                self.assertEqual(self.native_xorchestrate(previous, current), "enabled=" + str(expected).lower())
                self.assertEqual(self.native_xorchestrate(current, current), "enabled=false")
                previous = current

    def test_application_workflow_changes_select_only_the_application_surface(self):
        current = self.commit(".github/workflows/validate-application.yml", "application recipe\n")
        self.assertEqual(self.application(self.merge, current), "enabled=true")
        self.assertEqual(self.native_xorchestrate(self.merge, current), "enabled=false")

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
               "HEAD_SHA": self.source, "BASE_SHA": "a" * 40, "GITHUB_TOKEN": "test-token"}  # nosec B105 # synthetic credential test canary
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
