"""Exercise HTTP publication boundaries using real retrieved bytes and verifiers."""
import copy
import functools
import hashlib
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from library import ROOT, affected as image_affected, definitions as image_definitions
from xorder import model, release, transport, verify
import writeback


class ResourcePublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo, self.remote = self.root / "repo", self.root / "remote"
        self.repo.mkdir()
        self.remote.mkdir()
        shutil.copytree(ROOT / "schemas", self.repo / "schemas")
        self.resource_id = "configuration/sample"
        self.source = "a" * 40
        self.tag = self.resource_id + "/v1.0.0"
        resource = self.repo / "artifacts" / self.resource_id
        payload = resource / "payload"
        payload.mkdir(parents=True)
        (payload / "settings").write_text("verified resource\n")
        (payload / "not-published").write_text("outside declared selection\n")
        scripts = self.repo / "scripts"
        scripts.mkdir()
        (scripts / "verify.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "root = Path(sys.argv[1])\n"
            "assert root.joinpath('settings').read_text() == 'verified resource\\n'\n"
            "assert not root.joinpath('not-published').exists()\n"
            "Path('executed.log').open('a').write(str(root)+'\\n')\n")
        self.definition = {
            "schema_version": 2, "id": self.resource_id, "kind": "configuration", "name": "sample",
            "revision": "1.0.0", "purpose": "Publication boundary fixture", "capabilities": ["settings"],
            "targets": ["any"], "prerequisites": {"commands": ["python3"]},
            "documentation": "docs/sample.md", "details": {"target_application": "fixture", "files": [{"source": "settings", "destination": "settings"}]},
            "verification": {"command": ["python3", "scripts/verify.py"]},
        }
        (resource / "definition.json").write_text(model.encoded(self.definition))
        self.release = None
        self.events = []
        self.fail_record = False
        self.failed_record = None
        self.fail_notes = False
        self.corrupt_public = False
        self.authorization = []
        self.visibility_delays = {}
        self.pending_visibility = []
        self.lookups = []
        self.clock = 0.0
        self.sleeps = []
        self.hide_candidate = False
        self.api_failure = None
        self.observed_source = None
        self.observed_tag = None
        owner = self
        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                owner.authorization.append(self.headers.get("Authorization"))
                if owner.corrupt_public and self.path.endswith(".tar"):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"corrupted public bytes")
                else:
                    super().do_GET()
            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(self.remote)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def transfer(self, url, destination, checksum):
        local = f"http://127.0.0.1:{self.server.server_port}/{url.rsplit('/', 1)[-1]}"
        return transport.download(local, destination, checksum, allow_local_http=True)

    def fake_run(self, *args):
        self.events.append(args)
        self.assertEqual(args[:2], ("gh", "release"))
        action = args[2]
        before = copy.deepcopy(self.release)
        phase = None
        if action == "create":
            self.assertIsNone(self.release)
            self.release = {"id": 101, "tag_name": self.tag, "target_commitish": self.source, "draft": True, "assets": []}
            phase = "create"
        elif action == "upload":
            path = Path(args[4])
            if path.name == "record.json" and self.fail_record:
                self.failed_record = json.loads(path.read_text())
                raise RuntimeError("record upload interrupted")
            self.assertFalse((self.remote / path.name).exists(), "asset overwrite attempted")
            shutil.copyfile(path, self.remote / path.name)
            self.release["assets"].append({"name": path.name, "browser_download_url": "https://example.test/" + path.name})
            phase = "record" if path.name == "record.json" else "payload"
        elif action == "download":
            filename = args[args.index("--pattern") + 1]
            destination = Path(args[args.index("--dir") + 1])
            shutil.copyfile(self.remote / filename, destination / filename)
        elif action == "edit":
            if "--draft=false" in args:
                self.release["draft"] = False
                phase = "publish"
            elif "--notes" in args and self.fail_notes:
                raise RuntimeError("notes edit interrupted")
        else:
            self.fail(f"Unexpected release command: {args}")
        self.pending_visibility.extend(copy.deepcopy(before) for _ in range(self.visibility_delays.get(phase, 0)))

    def lookup(self, tag, release_id=None, timeout=None):
        self.assertEqual(tag, self.tag)
        self.lookups.append((release_id, timeout))
        if self.release is not None and self.api_failure:
            raise self.api_failure
        if self.release is not None and self.hide_candidate:
            return None
        observed = copy.deepcopy(self.pending_visibility.pop(0) if self.pending_visibility else self.release)
        if observed is not None:
            if self.observed_source:
                observed["target_commitish"] = self.observed_source
            if self.observed_tag:
                observed["tag_name"] = self.observed_tag
        return observed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.clock += seconds

    def publish(self):
        with patch.object(release, "release_info", side_effect=self.lookup), \
                patch.object(release, "run", side_effect=self.fake_run), \
                patch.object(release, "tag_guard"), \
                patch.object(release, "download", side_effect=self.transfer), \
                patch.object(release.time, "monotonic", side_effect=lambda: self.clock), \
                patch.object(release.time, "sleep", side_effect=self.sleep), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder", "GITHUB_RUN_ID": "42", "GH_TOKEN": "must-not-be-forwarded"}):
            return release.publish(self.resource_id, self.source, self.root / "out", self.repo)

    def test_delayed_visibility_retries_reads_without_repeating_any_write(self):
        self.visibility_delays = {"create": 2, "payload": 2, "publish": 2, "record": 2}
        record = self.publish()
        self.assertEqual(self.sleeps, [0.25, 0.5] * 4)
        self.assertEqual(sum(event[2] == "create" for event in self.events), 1)
        self.assertEqual(sum(event[2] == "upload" and event[4].endswith(".tar") for event in self.events), 1)
        self.assertEqual(sum(event[2] == "upload" and event[4].endswith("record.json") for event in self.events), 1)
        self.assertEqual(sum("--draft=false" in event for event in self.events), 1)
        self.assertTrue(all(release_id == 101 for release_id, _ in self.lookups[4:]))
        self.assertTrue(all(0 < timeout <= 20 for _, timeout in self.lookups[1:]))
        self.assertEqual(json.loads((self.remote / "record.json").read_text()), record)
        self.assertEqual(self.authorization, [None])
        self.assertTrue((self.repo / "executed.log").is_file())

    def test_unobservable_creation_stops_within_shared_visibility_budget(self):
        self.hide_candidate = True
        with self.assertRaisesRegex(RuntimeError, "Candidate release creation was not observable"):
            self.publish()
        self.assertEqual(sum(self.sleeps), 20)
        self.assertEqual(sum(event[2] == "create" for event in self.events), 1)
        self.assertFalse(any(event[2] == "upload" for event in self.events))

    def test_record_visibility_uses_remaining_budget_and_withholds_export(self):
        self.visibility_delays = {"create": 2, "payload": 2, "publish": 2, "record": 100}
        with self.assertRaisesRegex(RuntimeError, "Durable resource record is not observable"):
            self.publish()
        self.assertEqual(sum(self.sleeps), 20)
        self.assertTrue((self.remote / "record.json").is_file())
        self.assertTrue((self.repo / "executed.log").is_file())
        self.assertFalse((self.root / "out/record.json").exists())

    def test_api_failure_after_creation_is_not_retried(self):
        for error in (subprocess.CalledProcessError(1, ["gh", "api"]), subprocess.TimeoutExpired(["gh", "api"], 20)):
            with self.subTest(error=type(error)):
                self.release = None
                self.events.clear()
                self.lookups.clear()
                self.api_failure = error
                with self.assertRaises(type(error)):
                    self.publish()
                self.assertEqual(self.sleeps, [])
                self.assertEqual(len(self.lookups), 2)
                self.assertFalse(any(event[2] == "upload" for event in self.events))

    def test_changed_source_or_tag_after_creation_is_not_retried(self):
        for field, value in (("observed_source", "b" * 40), ("observed_tag", "configuration/other/v1.0.0")):
            with self.subTest(field=field):
                self.release = None
                self.events.clear()
                self.lookups.clear()
                self.observed_source = self.observed_tag = None
                setattr(self, field, value)
                with self.assertRaisesRegex(RuntimeError, "Observed release source or tag differs"):
                    self.publish()
                self.assertEqual(self.sleeps, [])
                self.assertEqual(len(self.lookups), 2)
                self.assertFalse(any(event[2] == "upload" for event in self.events))

    def test_direct_release_read_pins_id_and_tag(self):
        observed = {"id": 101, "tag_name": self.tag}
        with patch.object(release, "gh", return_value=json.dumps(observed)) as gh, \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder"}):
            self.assertEqual(release.release_info(self.tag, 101, timeout=3), observed)
        gh.assert_called_once_with("api", "repos/xormania/xorder/releases/101", timeout=3)
        for changed in ({"id": 102, "tag_name": self.tag}, {"id": 101, "tag_name": "other"}):
            with self.subTest(observed=changed), patch.object(release, "gh", return_value=json.dumps(changed)), \
                    patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder"}):
                with self.assertRaisesRegex(RuntimeError, "Observed release identity differs"):
                    release.release_info(self.tag, 101)

    def test_public_bytes_execute_before_durable_record_and_remain_unaccepted(self):
        record = self.publish()
        self.assertEqual(record["publication"]["sha256"], hashlib.sha256((self.remote / "sample-1.0.0.tar").read_bytes()).hexdigest())
        self.assertEqual(self.authorization, [None])
        self.assertTrue((self.repo / "executed.log").is_file())
        self.assertFalse(self.release["draft"])
        self.assertEqual(model.records(self.repo), [])
        publish_index = next(i for i, event in enumerate(self.events) if "--draft=false" in event)
        record_index = next(i for i, event in enumerate(self.events) if event[2] == "upload" and event[4].endswith("record.json"))
        self.assertLess(publish_index, record_index)

    def test_corrupt_public_download_has_no_passed_record(self):
        self.corrupt_public = True
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.publish()
        self.assertFalse((self.remote / "record.json").exists())
        self.assertFalse((self.root / "out/record.json").exists())
        self.assertFalse((self.repo / "executed.log").exists())

    def test_resume_after_record_upload_retrieves_and_executes_same_artifact(self):
        self.fail_notes = True
        with self.assertRaisesRegex(RuntimeError, "notes edit interrupted"):
            self.publish()
        durable = (self.remote / "record.json").read_bytes()
        self.fail_notes = False
        with patch.object(release, "prepare", side_effect=AssertionError("must reuse durable bytes")):
            record = self.publish()
        self.assertEqual((self.remote / "record.json").read_bytes(), durable)
        self.assertEqual(record, json.loads(durable))
        self.assertEqual(len((self.repo / "executed.log").read_text().splitlines()), 2)

    def test_resume_without_record_never_replaces_asset(self):
        self.fail_record = True
        with self.assertRaisesRegex(RuntimeError, "record upload interrupted"):
            self.publish()
        artifact = (self.remote / "sample-1.0.0.tar").read_bytes()
        self.fail_record = False
        record = self.publish()
        self.assertEqual((self.remote / "sample-1.0.0.tar").read_bytes(), artifact)
        uploads = [event for event in self.events if event[2] == "upload" and event[4].endswith(".tar")]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(record["version"], "1.0.0")

    def test_different_existing_candidate_bytes_refuse_exact_reassignment(self):
        self.fail_record = True
        with self.assertRaises(RuntimeError):
            self.publish()
        (self.remote / "sample-1.0.0.tar").write_bytes(b"different content")
        self.fail_record = False
        with self.assertRaisesRegex(RuntimeError, "different bytes"):
            self.publish()
        self.assertEqual((self.remote / "sample-1.0.0.tar").read_bytes(), b"different content")

    def test_changed_inputs_cannot_resume_recorded_revision(self):
        self.publish()
        (self.repo / "artifacts" / self.resource_id / "payload/settings").write_text("changed input\n")
        with self.assertRaisesRegex(RuntimeError, "different inputs"):
            self.publish()

    def test_api_failure_is_not_an_absent_release(self):
        with patch.object(release, "gh", side_effect=subprocess.CalledProcessError(1, ["gh", "api"])), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder"}):
            with self.assertRaises(subprocess.CalledProcessError):
                release.release_info(self.tag)

    def test_source_tag_guard_respects_annotated_tag_commit(self):
        output = f"{'b' * 40}\trefs/tags/{self.tag}\n{self.source}\trefs/tags/{self.tag}^{{}}\n"
        with patch.object(release.subprocess, "check_output", return_value=output):
            release.tag_guard(self.tag, self.source)
            with self.assertRaisesRegex(RuntimeError, "different commit"):
                release.tag_guard(self.tag, "c" * 40)

    def test_packaging_is_reproducible_and_contains_only_declared_files(self):
        first, facts = verify.prepare(self.definition, self.root / "first", self.repo)
        settings = self.repo / "artifacts" / self.resource_id / "payload/settings"
        os.utime(settings, (1000, 1000))
        second, next_facts = verify.prepare(self.definition, self.root / "second", self.repo)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(facts, next_facts)
        with tarfile.open(first) as archive:
            self.assertEqual(archive.getnames(), ["settings"])

    def test_writeback_requires_durable_record_asset(self):
        self.fail_record = True
        with self.assertRaisesRegex(RuntimeError, "record upload interrupted"):
            self.publish()
        self.assertFalse((self.root / "out/record.json").exists())
        record = self.failed_record
        view = {"isDraft": False, "targetCommitish": self.source,
                "assets": [{"name": asset["name"], "url": asset["browser_download_url"]} for asset in self.release["assets"]]}
        with patch.object(writeback, "output", return_value=json.dumps(view)), \
                patch.object(writeback, "download", side_effect=AssertionError("must reject before download")):
            self.assertFalse(writeback.accepted_resource(record))

    def mixed_writeback(self, failure):
        good = self.publish()
        bad = copy.deepcopy(good)
        bad.update(id="configuration/broken", source_tag="configuration/broken/v1.0.0")
        bad["definition"].update(id=bad["id"], name="broken")
        bad["publication"].update(filename="broken-1.0.0.tar", url="https://example.test/broken-1.0.0.tar")
        if failure != "unavailable-payload":
            shutil.copyfile(self.remote / "sample-1.0.0.tar", self.remote / "broken-1.0.0.tar")
        if failure == "corrupt-payload":
            (self.remote / "broken-1.0.0.tar").write_bytes(b"corrupted public payload")
        durable = self.remote / "broken-record.json"
        durable.write_text(model.encoded(bad))
        if failure == "corrupt-record":
            durable.write_bytes(b"corrupted durable record")
        releases = {
            good["source_tag"]: {"isDraft": False, "targetCommitish": self.source,
                "assets": [{"name": asset["name"], "url": asset["browser_download_url"]} for asset in self.release["assets"]]},
            bad["source_tag"]: {"isDraft": False, "targetCommitish": self.source,
                "assets": [{"name": "broken-1.0.0.tar", "url": bad["publication"]["url"]},
                           {"name": "record.json", "url": "https://example.test/broken-record.json"}]},
        }
        (self.repo / "README.md").write_text((ROOT / "README.md").read_text())
        origin = self.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "--initial-branch=master", str(origin)], check=True, capture_output=True)
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=self.repo, text=True, stderr=subprocess.PIPE).strip()
        git("init", "--initial-branch=master")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.test")
        git("add", ".")
        git("commit", "-m", "Fixture source")
        git("remote", "add", "origin", str(origin))
        git("push", "origin", "master")
        for name, record in (("a-failed", bad), ("b-passed", good)):
            path = self.repo / "out/releases" / name / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(model.encoded(record))
        def output(*args):
            if args[0] == "gh":
                if args[1:3] == ("api", "--paginate"):
                    return "[[]]"
                self.assertEqual(args[:3], ("gh", "release", "view"))
                return json.dumps(releases[args[3]])
            return subprocess.check_output(args, cwd=self.repo, text=True)
        diagnostics = io.StringIO()
        with patch.object(writeback, "ROOT", self.repo), \
                patch.object(writeback, "output", side_effect=output), \
                patch.object(writeback, "run", side_effect=lambda *args: subprocess.run(args, cwd=self.repo, check=True, capture_output=True)), \
                patch.object(writeback, "download", side_effect=self.transfer), \
                patch.object(writeback, "upsert_pr") as pr, \
                patch.object(writeback, "source_prs", return_value={}), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder", "GITHUB_RUN_ID": "43"}), \
                patch("sys.stdout", diagnostics):
            writeback.main()
        ledger = self.repo / "release-records/artifacts"
        self.assertEqual([record["id"] for record in model.records(self.repo)], [self.resource_id])
        self.assertTrue((ledger / self.resource_id / "1.0.0.json").exists())
        self.assertFalse((ledger / bad["id"] / "1.0.0.json").exists())
        self.assertEqual([item["id"] for item in json.loads((self.repo / "catalog-v2.json").read_text())["resources"]], [self.resource_id])
        pr.assert_called_once()
        self.assertIn("Skipping unverified public resource release for configuration/broken", diagnostics.getvalue())
        git("cat-file", "-e", "refs/remotes/origin/automation/catalog-" + writeback.catalog_identity([bad, good])[:24] + ":release-records/artifacts/configuration/sample/1.0.0.json")

    def test_corrupt_payload_does_not_block_independent_verified_writeback(self):
        self.mixed_writeback("corrupt-payload")

    def test_unavailable_payload_does_not_block_independent_verified_writeback(self):
        self.mixed_writeback("unavailable-payload")

    def test_corrupt_durable_record_does_not_block_independent_verified_writeback(self):
        self.mixed_writeback("corrupt-record")

    def test_writeback_release_api_failure_remains_global(self):
        record = self.publish()
        with patch.object(writeback, "output", side_effect=subprocess.CalledProcessError(1, ["gh", "release", "view"])), \
                patch.object(writeback, "download", side_effect=AssertionError("API failure must stop before download")):
            with self.assertRaises(subprocess.CalledProcessError):
                writeback.accepted_resource(record)


