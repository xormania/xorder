"""Private component reuse authenticates only explicit repository PR reads."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import components
import test_components


class ComponentReadAuthTests(unittest.TestCase):
    def setUp(self):
        fixture = test_components.ComponentTests("test_non_build_metadata_preserves_key_but_abi_changes_it")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.key = components.build_key("base", self.root)
        self.labels = json.dumps({"io.xorder.component.key": self.key, "io.xorder.component.id": "base"})

    def environment(self, head="xormania/xorder", opt_in="1"):
        path = self.root / (head.replace("/", "-") + ".json")
        path.write_text(json.dumps({"repository": {"full_name": "xormania/xorder"},
                                    "pull_request": {"head": {"repo": {"full_name": head}}}}))
        return {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REF": "refs/pull/106/merge", "GITHUB_REPOSITORY": "xormania/xorder",
                "GITHUB_EVENT_PATH": str(path), "XORDER_COMPONENTS_READ_AUTH": opt_in}

    def test_repository_pr_reuses_private_donor_with_pull_only_auth(self):
        with patch.object(components, "resolve", return_value={"digest": "sha256:" + "b" * 64}) as resolve, \
                patch.object(components, "_run") as run, \
                patch.object(components.subprocess, "check_output", return_value=self.labels):
            refs = components.prepare(["base"], root=self.root, env=self.environment())
        resolve.assert_called_once_with(components.reference("base", self.root), authenticated=True, pull_only=True)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["docker", "pull", "--platform", "linux/amd64", refs["base"]])
        self.assertFalse(any(command[:2] == ["docker", "push"] for command in commands))
        self.assertFalse(any(command[:3] == ["docker", "buildx", "build"] for command in commands))

    def test_unavailable_optional_cache_falls_back_without_registry_exports(self):
        environments = [({}, False), (self.environment("someone/fork"), False),
                        (self.environment(opt_in="0"), False),
                        (dict(self.environment(), GITHUB_EVENT_NAME="pull_request_target"), False),
                        (self.environment(), True)]
        for environment, authenticated_read in environments:
            with self.subTest(environment=environment), \
                    patch.object(components, "resolve", side_effect=RuntimeError("private cache unavailable")) as resolve, \
                    patch.object(components, "_cache", return_value={"cache-from": [], "cache-to": "registry-export", "write-enabled": True}), \
                    patch.object(components, "_run") as run:
                components.clear_prepared()
                refs = components.prepare(["base"], root=self.root, env=environment)
            expected = {"authenticated": True, "pull_only": True} if authenticated_read else {"authenticated": False}
            resolve.assert_called_once_with(components.reference("base", self.root), **expected)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(refs["base"].startswith("image-library-component:"))
            self.assertFalse(any(command[:2] == ["docker", "push"] for command in commands))
            self.assertFalse(any("registry-export" in command for command in commands))

    def test_auth_mode_does_not_reuse_a_memoized_anonymous_local_build(self):
        with patch.object(components, "resolve", side_effect=[None, {"digest": "sha256:" + "b" * 64}]) as resolve, \
                patch.object(components, "_cache", return_value={"cache-from": [], "cache-to": "", "write-enabled": False}), \
                patch.object(components, "_run"), \
                patch.object(components.subprocess, "check_output", return_value=self.labels):
            first = components.prepare(["base"], root=self.root, env={})
            second = components.prepare(["base"], root=self.root, env=self.environment())
        self.assertTrue(first["base"].startswith("image-library-component:"))
        self.assertTrue(second["base"].endswith("@sha256:" + "b" * 64))
        self.assertEqual(resolve.call_count, 2)
        self.assertEqual(resolve.call_args.kwargs, {"authenticated": True, "pull_only": True})

    def test_image_workflow_restricts_login_and_token_to_repository_prs(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/validate.yml").read_text()
        job = workflow.split("\n  images:\n", 1)[1].split("\n  checks:\n", 1)[0]
        self.assertIn("packages: read", job)
        self.assertNotIn("packages: write", job)
        login = job.split("      - name: Authenticate private component reads", 1)[1].split("      - id: cache-key", 1)[0]
        self.assertIn("github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository", login)
        self.assertIn("docker/login-action@81c6f93d4bc991e510b342a00b419b3bb4efc5c6", login)
        build = job.split("      - name: Build and exercise the documented recipe\n", 1)[1]
        self.assertIn("XORDER_COMPONENTS_READ_AUTH:", build)
        self.assertIn("GH_TOKEN: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository && github.token || '' }}", build)


if __name__ == "__main__":
    unittest.main()
