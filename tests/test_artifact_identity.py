"""Image reuse depends on installed inputs, while historical evidence stays intact."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import artifact_identity as identity
import library


class ArtifactIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "images/demo").mkdir(parents=True)
        (self.root / ".dockerignore").write_text(".git\n**/vendor\n")
        self.recipe = self.root / "images/demo/Dockerfile"
        self.recipe.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nARG APT_REFRESH\n"
                               "ARG SYMFONY_URL\nARG SYMFONY_SHA256\n"
                               "COPY images/demo/launch.sh /launch\n"
                               "ARG SOURCE_COMMIT\nARG IMAGE_VERSION\n"
                               "LABEL source=${SOURCE_COMMIT} version=${IMAGE_VERSION}\n")
        self.launch = self.root / "images/demo/launch.sh"
        self.launch.write_text("#!/bin/sh\necho ready\n")
        self.launch.chmod(0o755)
        self.tools = {"symfony": {"url": "https://example.test/cli", "sha256": "b" * 64, "version": "1.0"},
                      "node": {"tag": "node:22", "digest": "sha256:" + "c" * 64},
                      "apt_indexes": {"https://example.test/Release": "d" * 64}}
        (self.root / "images/tools.json").write_text(json.dumps(self.tools))
        self.definition = {"family": "demo", "line": "1-trixie", "line_id": "demo/1-trixie",
                           "platforms": ["linux/amd64"], "revision": "1.0.0",
                           "base": {"tag": "example.test/demo:1", "digest": "sha256:" + "a" * 64},
                           "purpose": "Original purpose", "changes": ["Initial revision"]}

    def key(self, **kwargs):
        return identity.build_key(self.definition, self.root, **kwargs)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def historical_record(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Identity test")
        self.git("config", "user.email", "identity@example.test")
        self.git("add", ".")
        self.git("commit", "-qm", "Original build inputs")
        return {"line_id": self.definition["line_id"], "definition": copy.deepcopy(self.definition),
                "source_commit": self.git("rev-parse", "HEAD"), "tools": copy.deepcopy(self.tools),
                "resolved_base": "example.test/demo:1@sha256:" + "a" * 64,
                "input_fingerprint": "e" * 64}

    def test_descriptions_revision_and_contract_metadata_reuse_artifact(self):
        before = self.key()
        self.definition.update(revision="3.0.0", purpose="Reworded", changes=["Documentation"],
                               migration="New instructions", limitations=["Clarified"],
                               capabilities=["required-capability"], execution={"default_uid": 1000},
                               input_fingerprint_version=2)
        self.assertEqual(before, self.key())

    def test_input_snapshot_has_explicit_hashes_and_modes(self):
        snapshot = identity.build_inputs(self.definition, self.root)
        self.assertEqual(snapshot["build_key_version"], 1)
        self.assertEqual(snapshot["files"]["images/demo/launch.sh"]["mode"], "0755")
        self.assertRegex(snapshot["files"]["images/demo/launch.sh"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(snapshot["resolved_base"], "example.test/demo@sha256:" + "a" * 64)
        self.assertNotIn("revision", snapshot)

    def test_copied_bytes_and_executable_mode_change_identity(self):
        initial = self.key()
        self.launch.write_text("#!/bin/sh\necho changed\n")
        changed = self.key()
        self.assertNotEqual(initial, changed)
        self.launch.chmod(0o644)
        self.assertNotEqual(changed, self.key())

    def test_uncopied_file_and_unconsumed_pin_do_not_change_identity(self):
        initial = self.key()
        (self.root / "images/demo/notes.md").write_text("A documentation edit")
        self.tools["node"]["digest"] = "sha256:" + "f" * 64
        self.tools["symfony"]["version"] = "2.0"
        self.assertEqual(initial, self.key(tools=self.tools))
        self.tools["symfony"]["sha256"] = "f" * 64
        self.assertNotEqual(initial, self.key(tools=self.tools))

    def test_apt_feed_changes_refresh_layers_without_revision_changes(self):
        before = self.key()
        old_refresh = identity.apt_refresh(self.tools)
        self.tools["apt_indexes"]["https://example.test/Release"] = "f" * 64
        self.assertNotEqual(old_refresh, identity.apt_refresh(self.tools))
        self.assertNotEqual(before, self.key(tools=self.tools))
        for invalid in ({}, {"apt_indexes": {}}, {"apt_indexes": {"feed": "not-a-hash"}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                identity.apt_refresh(invalid)

    def test_base_tag_alone_is_informational_but_digest_is_material(self):
        before = self.key()
        self.definition["base"]["tag"] = "example.test/demo:stable"
        self.assertEqual(before, self.key())
        self.definition["base"]["digest"] = "sha256:" + "f" * 64
        self.assertNotEqual(before, self.key())

    def test_parent_must_be_an_exact_digest_and_is_part_of_identity(self):
        self.definition["base"] = {"parent": "base/1-trixie"}
        with self.assertRaises(ValueError):
            self.key()
        for invalid in ("local-parent:tag", "base@sha256:short", "base@sha256:" + "a" * 63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.key(parent=invalid)
        first = self.key(parent="example.test/base@sha256:" + "a" * 64)
        second = self.key(parent="example.test/base@sha256:" + "b" * 64)
        self.assertNotEqual(first, second)

    def test_copy_glob_selects_only_the_chosen_image_line(self):
        self.recipe.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nARG IMAGE_LINE\n"
                               "COPY images/demo/${IMAGE_LINE}/*.json /data/\n")
        for line in ("1-trixie", "2-trixie"):
            folder = self.root / "images/demo" / line
            folder.mkdir()
            (folder / "package.json").write_text("{}")
        before = self.key()
        (self.root / "images/demo/2-trixie/package.json").write_text('{"changed":true}')
        self.assertEqual(before, self.key())
        (self.root / "images/demo/1-trixie/package.json").write_text('{"changed":true}')
        self.assertNotEqual(before, self.key())

    def test_ignored_dependency_directories_do_not_allocate_another_artifact(self):
        self.recipe.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nCOPY images/demo/ /data/\n")
        before = self.key()
        vendor = self.root / "images/demo/vendor"
        vendor.mkdir()
        (vendor / "huge-installed-package").write_text("Ignored dependency")
        self.assertEqual(before, self.key())

    def test_missing_copy_symlink_and_parent_traversal_fail_closed(self):
        self.launch.unlink()
        with self.assertRaises(ValueError):
            self.key()
        self.launch.symlink_to(self.root / "images/tools.json")
        with self.assertRaises(ValueError):
            self.key()
        self.recipe.write_text("COPY ../outside /data\n")
        with self.assertRaises(ValueError):
            self.key()

    def test_provenance_arguments_cannot_change_runtime_content(self):
        self.recipe.write_text(self.recipe.read_text() + 'RUN echo "$IMAGE_VERSION" > /version\n')
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.key()

    def test_historical_source_is_reconstructed_without_mutating_record(self):
        record = self.historical_record()
        original = copy.deepcopy(record)
        before = identity.recorded_build_key(record, self.root)
        self.assertEqual(before, self.key())
        self.definition.update(purpose="New description", revision="1.0.1")
        self.assertTrue(identity.existing_record_match(record, self.definition, self.root))
        self.launch.write_text("New local runtime bytes")
        self.assertEqual(before, identity.recorded_build_key(record, self.root))
        self.assertFalse(identity.existing_record_match(record, self.definition, self.root))
        self.assertEqual(original, record)

    def test_missing_history_and_noncommit_source_cannot_claim_equivalence(self):
        record = self.historical_record()
        for source in ("deadbeef", "0" * 40, self.git("hash-object", ".dockerignore")):
            with self.subTest(source=source), self.assertRaises(ValueError):
                identity.recorded_build_key(dict(record, source_commit=source), self.root)

    def test_historical_copy_patterns_are_anchored_to_the_build_context(self):
        unrelated = self.root / "extra/images/demo"
        unrelated.mkdir(parents=True)
        (unrelated / "launch.sh").write_text("An unrelated file with the same path suffix")
        record = self.historical_record()
        self.assertEqual(identity.recorded_build_key(record, self.root), self.key())

    def test_original_untracked_apt_feed_cannot_be_invented(self):
        record = self.historical_record()
        del record["tools"]["apt_indexes"]
        self.assertFalse(identity.existing_record_match(record, self.definition, self.root))

    def test_new_record_key_is_validated_and_does_not_need_historical_checkout(self):
        record = {"build_key": self.key(), "build_key_version": 1}
        self.assertEqual(record["build_key"], identity.recorded_build_key(record, self.root))
        for invalid in ({"build_key": "bad", "build_key_version": 1},
                        {"build_key": "a" * 64, "build_key_version": 2}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                identity.recorded_build_key(invalid, self.root)

    def test_current_accepted_records_prove_original_build_equivalence(self):
        if library.ROOT != identity.ROOT or not (identity.ROOT / ".git").exists():
            self.skipTest("Original git history is not available")
        definitions = library.definitions()
        for record in library.records():
            definition = definitions.get(record["line_id"])
            if definition and record["version"] == definition["revision"]:
                with self.subTest(line=record["line_id"]):
                    parent = record["resolved_base"] if definition["base"].get("parent") else None
                    self.assertTrue(identity.existing_record_match(record, definition, parent=parent))


if __name__ == "__main__":
    unittest.main()
