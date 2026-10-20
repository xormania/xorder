import contextlib
import io
import json
import os
import sys
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validation_base
from validation_base import main

BASE, GOOD, HEAD = "a" * 40, "b" * 40, "c" * 40
TREE, OTHER_TREE = "d" * 40, "e" * 40
REPOSITORY = "example/repository"


def run(commit=GOOD, number=22, base=BASE, conclusion="success", event="pull_request"):
    return {"id": 123, "run_attempt": 1, "head_sha": commit, "status": "completed", "conclusion": conclusion, "event": event,
            "pull_requests": [{"number": number, "base": {"sha": base}}],
            "context": {"schema_version": 1, "repository": REPOSITORY, "run_id": 123, "run_attempt": 1,
                        "number": number, "event": event, "head_sha": commit, "base_sha": base,
                        "checkout_sha": "f" * 40, "checkout_tree": TREE, "checkout_parents": [base, commit]}}


def select_context(runs, number, head, base, ancestor, **overrides):
    options = {"evidence": lambda item: item["context"], "repository": REPOSITORY,
               "checkout_tree": TREE, "get_tree": lambda _: TREE, **overrides}
    return validation_base.select_context(runs, number, head, base, ancestor, **options)


def select(runs, number, head, base, ancestor=lambda *_: False, **overrides):
    return select_context(runs, number, head, base, ancestor, **overrides)["sha"]


class ValidationBaseTests(unittest.TestCase):
    def test_successful_ancestral_validation_can_scope_the_next_update(self):
        ancestors = {(GOOD, HEAD), (BASE, GOOD)}
        self.assertEqual(select([run()], 22, HEAD, BASE, lambda *pair: pair in ancestors), GOOD)

    def test_failed_cancelled_other_pr_or_changed_base_cannot_skip_work(self):
        for candidate in (run(conclusion="failure"), run(conclusion="cancelled"),
                          {**run(), "status": "in_progress"},
                          run(number=21), run(base="d" * 40), run(event="workflow_dispatch"),
                          run(commit="invalid")):
            with self.subTest(candidate=candidate):
                self.assertEqual(select([candidate], 22, HEAD, BASE, lambda *_: True), BASE)

    def test_force_pushed_unrelated_heads_and_empty_history_use_full_delta(self):
        self.assertEqual(select([run()], 22, HEAD, BASE, lambda *_: False), BASE)
        self.assertEqual(select([], 22, HEAD, BASE), BASE)

    def test_an_unchanged_successful_head_needs_no_repeat_image_build(self):
        context = select_context([run(commit=HEAD)], 22, HEAD, BASE, lambda old, new: old == new)
        self.assertEqual(context, {"sha": HEAD, "head": HEAD, "reused": True, "same_head": True})

    def test_new_head_cannot_reuse_a_source_that_did_not_contain_the_base(self):
        context = select_context([run()], 22, HEAD, BASE, lambda *pair: pair == (GOOD, HEAD))
        self.assertEqual(context, {"sha": BASE, "head": "HEAD", "reused": False, "same_head": False})

    def test_changed_base_and_unavailable_history_use_the_merge_checkout(self):
        for candidates in ([run(base="d" * 40)], []):
            with self.subTest(candidates=candidates):
                self.assertEqual(select_context(candidates, 22, HEAD, BASE, lambda *_: True),
                                 {"sha": BASE, "head": "HEAD", "reused": False, "same_head": False})

    def test_search_continues_past_unusable_newer_runs(self):
        self.assertEqual(select([run(commit="d" * 40), run()], 22, HEAD, BASE,
                                lambda *pair: pair in {(GOOD, HEAD), (BASE, GOOD)}), GOOD)

    def test_old_runs_without_durable_evidence_cannot_reuse_work(self):
        self.assertEqual(validation_base.select([run()], 22, HEAD, BASE, lambda *_: True), BASE)
        self.assertEqual(select([run()], 22, HEAD, BASE, lambda *_: True, evidence=lambda _: None), BASE)

    def test_mutable_pull_request_associations_do_not_prove_the_tested_base(self):
        candidate = run(base="f" * 40)
        candidate["pull_requests"] = [{"number": 22, "base": {"sha": BASE}}]
        self.assertEqual(select([candidate], 22, HEAD, BASE, lambda *_: True), BASE)
        candidate = run()
        candidate["pull_requests"] = []
        self.assertEqual(select([candidate], 22, HEAD, BASE, lambda *_: True), GOOD)

    def test_forged_or_mismatched_proof_cannot_reuse_work(self):
        for field, value in (("schema_version", True), ("repository", "other/repo"), ("run_id", 124),
                             ("run_attempt", 2), ("number", 23), ("event", "workflow_dispatch"),
                             ("head_sha", HEAD), ("base_sha", "f" * 40), ("checkout_sha", "invalid"),
                             ("checkout_tree", OTHER_TREE), ("checkout_parents", [GOOD, BASE])):
            candidate = run()
            candidate["context"][field] = value
            with self.subTest(field=field):
                self.assertEqual(select([candidate], 22, HEAD, BASE, lambda *_: True), BASE)

    def test_same_head_requires_the_actual_previously_tested_merge_tree(self):
        self.assertEqual(select([run(commit=HEAD)], 22, HEAD, BASE, lambda *_: True,
                                checkout_tree=OTHER_TREE), BASE)
        self.assertEqual(select([run()], 22, HEAD, BASE, lambda *_: True, get_tree=lambda _: None), BASE)

    def test_candidate_evidence_downloads_are_bounded(self):
        candidates = [run() for _ in range(12)]
        seen = []
        self.assertEqual(select(candidates, 22, HEAD, BASE, lambda *_: True,
                                evidence=lambda item: seen.append(item)), BASE)
        self.assertEqual(len(seen), 10)


