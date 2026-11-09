"""Prepared inputs preserve exact identity, dependency scope and successful outputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import components
import build
from image_validation import affected_suites


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copy(ROOT / "schemas/component.schema.json", self.root / "schemas/component.schema.json")
        (self.root / ".dockerignore").write_text(".git\n")
        (self.root / "images").mkdir()
        (self.root / "images/tools.json").write_text(json.dumps({"version": "1", "other": "unchanged"}))
        self.component("base")
        components.clear_prepared()
        self.addCleanup(components.clear_prepared)

    def component(self, name, parent=None):
        folder = self.root / "images/components" / name
        folder.mkdir(parents=True)
        if parent:
            recipe = "ARG INPUT_IMAGE\nFROM ${INPUT_IMAGE}\n"
            extra = {"components": {"INPUT_IMAGE": parent}}
        else:
            recipe = "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
            extra = {"build_args": {"BASE_IMAGE": "docker.io/library/debian@sha256:" + "a" * 64}}
        recipe += f"COPY images/components/{name}/data/ /data/\n"
        (folder / "Dockerfile").write_text(recipe)
        (folder / "data").mkdir()
        (folder / "data/a").write_text("first")
        (folder / "data/b").write_text("second")
        self.manifest = {"schema_version": 1, "id": name, "purpose": "test input",
                         "dockerfile": f"images/components/{name}/Dockerfile",
                         "platforms": ["linux/amd64"], "abi": "debian-trixie-amd64",
                         "verify": ["/bin/true"], **extra}
        (folder / "definition.json").write_text(json.dumps(self.manifest))
        return folder

    def manifest_path(self, name="base"):
        return self.root / f"images/components/{name}/definition.json"

    def mutate(self, change, name="base"):
        path = self.manifest_path(name)
        item = json.loads(path.read_text())
        change(item)
        path.write_text(json.dumps(item))

    def test_non_build_metadata_preserves_key_but_abi_changes_it(self):
        before = components.build_key("base", self.root)
        self.mutate(lambda item: item.update(purpose="new documentation", verify=["/bin/echo", "checked"]))
        self.assertEqual(components.build_key("base", self.root), before)
        self.mutate(lambda item: item.update(abi="other-abi"))
        self.assertNotEqual(components.build_key("base", self.root), before)

    def test_changed_tool_pin_and_transitive_component_invalidate_only_consumers(self):
        self.component("child", "base")
        self.component("unrelated")
        path = self.root / "images/components/base/Dockerfile"
        path.write_text(path.read_text() + "ARG TOOL_VERSION\nRUN printf '%s' \"$TOOL_VERSION\"\n")
        self.mutate(lambda item: item.update(tool_args={"TOOL_VERSION": "version"}))
        original = {name: components.build_key(name, self.root) for name in ("base", "child", "unrelated")}
        old_tools = json.loads((self.root / "images/tools.json").read_text())
        (self.root / "images/tools.json").write_text(json.dumps({**old_tools, "version": "2"}))
        changed = {name for name, key in original.items() if components.build_key(name, self.root) != key}
        self.assertEqual(changed, {"base", "child"})
        self.assertEqual(components.affected_components(["images/tools.json"], self.root, old_tools), ["base", "child"])

    def test_deleted_directory_copy_member_selects_component_and_image(self):
        self.component("child", "base")
        before = components.build_key("child", self.root)
        path = "images/components/base/data/b"
        (self.root / path).unlink()
        self.assertNotEqual(components.build_key("child", self.root), before)
        self.assertEqual(components.affected_components([path], self.root), ["base", "child"])
        images = {"app/line": {"family": "app", "line": "line", "platforms": ["linux/amd64"],
                               "base": {}, "build_components": {"INPUT_IMAGE": "child"}}}
        self.assertEqual(affected_suites([path], images, self.root), {"app/line": ["full"]})

    def test_copied_transport_source_is_selected_before_metadata_exemption(self):
        copied = self.root / "scripts/xorder/transport.py"
        copied.parent.mkdir(parents=True)
        copied.write_text("transport bytes")
        recipe = self.root / "images/components/base/Dockerfile"
        recipe.write_text(recipe.read_text() + "COPY scripts/xorder/transport.py /transport.py\n")
        images = {"app/line": {"family": "app", "line": "line", "platforms": ["linux/amd64"],
                               "base": {}, "build_components": {"INPUT_IMAGE": "base"}}}
        self.assertEqual(affected_suites(["scripts/xorder/transport.py"], images, self.root),
                         {"app/line": ["full"]})

    def test_cycles_missing_arguments_and_mutable_donors_are_rejected(self):
        self.mutate(lambda item: item.update(build_args={"BASE_IMAGE": "debian:trixie"}))
        with self.assertRaisesRegex(ValueError, "exact digest"):
            components.build_key("base", self.root)
        self.mutate(lambda item: item.update(build_args={}))
        with self.assertRaisesRegex(ValueError, "Unbound"):
            components.build_key("base", self.root)
        self.mutate(lambda item: item.update(components={"BASE_IMAGE": "base"}))
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            components.definitions(self.root)

    def test_external_copy_donor_requires_an_exact_digest(self):
        recipe = self.root / "images/components/base/Dockerfile"
        recipe.write_text(recipe.read_text() + "COPY --from=example/tool:latest /tool /tool\n")
        with self.assertRaisesRegex(ValueError, "exact digest"):
            components.build_key("base", self.root)

    def test_reuse_runs_current_verification_and_retains_exact_receipt(self):
        key = components.build_key("base", self.root)
        labels = {"io.xorder.component.key": key, "io.xorder.component.id": "base"}
        with patch.object(components, "resolve", return_value={"digest": "sha256:" + "b" * 64}), \
                patch.object(components, "_run") as run, \
                patch.object(components.subprocess, "check_output", return_value=json.dumps(labels)):
            refs = components.prepare(["base"], "request-head", self.root, env={})
            self.mutate(lambda item: item.update(verify=["/bin/echo", "new verification"]))
            components.prepare(["base"], "request-head", self.root, env={})
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["docker", "run", "--rm", "--entrypoint", "/bin/echo", refs["base"], "new verification"], commands)
        receipt = json.loads((self.root / "out/components/base.json").read_text())
        self.assertEqual(receipt["reference"], refs["base"])
        self.assertEqual(receipt["request_source_commit"], "request-head")
        self.assertTrue(refs["base"].endswith("@sha256:" + "b" * 64))

    def test_identity_mismatch_never_falls_back_to_a_build(self):
        with patch.object(components, "resolve", return_value={"digest": "sha256:" + "b" * 64}), \
                patch.object(components, "_run") as run, \
                patch.object(components.subprocess, "check_output", return_value="{}"):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                components.prepare(["base"], root=self.root, env={})
        self.assertEqual(len(run.call_args_list), 1)

    def test_strict_published_mode_does_not_accept_a_memoized_local_donor(self):
        key = components.build_key("base", self.root)
        identity = (str(self.root.resolve()), "base", key, False, False, "xormania/xorder", "local",
                    components._hash(["/bin/true"]))
        components.PREPARED[identity] = "image-library-component:base-local"
        with patch.object(components, "resolve", return_value=None), patch.object(components, "_run") as run:
            with self.assertRaisesRegex(ValueError, "not published"):
                components.prepare(["base"], root=self.root, env={}, require_published=True)
        run.assert_not_called()

    def test_invalid_ca_is_rejected_before_component_side_effects(self):
        with patch.dict(os.environ, {"CA_CERTIFICATE": "relative.pem"}, clear=True), \
                patch.object(components, "arguments") as arguments, \
                patch.object(build.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "readable absolute"):
                build.build("python-dev/3.14-trixie", "test:image", "source")
        arguments.assert_not_called()
        run.assert_not_called()

    def test_publication_requires_the_actual_repository_master_push(self):
        for env in ({}, {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "pull_request",
                         "GITHUB_REF": "refs/heads/master"}):
            with self.subTest(env=env), patch.object(components, "_run") as run:
                with self.assertRaisesRegex(ValueError, "real master push"):
                    components.prepare(["base"], root=self.root, publish=True, env=env)
                run.assert_not_called()

    def test_completed_input_is_published_before_a_later_component_failure(self):
        self.component("later", "base")
        event = self.root / "event.json"
        event.write_text(json.dumps({"repository": {"full_name": "xormania/xorder", "default_branch": "master"}}))
        env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/master",
               "GITHUB_REF_PROTECTED": "true", "GITHUB_REPOSITORY": "xormania/xorder", "GITHUB_EVENT_PATH": str(event)}
        commands = []
        def run(command, root):
            commands.append(command)
            if command[:3] == ["docker", "buildx", "build"] and "later-" in command[command.index("-t") + 1]:
                raise subprocess.CalledProcessError(1, command)
        with patch.object(components, "resolve", side_effect=[None, None, {"digest": "sha256:" + "b" * 64}, None]), \
                patch.object(components, "_run", side_effect=run), \
                patch.object(components.subprocess, "check_output", return_value="default"):
            with self.assertRaises(subprocess.CalledProcessError):
                components.prepare(["later"], root=self.root, publish=True, env=env)
        self.assertTrue(any(command[:2] == ["docker", "push"] for command in commands))
        receipt = json.loads((self.root / "out/components/base.json").read_text())
        self.assertTrue(receipt["reference"].endswith("@sha256:" + "b" * 64))
        self.assertFalse((self.root / "out/components/later.json").exists())


if __name__ == "__main__":
    unittest.main()
