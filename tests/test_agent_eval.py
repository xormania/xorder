"""Hermetic evaluation-runner contracts; these doubles are not live-agent evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from jsonschema.exceptions import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agent_eval


class AgentEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.adapter = self.folder / "adapter.json"
        self.source = agent_eval.source_snapshot(agent_eval.ROOT, "HEAD")
        self.scenario = agent_eval.ROOT / "tests/scenarios/url-discovery.json"
        self.resource = agent_eval.resource_for(agent_eval.read_json(self.scenario), self.source)

    def write_adapter(self, script):
        executable = self.folder / "controlled-adapter.py"
        executable.write_text(script)
        self.adapter.write_text(json.dumps({"name": "controlled-test-double", "harness": "test-double",
                                           "model": "no-model", "command": [sys.executable, str(executable), "{workspace}"],
                                           "version_command": [sys.executable, "-c", "print('controlled-test-double 1.0')"]}))

    def evidence_script(self):
        result = {"resource_id": self.resource["id"], "identity": self.resource["identity"],
                  "version": self.resource["version"], "documentation": self.resource["documentation"],
                  "readiness_command": ["bash", "scripts/verify-image.sh", self.resource["id"][6:], self.resource["identity"]]}
        files = {"catalog-v2.json": self.source["blob"]("catalog-v2.json").decode(),
                 "README.md": self.source["blob"]("README.md").decode(),
                 "usage.md": self.source["blob"](self.resource["documentation"]).decode()}
        return ("import json,sys,subprocess\nfrom pathlib import Path\nw=Path(sys.argv[1])\n"
                "files=" + repr(files) + "\nfor name,content in files.items(): (w/'evidence'/name).write_text(content)\n"
                "(w/'result.json').write_text(" + repr(json.dumps(result)) + ")\n")

    def run_eval(self, scenario=None, timeout=None):
        return agent_eval.run(scenario or self.scenario, self.adapter, self.folder / "observation.json", timeout=timeout)

    def test_exact_selection_and_downloaded_source_have_independent_postchecks(self):
        self.write_adapter(self.evidence_script())
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "pass")
        self.assertEqual(observation["source"]["commit"], self.source["commit"])
        self.assertEqual(observation["harness"]["version"], "controlled-test-double 1.0")
        self.assertIsNone(observation["harness"]["model_observed"])
        self.assertIsNone(observation["metrics"]["download_bytes"])
        self.assertEqual(observation["cleanup"]["process_group"], "terminated")

    def test_agent_claim_of_pass_does_not_make_an_observation_pass(self):
        self.write_adapter("print('Everything passed')\n")
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "fail")
        self.assertEqual(observation["reason"], "missing-or-invalid-task-evidence")

    def test_moving_tag_and_wrong_downloaded_content_fail(self):
        self.write_adapter(self.evidence_script() + "r=json.loads((w/'result.json').read_text()); r['identity']='ghcr.io/xormania/php-dev:latest'; (w/'result.json').write_text(json.dumps(r)); (w/'evidence/usage.md').write_text('made up usage')\n")
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "fail")
        failed = {item["name"] for item in observation["checks"] if not item["passed"]}
        self.assertEqual(failed, {"available-exact-selection", "downloaded-usage.md"})

    def test_uninstalled_harness_is_indeterminate(self):
        self.adapter.write_text(json.dumps({"name": "unavailable", "harness": "absent", "model": "not-observed",
                                           "command": ["/absent-xorder-harness"], "version_command": ["/absent-xorder-harness", "--version"]}))
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "indeterminate")
        self.assertIsNone(observation["execution"])

    def test_controlled_missing_engine_reports_blocker_without_a_pull(self):
        self.write_adapter(self.evidence_script() + "subprocess.run(['docker','info'],check=False)\nr=json.loads((w/'result.json').read_text()); r.update(status='blocked',blocker='docker-engine',next_command=['docker','info']); (w/'result.json').write_text(json.dumps(r))\n")
        observation = self.run_eval(agent_eval.ROOT / "tests/scenarios/missing-prerequisite.json")
        self.assertEqual(observation["outcome"], "pass")
        self.assertIn("engine-checked-before-pull", {item["name"] for item in observation["checks"]})

    def test_attempted_pull_in_blocked_scenario_fails(self):
        self.write_adapter(self.evidence_script() + "subprocess.run(['docker','info'],check=False); subprocess.run(['docker','pull','a-moving-tag'],check=False)\nr=json.loads((w/'result.json').read_text()); r.update(status='blocked',blocker='docker-engine',next_command=['docker','info']); (w/'result.json').write_text(json.dumps(r))\n")
        observation = self.run_eval(agent_eval.ROOT / "tests/scenarios/missing-prerequisite.json")
        self.assertEqual(observation["outcome"], "fail")

    def test_global_options_and_unknown_invocations_cannot_hide_a_pull(self):
        for case, arguments in enumerate((["--context", "example", "pull", "a-moving-tag"],
                          ["--host=tcp://engine:2375", "image", "pull", "a-moving-tag"],
                          ["--unrecognized-option", "value", "info"])):
            with self.subTest(arguments=arguments):
                self.write_adapter(self.evidence_script() + "subprocess.run(['docker','info'],check=False); subprocess.run(['docker',*" + repr(arguments) + "],check=False)\nr=json.loads((w/'result.json').read_text()); r.update(status='blocked',blocker='docker-engine',next_command=['docker','info']); (w/'result.json').write_text(json.dumps(r))\n")
                observation = agent_eval.run(agent_eval.ROOT / "tests/scenarios/missing-prerequisite.json", self.adapter,
                                             self.folder / ("observation-" + str(case) + ".json"))
                self.assertEqual(observation["outcome"], "fail")
                self.assertFalse(next(item["passed"] for item in observation["checks"] if item["name"] == "engine-checked-before-pull"))

    def test_global_options_are_parsed_before_readonly_commands(self):
        self.assertEqual(agent_eval.docker_operation(["--context", "example", "info"]), "info")
        self.assertEqual(agent_eval.docker_operation(["--debug=true", "--host=tcp://engine:2375", "info"]), "info")
        self.assertEqual(agent_eval.docker_operation(["info", "--help"]), "help")
        self.assertEqual(agent_eval.docker_operation(["info", "--format", "{{json .}}"]), "info")
        self.assertIsNone(agent_eval.docker_operation(["--context"]))
        self.assertIsNone(agent_eval.docker_operation(["info", "--unknown"]))

    def test_timeout_kills_background_child_in_same_process_group(self):
        marker = self.folder / "escaped.txt"
        child = "import time; from pathlib import Path; time.sleep(0.6); Path(" + repr(str(marker)) + ").write_text('escaped')"
        self.write_adapter("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(20)\n")
        observation = self.run_eval(timeout=0.1)
        self.assertEqual(observation["reason"], "scenario-deadline-exceeded")
        self.assertTrue(observation["execution"]["timed_out"])
        time.sleep(0.7)
        self.assertFalse(marker.exists())

    def test_output_is_bounded_hashed_and_not_saved_or_printed(self):
        secret = "xorder-private-test-value"
        self.write_adapter(self.evidence_script() + "print(" + repr(secret) + "); print('a'*2000000)\n")
        observation = self.run_eval()
        self.assertGreater(observation["execution"]["output"][0]["bytes"], 2000000)
        self.assertNotIn(secret, json.dumps(observation))
        result = agent_eval.command([sys.executable, "-c", "print('b'*2000000)"], self.folder, dict(os.environ), 10)
        self.assertLessEqual(len(result["stdout"]), 16384)

    def test_redirected_evidence_directory_is_rejected(self):
        outside = self.folder / "outside"
        outside.mkdir()
        self.write_adapter(self.evidence_script() + "import shutil\nshutil.copytree(w/'evidence'," + repr(str(outside)) + ",dirs_exist_ok=True); shutil.rmtree(w/'evidence'); (w/'evidence').symlink_to(" + repr(str(outside)) + ",target_is_directory=True)\n")
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "fail")

    def test_schema_validation_does_not_accept_empty_pass(self):
        self.write_adapter(self.evidence_script())
        observation = self.run_eval()
        observation["checks"] = []
        with self.assertRaisesRegex(ValueError, "independent"):
            agent_eval.validate_observation(observation)

    def test_schema_formats_reject_invalid_timestamps_and_source_uri(self):
        self.write_adapter(self.evidence_script())
        valid = self.run_eval()
        for field, invalid in (("started_at", "yesterday"), ("finished_at", "2026-10-99T12:00:00Z")):
            with self.subTest(field=field):
                value = copy.deepcopy(valid)
                value[field] = invalid
                with self.assertRaises(ValidationError):
                    agent_eval.validate_observation(value)
        value = copy.deepcopy(valid)
        value["source"]["url"] = "not a URI/tree/" + value["source"]["commit"]
        with self.assertRaises(ValidationError):
            agent_eval.validate_observation(value)

    def test_warm_reuse_requires_private_copies_and_excludes_runtime_state(self):
        import shutil
        workspace = self.folder / "seed-task"
        workspace.mkdir()
        context = {"nonce": "c" * 32, "seed_source_file": "examples/uxor/seed.py"}
        scenario = agent_eval.read_json(agent_eval.ROOT / "tests/scenarios/warm-reuse.json")
        agent_eval.prepare(scenario, workspace, context, dict(os.environ))
        for relative in ("demo/vendor", "node_modules"):
            shutil.copytree(workspace / "donor" / relative, workspace / "receiver" / relative)
        source = dict(self.source, blob=lambda _: b"controlled-source-helper\n")
        for name in ("scripts/xr.py", context["seed_source_file"]):
            path = workspace / "checkout" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source["blob"](name))
        with patch.object(agent_eval, "discovered", side_effect=lambda *_: ([{"name": "selection", "passed": True}], {})):
            self.assertTrue(all(item["passed"] for item in agent_eval.postchecks(scenario, workspace, source, self.resource, context, dict(os.environ))))
            donor = workspace / "donor/demo/vendor/prepared.txt"
            receiver = workspace / "receiver/demo/vendor/prepared.txt"
            receiver.unlink()
            os.link(donor, receiver)
            checks = agent_eval.postchecks(scenario, workspace, source, self.resource, context, dict(os.environ))
            self.assertTrue(next(item["passed"] for item in checks if item["name"] == "reused-demo/vendor/prepared.txt"))
            self.assertFalse(next(item["passed"] for item in checks if item["name"] == "private-copy-demo/vendor/prepared.txt"))
            receiver.unlink()
            checks = agent_eval.postchecks(scenario, workspace, source, self.resource, context, dict(os.environ))
            self.assertFalse(next(item["passed"] for item in checks if item["name"] == "private-copy-demo/vendor/prepared.txt"))
            shutil.copy2(donor, receiver)
            shutil.copytree(workspace / "donor/demo/var", workspace / "receiver/demo/var")
            self.assertFalse(all(item["passed"] for item in agent_eval.postchecks(scenario, workspace, source, self.resource, context, dict(os.environ))))

    def test_existing_observation_is_never_overwritten(self):
        self.write_adapter(self.evidence_script())
        output = self.folder / "observation.json"
        output.write_text("keep original")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_eval()
        self.assertEqual(output.read_text(), "keep original")

    def test_failed_adapter_without_task_evidence_is_indeterminate(self):
        self.write_adapter("raise SystemExit(7)\n")
        observation = self.run_eval()
        self.assertEqual(observation["outcome"], "indeterminate")
        self.assertEqual(observation["reason"], "adapter-exited-unsuccessfully")

    def test_version_probe_redacts_known_secret_values(self):
        self.assertEqual(agent_eval.safe_version(b"harness 1.0 private-value", {"API_KEY": "private-value"}),
                         "harness 1.0 [redacted]")

    def test_first_task_postcheck_inspects_the_actual_container_identity(self):
        workspace = self.folder / "task"
        workspace.mkdir()
        context = {"run_id": "a" * 32, "nonce": "b" * 32, "container_name": "xorder-eval-test"}
        env = dict(os.environ)
        scenario = agent_eval.read_json(agent_eval.ROOT / "tests/scenarios/first-task.json")
        agent_eval.prepare(scenario, workspace, context, env)
        good = {"Config": {"Image": self.resource["identity"], "Labels": {"xorder.agent-eval": context["run_id"]},
                           "Cmd": ["php", "/evaluation/task.php"], "Entrypoint": ["dev-entrypoint"]},
                "State": {"Status": "exited", "ExitCode": 0},
                "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True},
                "Mounts": [{"Source": str(workspace / "fixture"), "Destination": "/evaluation", "RW": False}]}
        good["Config"]["User"] = "1000:1000"
        image = {"Config": {"Entrypoint": ["dev-entrypoint"]}, "Architecture": "amd64", "Os": "linux"}
        with patch.object(agent_eval, "discovered", return_value=([{ "name": "selection", "passed": True}], {})), \
             patch.object(agent_eval, "docker_json", side_effect=[[good], [image], {"nonce": context["nonce"], "requirements_met": True}]):
            self.assertTrue(all(item["passed"] for item in agent_eval.postchecks(scenario, workspace, self.source, self.resource, context, env)))
        wrong = copy.deepcopy(good)
        wrong["Config"]["Image"] = "a-moving-tag"
        with patch.object(agent_eval, "discovered", return_value=([{ "name": "selection", "passed": True}], {})), \
             patch.object(agent_eval, "docker_json", side_effect=[[wrong], [image], {"nonce": context["nonce"], "requirements_met": True}]):
            self.assertFalse(all(item["passed"] for item in agent_eval.postchecks(scenario, workspace, self.source, self.resource, context, env)))


if __name__ == "__main__":
    unittest.main()