class ValidationArtifactTests(unittest.TestCase):
    def archive(self, entries):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return content.getvalue()

    def listing(self, size, **changes):
        return {"artifacts": [{"id": 456, "name": "validation-context-1", "expired": False,
                               "size_in_bytes": size, **changes}]}

    def test_valid_context_is_read_without_extracting_and_uses_canonical_download_endpoint(self):
        candidate = run()
        archive = self.archive([("validation-context.json", json.dumps(candidate["context"]))])
        listing = self.listing(len(archive), archive_download_url="https://attacker.test/ignored")
        with patch("validation_base.api_bytes", side_effect=[json.dumps(listing).encode(), archive]) as read:
            self.assertEqual(validation_base.artifact_context(candidate, REPOSITORY, "token"), candidate["context"])
        self.assertEqual(read.call_args_list[1].args[0], "https://api.github.com/repos/example/repository/actions/artifacts/456/zip")

    def test_missing_expired_duplicate_and_oversized_artifacts_are_unusable(self):
        listings = [{"artifacts": []}, {"artifacts": [None]}, {"artifacts": "invalid"}, [],
                    self.listing(100, expired=True), self.listing(65537)]
        duplicate = self.listing(100)
        duplicate["artifacts"] *= 2
        listings.append(duplicate)
        for listing in listings:
            with self.subTest(listing=listing), patch("validation_base.api_bytes", return_value=json.dumps(listing).encode()) as read:
                self.assertIsNone(validation_base.artifact_context(run(), REPOSITORY, "token"))
                self.assertEqual(read.call_count, 1)

    def test_archive_members_and_uncompressed_context_size_are_bounded(self):
        for entries in ([("unexpected.json", "{}")], [("validation-context.json", "{}"), ("extra", "x")],
                        [("validation-context.json", " " * 8193)]):
            archive = self.archive(entries)
            with self.subTest(entries=[name for name, _ in entries]), \
                    patch("validation_base.api_bytes", side_effect=[json.dumps(self.listing(len(archive))).encode(), archive]):
                self.assertIsNone(validation_base.artifact_context(run(), REPOSITORY, "token"))

    def test_encrypted_and_unsupported_compression_members_are_unusable(self):
        original = self.archive([("validation-context.json", "{}")])
        for kind in ("encrypted", "unsupported"):
            archive = bytearray(original)
            central = archive.index(b"PK\x01\x02")
            if kind == "encrypted":
                archive[6:8] = (1).to_bytes(2, "little")
                archive[central + 8:central + 10] = (1).to_bytes(2, "little")
            else:
                archive[8:10] = (99).to_bytes(2, "little")
                archive[central + 10:central + 12] = (99).to_bytes(2, "little")
            with self.subTest(kind=kind), patch("validation_base.api_bytes", side_effect=[
                    json.dumps(self.listing(len(archive))).encode(), bytes(archive)]):
                self.assertIsNone(validation_base.artifact_context(run(), REPOSITORY, "token"))

    def test_api_downloads_are_bounded_and_drop_authorization_on_redirect(self):
        with patch("validation_base.urlopen", return_value=io.BytesIO(b"{}")) as open_url:
            self.assertEqual(validation_base.api_bytes("https://api.github.com/data", "token", 8), b"{}")
            request = open_url.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer token")
            redirected = urllib.request.HTTPRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "https://assets.example.test/archive")
            self.assertIsNone(redirected.get_header("Authorization"))
        with patch("validation_base.urlopen", return_value=io.BytesIO(b"x" * 9)), self.assertRaises(ValueError):
            validation_base.api_bytes("https://api.github.com/data", "token", 8)
        with self.assertRaises(ValueError):
            validation_base.api_bytes("https://attacker.test/data", "token", 8)


