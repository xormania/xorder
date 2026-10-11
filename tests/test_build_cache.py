"""Build-cache namespaces and read-only boundaries, without registry credentials."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
import build_cache


class BuildCacheTests(unittest.TestCase):
    def github(self, trigger="push", ref="refs/heads/dev", repository="xormania/uxor", event=None, **overrides):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "event.json"
            payload = {"repository": {"full_name": repository, "default_branch": "main"}}
            payload.update(event or {})
            path.write_text(json.dumps(payload))
            env = {"GITHUB_EVENT_PATH": str(path), "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": repository,
                   "GITHUB_EVENT_NAME": trigger, "GITHUB_REF": ref, "GITHUB_REF_PROTECTED": "false", **overrides}
            return build_cache.github_plan(env)

    def test_imports_branch_dev_main_and_actual_default_once(self):
        result = build_cache.plan("Xormania/uxor", "feature/demo", "master")
        self.assertEqual(result["image"], "ghcr.io/xormania/uxor-cache")
        self.assertEqual([item.rsplit(":", 1)[1] for item in result["cache-from"]][1:], ["dev", "main", "master"])
        self.assertEqual(len(build_cache.plan("xormania/uxor", "dev")["cache-from"]), 2)
        self.assertFalse(result["write-enabled"])
        self.assertEqual(result["cache-to"], "")

    def test_branch_tags_separate_normalization_case_and_truncation(self):
        branches = ["a/b", "a-b", "A-B", "main", "Main", "x" * 200 + "a", "x" * 200 + "b", "日本語"]
        tags = [build_cache.branch_tag(branch, "demo") for branch in branches]
        self.assertEqual(len(tags), len(set(tags)))
        for tag in tags:
            self.assertLessEqual(len(tag), 128)
            self.assertRegex(tag, r"^[a-z0-9][a-z0-9_.-]*$")
        self.assertEqual(build_cache.branch_tag("main", "demo"), "demo-main")

    def test_invalid_names_fail_and_unusual_github_repo_names_remain_distinct(self):
        for repository in ("https://github.com/a/b", "a/b/c", "a/b\ninjected=value", "a/b,mode=max"):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                build_cache.plan(repository, "main")
        for scope in ("Demo", "a/b", "a,b", "x" * 25):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                build_cache.plan("a/b", "main", scope=scope)
        self.assertNotEqual(build_cache.cache_image("owner/.github"), build_cache.cache_image("owner/github"))

    def test_only_matching_branch_push_exports_with_explicit_manifest_options(self):
        result = self.github()
        self.assertTrue(result["write-enabled"])
        self.assertEqual(result["cache-to"], "type=registry,ref=ghcr.io/xormania/uxor-cache:dev,mode=max,image-manifest=true,oci-mediatypes=true")
        for trigger, ref, event, overrides in (
            ("workflow_dispatch", "refs/heads/main", {}, {}),
            ("schedule", "refs/heads/main", {}, {}),
            ("push", "refs/tags/v1", {}, {}),
            ("push", "refs/heads/main", {"deleted": True}, {}),
            ("push", "refs/heads/main", {"repository": {"full_name": "fork/uxor"}}, {}),
            ("push", "refs/heads/main", {}, {"GITHUB_ACTIONS": "false"}),
            ("push", "refs/heads/main", {}, {"XORDER_CACHE_WRITE": "false"}),
        ):
            with self.subTest(trigger=trigger, ref=ref, event=event, overrides=overrides):
                result = self.github(trigger, ref, event=event, **overrides)
                self.assertFalse(result["write-enabled"])
                self.assertEqual(result["cache-to"], "")
                self.assertIn("*.cache-to=", result["bake-set"])

    def test_pull_requests_are_read_only_and_fork_head_caches_are_omitted(self):
        for trigger in ("pull_request", "pull_request_target"):
            for head_repository in ("xormania/uxor", "fork/uxor"):
                with self.subTest(trigger=trigger, repository=head_repository):
                    result = self.github(trigger, "refs/heads/main", event={"pull_request": {
                        "head": {"ref": "feature/demo", "repo": {"full_name": head_repository}},
                        "base": {"ref": "release/next"}}})
                    tags = [item.rsplit(":", 1)[1] for item in result["cache-from"]]
                    self.assertEqual(bool(result["branch-tag"]), head_repository == "xormania/uxor")
                    if trigger == "pull_request":
                        self.assertIn(build_cache.branch_tag("release/next"), tags)
                    else:
                        self.assertEqual(tags, [])
                    self.assertFalse(result["write-enabled"])
                    self.assertNotIn("*.cache-to+=", "\n".join(result["bake-set"]))

    def test_protected_pushes_only_import_their_protected_ref_by_default(self):
        for branch in ("main", "master", "release/next"):
            with self.subTest(branch=branch):
                result = self.github(ref="refs/heads/" + branch, GITHUB_REF_PROTECTED="true")
                self.assertEqual(result["import-policy"], "protected-only")
                self.assertEqual(result["cache-from"], ["type=registry,ref=ghcr.io/xormania/uxor-cache:" + build_cache.branch_tag(branch)])
                self.assertTrue(result["write-enabled"])
                self.assertEqual(result["cache-to"].split(",mode=", 1)[0], result["cache-from"][0])

    def test_equal_protection_is_explicit_and_cannot_implicitly_include_dev_or_default(self):
        result = self.github(ref="refs/heads/master", GITHUB_REF_PROTECTED="true",
                             XORDER_CACHE_TRUSTED_BRANCHES="main\nrelease/next\nmain\n")
        tags = [item.rsplit(":", 1)[1] for item in result["cache-from"]]
        self.assertEqual(tags, ["master", "main", build_cache.branch_tag("release/next")])
        self.assertNotIn("dev", tags)
        result = self.github(ref="refs/heads/release/next", GITHUB_REF_PROTECTED="true")
        self.assertNotIn("main", [item.rsplit(":", 1)[1] for item in result["cache-from"]])

    def test_pull_request_target_uses_protected_base_cache_and_omits_untrusted_head(self):
        for head_repository in ("xormania/uxor", "fork/uxor"):
            with self.subTest(head_repository=head_repository):
                result = self.github("pull_request_target", "refs/heads/main", GITHUB_REF_PROTECTED="true",
                                     event={"pull_request": {"head": {"ref": "dev", "repo": {"full_name": head_repository}},
                                                              "base": {"ref": "main"}}})
                self.assertEqual(result["cache-from"], ["type=registry,ref=ghcr.io/xormania/uxor-cache:main"])
                self.assertFalse(result["write-enabled"])

    def test_missing_protection_fact_imports_only_explicitly_trusted_caches(self):
        result = self.github(GITHUB_REF_PROTECTED="")
        self.assertEqual(result["cache-from"], [])
        self.assertEqual(result["bake-set"][:2], ["*.cache-from=", "*.cache-to="])
        self.assertIn("cache_from: !override []", build_cache.compose_overlay(result, "php"))
        result = self.github(GITHUB_REF_PROTECTED="", XORDER_CACHE_TRUSTED_BRANCHES="main")
        self.assertEqual(result["cache-from"], ["type=registry,ref=ghcr.io/xormania/uxor-cache:main"])

    def test_bake_clears_existing_exports_and_imports_before_setting_the_plan(self):
        result = self.github(XORDER_CACHE_SCOPE="demo")
        self.assertEqual(result["bake-set"][:2], ["*.cache-from=", "*.cache-to="])
        self.assertEqual(result["bake-set"][-1], "*.cache-to+=" + result["cache-to"])
        self.assertTrue(all(item.startswith("*.cache-from+=") for item in result["bake-set"][2:-1]))

    def test_local_output_modes_never_emit_cache_exports(self):
        for mode in ("json", "buildx", "bake", "compose"):
            with self.subTest(mode=mode), contextlib.redirect_stdout(io.StringIO()) as output:
                build_cache.main(["--repository", "xormania/uxor", "--branch", "dev", "--scope", "demo", "--format", mode])
                text = output.getvalue()
                self.assertIn("ghcr.io/xormania/uxor-cache:demo-main", text)
                self.assertNotIn("mode=max", text)
                self.assertNotIn("--cache-to", text)
                if mode == "compose":
                    self.assertIn("cache_to: !reset []", text)
                    self.assertIn("cache_from: !override", text)

    @unittest.skipUnless(shutil.which("docker"), "Docker CLI is unavailable; CI verifies Compose merging")
    def test_compose_overlay_removes_inherited_exports_and_replaces_imports(self):
        version = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if version.returncode:
            self.skipTest("Docker Compose is unavailable")
        result = build_cache.plan("xormania/uxor", "dev", scope="demo")
        with tempfile.TemporaryDirectory() as tmp:
            base, overlay = Path(tmp) / "compose.yaml", Path(tmp) / "cache.yaml"
            base.write_text(json.dumps({"services": {"php": {"image": "local/cache-reader:test", "build": {
                "context": ".", "cache_to": ["type=registry,ref=ghcr.io/example/export:main"],
                "cache_from": ["type=registry,ref=ghcr.io/example/untrusted:main"]}}}}))
            overlay.write_text(build_cache.compose_overlay(result, "php"))
            resolved = json.loads(subprocess.check_output(
                ["docker", "compose", "--project-directory", tmp, "-f", str(base), "-f", str(overlay),
                 "config", "--format", "json"], text=True))
            definition = resolved["services"]["php"]["build"]
            self.assertFalse(definition.get("cache_to"))
            self.assertEqual(definition["cache_from"], result["cache-from"])
            self.assertEqual(definition["context"], tmp)

    def test_action_output_roundtrip_keeps_multiline_inputs_and_false_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "outputs"
            result = build_cache.plan("xormania/uxor", "dev")
            build_cache.github_outputs(result, output)
            lines = output.read_text().splitlines()
            decoded = {}
            while lines:
                name, marker = lines.pop(0).split("<<")
                values = []
                while lines[0] != marker:
                    values.append(lines.pop(0))
                lines.pop(0)
                decoded[name] = "\n".join(values)
            self.assertEqual(decoded["cache-from"].splitlines(), result["cache-from"])
            self.assertEqual(decoded["write-enabled"], "false")
            self.assertEqual(decoded["cache-to"], "")

    def test_local_image_builder_imports_registry_without_exporting(self):
        imports = build_cache.plan("xormania/xorder", "dev", "master")["cache-from"]
        with patch.dict(os.environ, {}, clear=True), patch.object(build.subprocess, "run") as run:
            build.build("python-dev/3.14-trixie", "local:test", "local", registry_imports=imports)
        command = run.call_args.args[0]
        imported = [command[i + 1] for i, item in enumerate(command) if item == "--cache-from"]
        self.assertEqual(imported, imports)
        self.assertNotIn("--cache-to", command)
        self.assertNotIn("--push", command)

    def test_builder_cli_passes_read_only_imports_through_validation(self):
        with patch.object(build, "validate_tree") as validate:
            build.main(["python-dev/3.14-trixie", "local:test", "--registry-cache", "xormania/xorder",
                        "--cache-branch", "dev", "--cache-scope", "python"])
        args = validate.call_args.args[0]
        self.assertEqual(args.registry_imports, build_cache.plan("xormania/xorder", "dev", "master", scope="python")["cache-from"])


if __name__ == "__main__":
    unittest.main()
