"""Exact evidence binding, scanner failures, and credential-free consumer verification."""
import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import image_assurance as assurance
import release
from library import ROOT, encoded, read, validate_record
from test_library import record

IMAGE = "ghcr.io/xormania/php-dev@sha256:" + "d" * 64
SOURCE = "f" * 40
WORKFLOW_SOURCE = "a" * 40
EVIDENCE = "https://github.com/xormania/xorder/actions/runs/42"


def report(findings=None):
    return {"SchemaVersion": 2, "Metadata": {"RepoDigests": [IMAGE], "OS": {"Family": "debian"}},
            "Results": [{"Target": "Debian", "Class": "os-pkgs", "Vulnerabilities": findings or []}]}


def envelope(predicate, digest="d" * 64):
    statement = {"subject": [{"name": "image", "digest": {"sha256": digest}}], "predicate": predicate}
    return json.dumps({"payload": base64.b64encode(json.dumps(statement).encode()).decode()})


class AssuranceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"GITHUB_REPOSITORY": "xormania/xorder"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.report = report()
        self.sbom = {"bomFormat": "CycloneDX", "components": [{"name": "libc"}]}
        files = {}
        for name, payload in (("vulnerabilities", self.report), ("sbom", self.sbom),
                              ("scanner", {"Version": assurance.TRIVY["version"], "VulnerabilityDB": {"UpdatedAt": "2026-10-11T00:00:00Z"}})):
            temporary = self.folder / name
            temporary.write_text(encoded(payload))
            digest = assurance.sha256(temporary)
            path = self.folder / (name + "-" + digest + ".json")
            temporary.rename(path)
            files[name] = {"filename": path.name, "sha256": digest}
        self.receipt = {"schema_version": 1, "artifact": IMAGE, "source_commit": SOURCE,
                        "completed_at": "2026-10-11T00:00:00Z", "evidence": EVIDENCE,
                        "certificate_identity": assurance.IDENTITY, "certificate_oidc_issuer": assurance.ISSUER,
                        "predicate_type": assurance.PREDICATE, "scanner": {"name": "trivy", **assurance.TRIVY},
                        "scan": assurance.scan_summary(self.report), "files": files}
        (self.folder / "assurance.json").write_text(encoded(self.receipt))

    def test_scan_gate_retains_high_and_unfixed_critical_instead_of_claiming_no_findings(self):
        result = assurance.scan_summary(report([
            {"VulnerabilityID": "CVE-test1", "Severity": "HIGH", "FixedVersion": "2"},
            {"VulnerabilityID": "CVE-test2", "Severity": "CRITICAL"},
        ]))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["counts"]["HIGH"], 1)
        self.assertEqual(result["counts"]["CRITICAL"], 1)
        result = assurance.scan_summary(report([{"VulnerabilityID": "CVE-test3", "Severity": "CRITICAL", "FixedVersion": "2"}]))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["fixable_critical"][0]["id"], "CVE-test3")

    def test_empty_malformed_or_unsupported_scanner_output_is_not_a_pass(self):
        for value in ({}, {"SchemaVersion": 3, "Results": []},
                      {"SchemaVersion": 2, "Results": [{}]},
                      report([{"VulnerabilityID": "CVE-test", "Severity": "BOGUS"}])):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assurance.scan_summary(value)

    def test_receipt_rejects_substituted_digest_source_identity_and_policy(self):
        for path, value in ((["artifact"], IMAGE.replace("d" * 64, "e" * 64)),
                            (["source_commit"], "a" * 40), (["certificate_identity"], "attacker"),
                            (["scan", "policy"], "advisory"), (["files", "sbom", "filename"], "../escape")):
            changed = copy.deepcopy(self.receipt)
            parent = changed
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                assurance.validate_receipt(changed, IMAGE, SOURCE)

    def test_authenticated_attestation_must_contain_expected_predicate_and_subject(self):
        for result in (envelope(self.receipt, "e" * 64), envelope({"different": "predicate"})):
            with patch.object(assurance, "run", return_value=result), self.assertRaisesRegex(ValueError, "expected predicate"):
                assurance.verify_attestation(IMAGE, assurance.PREDICATE, self.receipt, {})
        with patch.object(assurance, "run", return_value=envelope(self.receipt)):
            assurance.verify_attestation(IMAGE, assurance.PREDICATE, self.receipt, {})

    def test_consumer_checks_evidence_before_crypto_and_strips_publication_credentials(self):
        def commands(*args, env=None):
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("REGISTRY_AUTH_FILE", env)
            self.assertNotEqual(env["DOCKER_CONFIG"], "/publisher")
            self.assertEqual(read(Path(env["DOCKER_CONFIG"]) / "config.json"), {"auths": {}})
            self.assertIn(assurance.IDENTITY, args)
            self.assertIn(assurance.ISSUER, args)
            if args[1] == "verify-attestation":
                return envelope(self.sbom if args[3] == "cyclonedx" else self.receipt)
            return "[]"
        with patch.dict(os.environ, {"GH_TOKEN": "private", "GITHUB_TOKEN": "private", "DOCKER_CONFIG": "/publisher", "REGISTRY_AUTH_FILE": "/private"}), \
                patch.object(assurance, "run", side_effect=commands) as run:
            self.assertEqual(assurance.verify_local(self.receipt, self.folder), self.receipt)
            self.assertEqual(run.call_count, 3)
        (self.folder / self.receipt["files"]["sbom"]["filename"]).write_text("corruption")
        with patch.object(assurance, "run") as run, self.assertRaisesRegex(ValueError, "checksum"):
            assurance.verify_local(self.receipt, self.folder)
        run.assert_not_called()

    def test_changed_scan_policy_is_detected_even_if_file_hash_is_replaced(self):
        self.receipt["scan"]["counts"]["CRITICAL"] = 50
        with patch.object(assurance, "run") as run, self.assertRaisesRegex(ValueError, "differs"):
            assurance.verify_local(self.receipt, self.folder)
        run.assert_not_called()

    def test_historical_unsigned_records_remain_valid_but_cannot_claim_assurance(self):
        old = record("php-dev/8.4-trixie")
        validate_record(old)
        with self.assertRaisesRegex(ValueError, "historical release"):
            assurance.verify_record(old, self.folder)

    def test_receipt_uploaded_last_and_retry_reuses_original_database_and_time(self):
        calls = []
        with patch.object(release, "gh", return_value="[[]]"), \
                patch.object(release, "run", side_effect=lambda *args: calls.append(args)), \
                patch.object(assurance, "create", return_value=self.receipt):
            link = release.stage_assurance("php-dev/8.4-trixie/v1.0.0", SOURCE, IMAGE, EVIDENCE, self.folder)
        uploads = [args[-1] for args in calls if args[:3] == ("gh", "release", "upload")]
        creation = next(args for args in calls if args[:3] == ("gh", "release", "create"))
        self.assertEqual(creation[creation.index("--target") + 1], SOURCE)
        self.assertEqual(uploads[-1], str(self.folder / "assurance.json"))
        self.assertEqual(len(uploads), 4)
        assets = {"tag_name": "php-dev/8.4-trixie/v1.0.0", "target_commitish": SOURCE,
                  "assets": [{"name": "assurance.json"}]}
        with patch.object(release, "gh", return_value=json.dumps([[assets]])), \
                patch.object(release, "run"), patch.object(assurance, "create") as create, \
                patch.object(assurance, "verify_local") as verify:
            recovered = release.stage_assurance(assets["tag_name"], SOURCE, IMAGE, "new run", self.folder)
        self.assertEqual(recovered, link)
        create.assert_not_called()
        verify.assert_called_once()

    def test_sidecar_target_and_recovered_receipt_bind_producer_without_changing_image_source(self):
        tag = "image-assurance/php-dev/8.4-trixie/v1.0.0/42-1"
        self.receipt["assurance_workflow_commit"] = WORKFLOW_SOURCE
        (self.folder / "assurance.json").write_text(encoded(self.receipt))
        calls = []
        with patch.object(release, "gh", return_value="[[]]"), \
                patch.object(release, "run", side_effect=lambda *args: calls.append(args)), \
                patch.object(assurance, "create", return_value=self.receipt) as create:
            link = release.stage_assurance(tag, SOURCE, IMAGE, EVIDENCE, self.folder, release_target=WORKFLOW_SOURCE)
        creation = next(args for args in calls if args[:3] == ("gh", "release", "create"))
        self.assertEqual(creation[creation.index("--target") + 1], WORKFLOW_SOURCE)
        self.assertEqual(create.call_args.args[:2], (IMAGE, SOURCE))
        self.assertEqual(self.receipt["source_commit"], SOURCE)
        existing = {"tag_name": tag, "target_commitish": WORKFLOW_SOURCE, "assets": [{"name": "assurance.json"}]}
        with patch.object(release, "gh", side_effect=lambda *args: json.dumps([[existing]])), \
                patch.object(release, "run"), patch.object(assurance, "create") as create, \
                patch.object(assurance, "verify_local") as verify:
            self.assertEqual(release.stage_assurance(tag, SOURCE, IMAGE, "retry", self.folder,
                                                    release_target=WORKFLOW_SOURCE), link)
            create.assert_not_called()
            verify.assert_called_once()
            existing["target_commitish"] = SOURCE
            with self.assertRaisesRegex(RuntimeError, "another target commit"):
                release.stage_assurance(tag, SOURCE, IMAGE, "retry", self.folder, release_target=WORKFLOW_SOURCE)
            existing["target_commitish"] = WORKFLOW_SOURCE
            self.receipt["assurance_workflow_commit"] = SOURCE
            (self.folder / "assurance.json").write_text(encoded(self.receipt))
            with self.assertRaisesRegex(RuntimeError, "receipt producer differs"):
                release.stage_assurance(tag, SOURCE, IMAGE, "retry", self.folder, release_target=WORKFLOW_SOURCE)

    def test_scan_failure_does_not_sign_or_publish_claims(self):
        def scanner(*args, env=None):
            self.assertFalse(any(key.startswith("TRIVY_") for key in env))
            self.assertEqual(Path(args[args.index("--config") + 1]).read_text(), "{}\n")
            if "version" in args:
                return json.dumps({"Version": assurance.TRIVY["version"], "VulnerabilityDB": {"UpdatedAt": "2026-10-11"}})
            if args[0] != "trivy":
                self.fail("Signing must not occur after a blocked scan")
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("TRIVY_USERNAME", env)
            self.assertNotIn("TRIVY_PASSWORD", env)
            self.assertNotIn("TRIVY_REGISTRY_TOKEN", env)
            self.assertEqual(read(Path(env["DOCKER_CONFIG"]) / "config.json"), {"auths": {}})
            self.assertEqual(Path(args[args.index("--ignorefile") + 1]).read_text(), "")
            path = Path(args[args.index("--output") + 1])
            value = self.sbom if "cyclonedx" in args else report([{"VulnerabilityID": "CVE-test", "Severity": "CRITICAL", "FixedVersion": "2"}])
            path.write_text(encoded(value))
            return ""
        with patch.dict(os.environ, {"GITHUB_WORKFLOW_REF": assurance.IDENTITY.removeprefix("https://github.com/"),
                                    "GH_TOKEN": "publisher", "TRIVY_USERNAME": "publisher",
                                    "TRIVY_PASSWORD": "private", "TRIVY_REGISTRY_TOKEN": "private",
                                    "TRIVY_SEVERITY": "LOW", "TRIVY_IGNOREFILE": "/publisher/ignore"}), \
                patch.object(assurance, "run", side_effect=scanner), self.assertRaisesRegex(RuntimeError, "scan blocked"):
            assurance.create(IMAGE, SOURCE, EVIDENCE, self.folder / "blocked")
        self.assertEqual(read(self.folder / "blocked/assurance.json")["scan"]["status"], "blocked")

    def test_signing_refuses_a_pull_request_or_fork_workflow(self):
        for workflow in ("xormania/xorder/.github/workflows/publish.yml@refs/pull/1/merge",
                         "attacker/xorder/.github/workflows/publish.yml@refs/heads/master"):
            with patch.dict(os.environ, {"GITHUB_WORKFLOW_REF": workflow}), \
                    patch.object(assurance, "run") as run, self.assertRaisesRegex(ValueError, "master publication"):
                assurance.create(IMAGE, SOURCE, EVIDENCE, self.folder)
            run.assert_not_called()

    def test_image_assurance_changes_do_not_request_new_image_builds(self):
        from library import affected, definitions
        self.assertEqual(affected(["scripts/image_assurance.py", ".github/workflows/publish.yml",
                                   ".github/workflows/catalog.yml"], definitions()), [])

    def test_assurance_only_publication_does_not_rewrite_or_reverify_the_original_record(self):
        original = record("php-dev/8.4-trixie")
        path = self.folder / "release-records/php-dev/8.4-trixie/1.0.0.json"
        path.parent.mkdir(parents=True)
        path.write_text(encoded(original))
        before = path.read_bytes()
        artifact = original["publication"]["repository"] + "@" + original["publication"]["digest"]
        summary = {"receipt_url": "https://github.com/xormania/xorder/releases/download/image-assurance/assurance.json",
                   "receipt_sha256": "a" * 64, "predicate_type": assurance.PREDICATE}
        with patch.object(assurance, "ROOT", self.folder), \
                patch("registry.resolve", return_value={"digest": original["publication"]["digest"]}), \
                patch.object(release, "stage_assurance", return_value=summary) as stage, \
                patch.object(assurance, "verify_published") as verify, \
                patch.object(assurance, "run") as run, \
                patch.dict(os.environ, {"GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": WORKFLOW_SOURCE}):
            publication = assurance.assure_existing(path, self.folder / "sidecar")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(publication["artifact"], artifact)
        self.assertEqual(publication["source_commit"], original["source_commit"])
        self.assertIn("/42-2", stage.call_args.args[0])
        self.assertEqual(stage.call_args.args[1], original["source_commit"])
        self.assertEqual(stage.call_args.kwargs, {"release_target": WORKFLOW_SOURCE})
        verify.assert_called_once()
        self.assertEqual(run.call_args.args[:3], ("gh", "release", "edit"))
        self.assertIn("Assurance producer and evidence Release target: " + WORKFLOW_SOURCE, run.call_args.args[-1])

    def test_sidecar_requires_valid_execution_commit_instead_of_falling_back_to_image_source(self):
        original = record("php-dev/8.4-trixie")
        path = self.folder / "release-records/php-dev/8.4-trixie/1.0.0.json"
        path.parent.mkdir(parents=True)
        path.write_text(encoded(original))
        for env in ({}, {"GITHUB_SHA": ""}, {"GITHUB_SHA": "master"}, {"GITHUB_SHA": "f" * 39}):
            with self.subTest(env=env), \
                    patch.dict(os.environ, env, clear=True), patch.object(assurance, "ROOT", self.folder), \
                    patch("registry.resolve") as resolve, patch.object(release, "stage_assurance") as stage, \
                    self.assertRaisesRegex(ValueError, "executing workflow's exact commit"):
                assurance.assure_existing(path, self.folder / "sidecar")
            resolve.assert_not_called()
            stage.assert_not_called()

    def test_sidecar_verification_requires_the_consumers_explicit_digest_pin(self):
        publication = {"artifact": IMAGE, "source_commit": SOURCE, "assurance": {}}
        with patch.object(assurance, "download") as download, self.assertRaisesRegex(ValueError, "pinned image"):
            assurance.verify_published(publication, IMAGE.replace("d" * 64, "e" * 64), self.folder)
        download.assert_not_called()

    def test_push_smoke_selects_an_accepted_digest_only_for_changed_assurance_inputs(self):
        old = record("python-dev/3.14-trixie")
        newer = record("python-dev/3.14-trixie", "1.0.1")
        with patch.object(assurance.subprocess, "check_output", return_value=""), \
                patch("library.records") as accepted:
            self.assertEqual(assurance.smoke_record("base"), "")
            accepted.assert_not_called()
        with patch.object(assurance.subprocess, "check_output", return_value="scripts/image_assurance.py\n"), \
                patch("library.records", return_value=[old, newer]):
            self.assertEqual(assurance.smoke_record("base"), "release-records/python-dev/3.14-trixie/1.0.1.json")

    def test_optional_assurance_surfaces_in_generic_discovery_without_claiming_old_records_are_signed(self):
        from xorder.model import image_entry, validate_schema
        old = record("php-dev/8.4-trixie")
        self.assertNotIn("assurance", image_entry(old))
        old["assurance"] = {"receipt_url": "https://github.com/xormania/xorder/releases/download/source/assurance.json",
                            "receipt_sha256": "a" * 64, "predicate_type": assurance.PREDICATE}
        entry = image_entry(old)
        self.assertEqual(entry["assurance"], old["assurance"])
        validate_schema({"schema_version": 2, "generated_at": old["created_at"], "resources": [entry]}, "catalog-v2.schema.json")

    def test_publication_workflow_keeps_browser_consumer_isolated(self):
        workflow = (ROOT / ".github/workflows/publish.yml").read_text()
        parity = workflow.split("  browser-parity:\n", 1)[1].split("  publish-browser:\n", 1)[0]
        self.assertIn("permissions: {}", parity)
        self.assertNotIn("GH_TOKEN", parity)
        self.assertNotIn("id-token", parity)
        self.assertNotIn("login-action", parity)
        self.assertEqual(workflow.count("id-token: write"), 3)
        self.assertEqual(workflow.count("cosign-installer@ba7bc0a3fef59531c69a25acd34668d6d3fe6f22"), 3)

    def test_admin_proposal_preserves_existing_check_sources_and_guards_changed_structure(self):
        document = (ROOT / "docs/repository-gates.md").read_text()
        script = document.split("python3 - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        folder = self.folder / "out/admin"
        folder.mkdir(parents=True)
        observed = {"name": "master", "target": "branch", "enforcement": "active",
                    "rules": [{"type": "required_status_checks", "parameters": {
                        "strict_required_status_checks_policy": True,
                        "required_status_checks": [{"context": "checks", "integration_id": 123},
                                                   {"context": "existing-ci", "integration_id": 456}]}}]}
        path = folder / "master-ruleset-observed.json"
        path.write_text(encoded(observed))
        subprocess.run([sys.executable, "-c", script], cwd=self.folder, check=True)
        proposed = read(folder / "master-ruleset-proposed.json")
        self.assertEqual(proposed["rules"][0]["parameters"]["required_status_checks"],
                         [{"context": "checks", "integration_id": 123},
                          {"context": "existing-ci", "integration_id": 456},
                          {"context": "catalog-evidence", "integration_id": 15368}])
        self.assertTrue(proposed["rules"][0]["parameters"]["strict_required_status_checks_policy"])
        self.assertEqual(read(path), observed)
        observed["rules"].append(copy.deepcopy(observed["rules"][0]))
        path.write_text(encoded(observed))
        result = subprocess.run([sys.executable, "-c", script], cwd=self.folder, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("structure changed", result.stderr)
