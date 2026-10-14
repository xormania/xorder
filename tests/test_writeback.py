"""Exercise post-push refresh recovery against a real local Git remote."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from library import ROOT, read, encoded, generated
from test_library import record
import refresh
import writeback


class RefreshRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "origin.git"
        self.seed = self.root / "seed"
        self.worker = self.root / "worker"
        self.git(self.root, "init", "--bare", "--initial-branch=master", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.seed))
        shutil.copytree(ROOT, self.seed, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "out"))
        # Keep the recovery scenario independent of the repository's current
        # revisions: master starts at 1.0.0 and this refresh allocates 1.0.1.
        for path in (self.seed / "images").glob("*/definition.json"):
            definition = read(path)
            for line in definition["lines"].values():
                line["revision"] = "1.0.0"
            path.write_text(json.dumps(definition, indent=2) + "\n")
        self.git(self.seed, "config", "user.name", "Fixture")
        self.git(self.seed, "config", "user.email", "fixture@example.test")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Initial definitions")
        self.git(self.seed, "push", "origin", "master")
        self.git(self.root, "clone", str(self.remote), str(self.worker))
        self.branch = "automation/refresh-42"
        self.pr_attempts = 0
        self.pr_requests = []

    @staticmethod
    def git(cwd, *args):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE).strip()

    @staticmethod
    def upstream(url, **kwargs):
        if isinstance(url, refresh.urllib.request.Request):
            url = url.full_url
        if url.endswith("stable.txt"):
            return io.BytesIO(b"1.0.0")
        if url.endswith("/Release"):
            return io.BytesIO((" " + "c" * 64 + " 123 main/binary-amd64/Packages.xz\n").encode())
        if "/infection/" in url:
            return io.BytesIO(json.dumps({"tag_name": "0.35.6", "assets": [{
                "name": "infection.phar", "digest": "sha256:" + "b" * 64,
                "browser_download_url": "https://example.test/infection.phar"}]}).encode())
        return io.BytesIO(json.dumps({"tag_name": "v9.9.9", "assets": [{
            "name": "symfony-cli_linux_amd64.tar.gz", "digest": "sha256:" + "a" * 64,
            "browser_download_url": "https://example.test/symfony.tar.gz"}]}).encode())

    def run_writeback(self, existing_prs=None):
        original_output = writeback.output

        def output(*args):
            if args[0] == "gh":
                self.assertEqual(args[:4], ("gh", "api", "--method", "GET"))
                self.assertIn("head=xormania:" + self.branch, args)
                self.assertIn("base=master", args)
                self.assertIn("state=open", args)
                return json.dumps(existing_prs or [])
            return original_output(*args)

        def run(*args, **kwargs):
            if args[0] == "gh":
                # Reject the GraphQL CLI path that requires read:org on a
                # public_repo-only machine token, and retain the REST request.
                self.assertEqual(args[:3], ("gh", "api", "--method"))
                self.pr_requests.append((args[3], args[4], read(args[-1])))
                self.pr_attempts += 1
                if self.pr_attempts == 1:
                    raise RuntimeError("PR creation interrupted after push")
                return
            return subprocess.run(args, cwd=self.worker, check=True, capture_output=True, **kwargs)

        with patch.object(writeback, "ROOT", self.worker), \
                patch.object(refresh, "ROOT", self.worker), \
                patch.object(writeback, "output", side_effect=output), \
                patch.object(writeback, "run", side_effect=run), \
                patch.object(refresh, "resolve", return_value={"digest": "sha256:" + "a" * 64}), \
                patch.object(refresh.urllib.request, "urlopen", side_effect=self.upstream), \
                patch.dict(os.environ, {"GITHUB_RUN_ID": "42",
                                        "GITHUB_REPOSITORY": "xormania/docker-image-library"}):
            writeback.main(refresh=True)

    def interrupt_after_push(self):
        with self.assertRaisesRegex(RuntimeError, "PR creation interrupted"):
            self.run_writeback()
        first = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        shutil.rmtree(self.worker)
        self.git(self.root, "clone", str(self.remote), str(self.worker))
        return first

    def test_unchanged_rerun_recovers_missing_pr_and_preserves_revision(self):
        first = self.interrupt_after_push()
        self.run_writeback()
        after = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        self.assertEqual(after, first)
        self.assertEqual(self.pr_attempts, 2)
        d = read(self.worker / "images/php-dev/definition.json")
        self.assertEqual(d["lines"]["8.4-trixie"]["revision"], "1.0.1")

    def test_rerun_merges_new_master_without_replacing_remote_history(self):
        first = self.interrupt_after_push()
        readme = self.seed / "README.md"
        readme.write_text(readme.read_text() + "\nUpstream documentation update.\n")
        self.git(self.seed, "add", "README.md")
        self.git(self.seed, "commit", "-m", "Update documentation on master")
        self.git(self.seed, "push", "origin", "master")
        self.run_writeback()
        after = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        self.assertNotEqual(after, first)
        self.git(self.worker, "merge-base", "--is-ancestor", first, after)
        self.assertIn("Upstream documentation update.", (self.worker / "README.md").read_text())
        self.assertEqual(self.pr_attempts, 2)
        d = read(self.worker / "images/php-dev/definition.json")
        self.assertEqual(d["lines"]["8.4-trixie"]["revision"], "1.0.1")


    def test_rerun_updates_existing_pr_with_repository_rest_api(self):
        first = self.interrupt_after_push()
        self.run_writeback(existing_prs=[{"number": 5}])
        after = self.git(self.seed, "ls-remote", "--heads", "origin", self.branch).split()[0]
        self.assertEqual(after, first)
        method, endpoint, payload = self.pr_requests[-1]
        self.assertEqual(method, "PATCH")
        self.assertEqual(endpoint, "repos/xormania/docker-image-library/pulls/5")
        self.assertEqual(set(payload), {"title", "body"})
        self.assertIn("\n\n", payload["body"])

    def test_refresh_with_identical_pins_has_no_changes_and_uv_refresh_is_scoped(self):
        tools = read(self.worker / "images/tools.json")
        digests = {tools[name]["tag"]: tools[name]["digest"] for name in ("composer", "uv", "node")}
        for path in (self.worker / "images").glob("*/definition.json"):
            for line in read(path)["lines"].values():
                if "tag" in line["base"]:
                    digests[line["base"]["tag"]] = line["base"]["digest"]

        def unchanged(url, **kwargs):
            if isinstance(url, refresh.urllib.request.Request):
                url = url.full_url
            if url.endswith("stable.txt"):
                name = url.split("/r/")[1].split("/")[0]
                return io.BytesIO(tools[name + "_version"].encode())
            name = "infection" if "/infection/" in url else "symfony"
            pin = tools[name]
            return io.BytesIO(json.dumps({"tag_name": pin["version"], "assets": [{
                "name": "infection.phar" if name == "infection" else "symfony-cli_linux_amd64.tar.gz",
                "digest": "sha256:" + pin["sha256"], "browser_download_url": pin["url"]}]}).encode())

        paths = list((self.worker / "images").glob("*/definition.json")) + [self.worker / "images/tools.json"]
        before = {path: path.read_bytes() for path in paths}
        with patch.object(refresh, "ROOT", self.worker), \
                patch.object(refresh, "resolve", side_effect=lambda tag: {"digest": digests[tag]}), \
                patch.object(refresh.urllib.request, "urlopen", side_effect=unchanged), \
                patch.object(refresh, "apt_indexes", return_value=tools["apt_indexes"]):
            refresh.refresh()
            self.assertEqual({path: path.read_bytes() for path in paths}, before)
            digests[tools["uv"]["tag"]] = "sha256:" + "f" * 64
            refresh.refresh()
        for path in paths:
            if path.name == "definition.json" and path.parent.name != "python-dev":
                self.assertEqual(path.read_bytes(), before[path])
        python = read(self.worker / "images/python-dev/definition.json")
        self.assertEqual(python["lines"]["3.14-trixie"]["revision"], "1.0.1")

    def test_missing_pr_posts_to_repository_with_explicit_base_and_head(self):
        self.interrupt_after_push()
        self.run_writeback()
        method, endpoint, payload = self.pr_requests[-1]
        self.assertEqual(method, "POST")
        self.assertEqual(endpoint, "repos/xormania/docker-image-library/pulls")
        self.assertEqual(payload["base"], "master")
        self.assertEqual(payload["head"], self.branch)
        self.assertIn("Approve workflows to run", payload["body"])

    def test_writeback_stages_new_generated_root_view(self):
        def outputs(root):
            return {**generated(root), root / "discovery.json": '{"schema_version": 1}\n'}

        with patch.object(writeback, "generated", side_effect=outputs):
            with self.assertRaisesRegex(RuntimeError, "PR creation interrupted"):
                self.run_writeback()
        self.assertEqual(self.git(self.worker, "show", "HEAD:discovery.json"),
                         '{"schema_version": 1}')
        self.assertEqual(self.git(self.worker, "status", "--porcelain", "--", "discovery.json"), "")

    def add_catalog_record(self, line, digest):
        item = record(line, "9.0.0", digest)
        if line.startswith("rust-dev/"):
            item["platforms"][0]["inventory"]["rust_targets"] = ["wasm32-unknown-unknown"]
        path = self.seed / "release-records" / line / "9.0.0.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded(item))
        for path, content in generated(self.seed).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def prepare_catalog_conflict(self, authored=None):
        self.branch = "automation/catalog-42"
        self.git(self.seed, "checkout", "-b", self.branch)
        self.add_catalog_record("python-dev/3.14-trixie", "d")
        if authored:
            path, content = authored
            (self.seed / path).write_text(content + " from automation\n")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Pending Python catalog")
        original = self.git(self.seed, "rev-parse", "HEAD")
        self.git(self.seed, "push", "origin", self.branch)
        self.git(self.seed, "checkout", "master")
        self.add_catalog_record("rust-dev/1.99-trixie", "e")
        if authored:
            path, content = authored
            (self.seed / path).write_text(content + " from master\n")
        else:
            readme = self.seed / "README.md"
            readme.write_text(readme.read_text() + "\nAuthored master prose is preserved.\n")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "Accepted Rust catalog")
        self.git(self.seed, "push", "origin", "master")
        self.git(self.worker, "config", "user.name", "Fixture")
        self.git(self.worker, "config", "user.email", "fixture@example.test")
        return original

    def recover_catalog_branch(self):
        def run(*args, **kwargs):
            return subprocess.run(args, cwd=self.worker, check=True, capture_output=True, **kwargs)
        with patch.object(writeback, "ROOT", self.worker), patch.object(writeback, "run", side_effect=run):
            writeback.prepare_branch(self.branch)

    def test_catalog_conflicts_regenerate_both_releases_and_preserve_authored_prose(self):
        original = self.prepare_catalog_conflict()
        self.recover_catalog_branch()
        self.assertEqual(self.git(self.worker, "diff", "--name-only", "--diff-filter=U"), "")
        self.git(self.worker, "merge-base", "--is-ancestor", original, "HEAD")
        self.assertIn("Authored master prose is preserved.", (self.worker / "README.md").read_text())
        for path, content in generated(self.worker).items():
            self.assertEqual(path.read_text(), content)
        current = read(self.worker / "catalog.json")
        proposed = {(item["line_id"], item["version"]) for item in current["images"]}
        self.assertIn(("python-dev/3.14-trixie", "9.0.0"), proposed)
        self.assertIn(("rust-dev/1.99-trixie", "9.0.0"), proposed)
        self.git(self.worker, "push", "origin", self.branch)

    def test_authored_file_conflict_is_left_for_manual_recovery(self):
        self.prepare_catalog_conflict(("docs/usage.md", "Conflicting authored usage"))
        with self.assertRaisesRegex(RuntimeError, "Authored files.*docs/usage.md"):
            self.recover_catalog_branch()
        self.assertIn("docs/usage.md", self.git(self.worker, "diff", "--name-only", "--diff-filter=U"))

    def test_authored_readme_conflict_is_not_hidden_by_table_regeneration(self):
        # Keep valid generator markers while changing the same prose line.
        original = (self.seed / "README.md").read_text()
        self.prepare_catalog_conflict(("README.md", original.replace("# xorder", "# Conflicting heading", 1)))
        with self.assertRaisesRegex(RuntimeError, "Authored README prose"):
            self.recover_catalog_branch()
        self.assertIn("README.md", self.git(self.worker, "diff", "--name-only", "--diff-filter=U"))


class CatalogDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin.git"
        self.worker = self.root / "worker"
        self.git(self.root, "init", "--bare", "--initial-branch=master", str(self.origin))
        self.git(self.root, "clone", str(self.origin), str(self.worker))
        self.git(self.worker, "config", "user.name", "Fixture")
        self.git(self.worker, "config", "user.email", "fixture@example.test")
        (self.worker / "README.md").write_text("Fixture\n")
        self.git(self.worker, "add", ".")
        self.git(self.worker, "commit", "-m", "Master")
        self.git(self.worker, "push", "origin", "master")
        self.record = record("php-dev/8.4-trixie")

    git = staticmethod(RefreshRecoveryTests.git)

    def publish_branch(self, branch, records):
        self.git(self.worker, "checkout", "-b", branch, "master")
        for item in records:
            path = self.worker / writeback.record_path(item)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded(item))
        self.git(self.worker, "add", ".")
        self.git(self.worker, "commit", "-m", "Pending evidence")
        self.git(self.worker, "push", "origin", branch)
        self.git(self.worker, "checkout", "master")

    def select_branch(self, records, pulls=None):
        def output(*args):
            if args[0] == "gh":
                return json.dumps([pulls or []])
            return subprocess.check_output(args, cwd=self.worker, text=True)
        with patch.object(writeback, "ROOT", self.worker), \
                patch.object(writeback, "output", side_effect=output), \
                patch.object(writeback, "run", side_effect=lambda *args: subprocess.run(args, cwd=self.worker, check=True, capture_output=True)), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder"}):
            return writeback.catalog_branch(records)

    def test_identical_records_deduplicate_across_run_and_documentation_commits(self):
        branch = self.select_branch([self.record])
        self.publish_branch(branch, [self.record])
        (self.worker / "README.md").write_text("Documentation changed\n")
        self.git(self.worker, "add", ".")
        self.git(self.worker, "commit", "-m", "Unrelated documentation")
        self.git(self.worker, "push", "origin", "master")
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "entirely-new-run"}):
            self.assertEqual(self.select_branch([self.record]), branch)

    def test_complete_source_and_verification_facts_change_proposal_identity(self):
        other = record("python-dev/3.14-trixie")
        self.assertEqual(writeback.catalog_identity([self.record, other]), writeback.catalog_identity([other, self.record, other]))
        original = writeback.catalog_identity([self.record])
        for field, value in (("source_commit", "c" * 40), ("verification", {**self.record["verification"], "evidence": "https://example.test/new-verification"})):
            with self.subTest(field=field):
                changed = {**self.record, field: value}
                self.assertNotEqual(writeback.catalog_identity([changed]), original)
        with self.assertRaisesRegex(RuntimeError, "Conflicting"):
            writeback.catalog_identity([self.record, {**self.record, "source_commit": "c" * 40}])

    def test_existing_run_id_pending_pr_is_reused_when_it_contains_the_exact_records(self):
        legacy = "automation/catalog-42"
        self.publish_branch(legacy, [self.record, record("python-dev/3.14-trixie")])
        pull = {"head": {"ref": legacy, "repo": {"full_name": "xormania/xorder"}}}
        self.assertEqual(self.select_branch([self.record], [pull]), legacy)
        changed = {**self.record, "source_commit": "c" * 40}
        self.assertNotEqual(self.select_branch([changed], [pull]), legacy)

    def test_fork_or_non_catalog_branches_do_not_control_automation(self):
        pulls = [{"head": {"ref": "automation/catalog-42", "repo": {"full_name": "attacker/xorder"}}},
                 {"head": {"ref": "master", "repo": {"full_name": "xormania/xorder"}}}]
        self.assertEqual(self.select_branch([self.record], pulls), "automation/catalog-" + writeback.catalog_identity([self.record])[:24])


if __name__ == "__main__":
    unittest.main()