class AffectedResourceTests(unittest.TestCase):
    def test_context_change_keeps_images_and_other_resources_unselected(self):
        definitions = {"context/guidance": {"kind": "context"}, "binary/composer": {"kind": "binary"}, "environment/php": {"kind": "environment"}}
        changed = ["artifacts/context/guidance/payload/guidance.md"]
        self.assertEqual(verify.affected(changed, definitions), ["context/guidance"])
        self.assertEqual(image_affected(changed, image_definitions()), [])

    def test_shared_transport_selects_resource_consumers_and_no_image_jobs(self):
        definitions = {"context/guidance": {"kind": "context"}, "binary/composer": {"kind": "binary"}, "environment/php": {"kind": "environment"}}
        self.assertEqual(verify.affected(["scripts/xorder/transport.py"], definitions), sorted(definitions))
        self.assertEqual(image_affected(["scripts/xorder/transport.py"], image_definitions()), [])
        self.assertEqual(len(image_affected(["scripts/unknown-image-helper.py"], image_definitions())), 7)

    def test_environment_verifier_changes_select_native_environment_only(self):
        definitions = {"context/guidance": {"kind": "context"}, "environment/php": {"kind": "environment"}}
        self.assertEqual(verify.affected(["scripts/xorder/verify-devenv.sh"], definitions), ["environment/php"])
        self.assertEqual(image_affected(["schemas/resource.schema.json", "schemas/artifact-release-record.schema.json"], image_definitions()), [])

    def test_native_environment_fixture_changes_select_its_consumers(self):
        definitions = {"context/guidance": {"kind": "context"}, "binary/composer": {"kind": "binary"}, "environment/php": {"kind": "environment"}}
        changed = ["tests/fixtures/artifacts/environment/check.php"]
        self.assertEqual(verify.affected(changed, definitions), ["environment/php"])
        self.assertEqual(image_affected(changed, image_definitions()), [])

    def test_application_fixture_does_not_select_unexercised_runtimes(self):
        definitions = {"configuration/editorconfig": {"kind": "configuration"}, "context/guidance": {"kind": "context"}, "binary/composer": {"kind": "binary"}, "environment/php": {"kind": "environment"}}
        changed = ["tests/fixtures/artifacts/application/check.py"]
        self.assertEqual(verify.affected(changed, definitions), ["configuration/editorconfig", "context/guidance"])
        self.assertEqual(image_affected(changed, image_definitions()), [])


if __name__ == "__main__":
    unittest.main()