class ValidationBaseCommandTests(unittest.TestCase):
    def invoke(self, args, env):
        output = io.StringIO()
        with patch.object(sys, "argv", ["validation_base.py", *args]), \
                patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            main()
        return output.getvalue()

    def test_legacy_stdout_remains_the_base_only(self):
        self.assertEqual(self.invoke([], {"BASE_SHA": BASE}), BASE + "\n")

    def test_full_manual_and_scheduled_contexts_cannot_skip_metadata(self):
        output = self.invoke(["--github-output"], {})
        self.assertEqual(dict(line.split("=", 1) for line in output.splitlines()),
                         {"sha": "", "head": "HEAD", "reused": "false", "same_head": "false"})

    def test_unavailable_run_history_checks_the_merge_checkout_and_full_metadata(self):
        env = {"BASE_SHA": BASE, "HEAD_SHA": HEAD, "PR_NUMBER": "22",
               "GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "example/repository"}
        checkout = {"base_sha": BASE, "checkout_tree": TREE}
        with patch("validation_base.observed_checkout", return_value=checkout), \
                patch("validation_base.urlopen", side_effect=URLError("unavailable")), \
                contextlib.redirect_stderr(io.StringIO()):
            output = self.invoke(["--github-output"], env)
        self.assertEqual(dict(line.split("=", 1) for line in output.splitlines()),
                         {"sha": BASE, "head": "HEAD", "reused": "false", "same_head": "false"})

    def test_unproved_pr_checkout_requires_all_runtime_checks(self):
        env = {"BASE_SHA": BASE, "HEAD_SHA": HEAD, "PR_NUMBER": "22"}
        with patch("validation_base.observed_checkout", return_value={"base_sha": None, "checkout_tree": TREE}):
            output = self.invoke(["--github-output"], env)
        self.assertEqual(dict(line.split("=", 1) for line in output.splitlines()),
                         {"sha": "", "head": "HEAD", "reused": "false", "same_head": "false"})

    def test_actual_merge_base_controls_selection_when_the_event_base_is_stale(self):
        env = {"BASE_SHA": "f" * 40, "HEAD_SHA": HEAD, "PR_NUMBER": "22"}
        with patch("validation_base.observed_checkout", return_value={"base_sha": BASE, "checkout_tree": TREE}):
            output = self.invoke(["--github-output"], env)
        self.assertEqual(dict(line.split("=", 1) for line in output.splitlines())["sha"], BASE)
