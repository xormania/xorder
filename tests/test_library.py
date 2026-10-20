import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from library import ROOT, affected, catalog, definitions, generated, select, validate_record
from release import alias_eligible, exact_guard
import release
from library import fingerprint, pending_releases
from unittest.mock import patch
import tempfile


def record(line, revision="1.0.0", digest="a"):
    d = copy.deepcopy(definitions()[line]); d["revision"] = revision
    inv = {"platform": "linux/amd64", "runtime_version": d["runtime_line"] + ".1",
           "os": {"VERSION_CODENAME": "trixie", "PRETTY_NAME": "Debian 13"},
           "extensions": {e: "test" for e in d["extensions"]}, "tools": {t: "test" for t in d["tools"]}}
    if "node" in d["capabilities"]:
        inv["tools"].update(node="v22.1.0", npm="10.1.0")
    if d["family"] == "php-browser":
        inv["tools"].update(chromium="Chromium 140.0", chromedriver="ChromeDriver 140.0")
    if d["family"] == "php-toolkit":
        inv["prepared_projects"] = {
            "validator": {"composer_lock_sha256": "0" * 64, "packages": {"symfony/ux-toolkit": "v3.5.1"}},
            "symfony-7.4": {"composer_lock_sha256": "1" * 64, "packages": {
                "symfony/ux-toolkit": "v3.5.1", "symfony/framework-bundle": "v7.4.1"}},
        }
    if d["family"] == "python-matrix":
        inv["interpreters"] = {minor: {"version": minor + ".1", "executable": "/usr/local/bin/python" + minor,
                                      "sqlite_version": "3.46.1"} for minor in ("3.10", "3.12", "3.14")}
        inv["tools"]["tmux"] = "tmux 3.5a"
    return {"schema_version": 1, "line_id": line, "version": revision, "source_commit": "b" * 40,
            "source_tag": line + "/v" + revision, "created_at": "2026-01-01T00:00:00Z", "definition": d,
            "resolved_base": "test@sha256:" + "c" * 64, "tools": {}, "input_fingerprint": "d" * 64,
            "lifecycle": "available", "platforms": [{"platform": "linux/amd64", "digest": "sha256:" + digest * 64, "inventory": inv}],
            "publication": {"repository": "ghcr.io/xormania/" + d["family"], "digest": "sha256:" + digest * 64,
                            "exact_tag": d["line"] + "-v" + revision, "public_pull_verified_at": "2026-01-01T00:00:00Z", "evidence": "https://example.test/ci"},
            "verification": {"status": "passed", "surface": "github-actions-linux-amd64", "completed_at": "2026-01-01T00:00:00Z", "evidence": "https://example.test/ci"}}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.cat = catalog([record("php-dev/8.4-trixie"), record("php-browser/8.4-trixie", digest="e")])

    def test_empty_catalog_does_not_offer_definitions(self):
        self.assertEqual(catalog([])["images"], [])
        self.assertEqual(select(catalog([]), {"runtime_line": "8.4"})["status"], "no_matching_image")

    def test_mock_requirements_have_independent_expected_outcomes(self):
        for name, expected in [("php", "php-dev/8.4-trixie"), ("browser", "php-browser/8.4-trixie"), ("missing-runtime", None), ("missing-capability", None)]:
            with self.subTest(name=name):
                requirements = json.loads((ROOT / "tests/requirements" / (name + ".json")).read_text())
                result = select(self.cat, requirements)
                if expected:
                    self.assertEqual(result["image"]["line_id"], expected)
                else:
                    self.assertEqual(result["status"], "no_matching_image")

    def test_preserve_existing_pin_even_when_new_revision_available(self):
        newer = record("php-dev/8.4-trixie", "1.0.1", "f")
        cat = catalog([record("php-dev/8.4-trixie"), newer])
        req = {"runtime_line": "8.4", "pinned_digest": cat["images"][0]["digest_reference"]}
        result = select(cat, req)
        self.assertTrue(result["preserved_pin"])
        self.assertEqual(result["image"]["version"], "1.0.0")
        req["pinned_digest"] = "unknown"
        self.assertEqual(select(cat, req)["status"], "pin_unverified_or_incompatible")

    def test_unverified_inventory_and_withdrawal_are_rejected(self):
        r = record("php-dev/8.4-trixie")
        del r["platforms"][0]["inventory"]["extensions"]["intl"]
        with self.assertRaises(AssertionError): validate_record(r)
        r = record("php-dev/8.4-trixie"); r["lifecycle"] = "withdrawn"
        with self.assertRaises(AssertionError): validate_record(r)

    def test_docs_only_change_has_no_image_builds(self):
        self.assertEqual(affected(["README.md", "docs/usage.md", "catalog.json", "release-records/php-dev/8.4-trixie/1.0.0.json"], definitions()), [])
        self.assertEqual(affected(["images/php-browser/Dockerfile"], definitions()), ["php-dev/8.4-trixie", "php-dev/8.5-trixie"])
        self.assertIn("rust-dev/1.99-trixie", affected(["images/shared/install.sh"], definitions()))

    def test_metadata_and_fixture_changes_select_only_their_consumers(self):
        defs = definitions()
        self.assertEqual(affected(["scripts/release.py", "scripts/writeback.py", "tests/test_library.py", "tests/requirements/php.json", ".github/workflows/refresh.yml"], defs), [])
        self.assertEqual(affected(["tests/fixtures/php/composer.lock"], defs), ["php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["tests/fixtures/python/uv.lock"], defs), ["python-dev/3.14-trixie"])
        self.assertEqual(affected(["tests/fixtures/rust/Cargo.lock"], defs), ["rust-dev/1.99-trixie"])
        self.assertEqual(len(affected(["images/tools.json"], defs)), 8)
        self.assertEqual(affected(["examples/uxor/runner.py"], defs), ["php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["examples/uxor/run.sh"], defs), ["php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["examples/shared/network.py"], defs), ["php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["examples/shared/proxy_relay.py"], defs), ["php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["tests/fixtures/network/check.py"], defs), ["php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(len(affected(["scripts/new-build-helper.py"], defs)), 8)
        self.assertEqual(len(affected([".github/workflows/new-image-check.yml"], defs)), 8)

    def test_unrelated_tool_pins_do_not_change_release_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import shutil
            shutil.copytree(ROOT / "images", root / "images")
            defs = definitions(root)
            before = {line: fingerprint(d, root) for line, d in defs.items()}
            path = root / "images/tools.json"
            tools = json.loads(path.read_text())
            tools["uv"]["digest"] = "sha256:" + "f" * 64
            path.write_text(json.dumps(tools))
            after = {line: fingerprint(d, root) for line, d in defs.items()}
            self.assertNotEqual(before["python-dev/3.14-trixie"], after["python-dev/3.14-trixie"])
            for line in ("php-dev/8.4-trixie", "php-browser/8.4-trixie", "rust-dev/1.99-trixie"):
                self.assertEqual(before[line], after[line])

    def test_shared_php_inputs_leave_other_images_and_their_caches_unchanged(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "images", root / "images")
            defs = definitions(root)
            before = {line: fingerprint(d, root) for line, d in defs.items()}
            for name in ("php-tests.py", "install-infection.sh"):
                path = root / "images/shared" / name
                path.write_text(path.read_text() + "\n# PHP-only update\n")
            changed = {line for line, d in defs.items() if fingerprint(d, root) != before[line]}
            self.assertEqual(changed, {"php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"})
            self.assertEqual(affected(["images/shared/php-tests.py"], definitions()), sorted(changed))

    def test_tool_refresh_selects_only_changed_pins_consumers(self):
        current = json.loads((ROOT / "images/tools.json").read_text())
        previous = copy.deepcopy(current)
        self.assertEqual(affected(["images/tools.json"], definitions(), previous), [])
        previous["uv"]["digest"] = "sha256:" + "0" * 64
        self.assertEqual(affected(["images/tools.json"], definitions(), previous), ["python-dev/3.14-trixie"])
        previous = copy.deepcopy(current)
        previous["infection"]["sha256"] = "0" * 64
        self.assertEqual(affected(["images/tools.json"], definitions(), previous), ["php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])

    def test_accepted_unchanged_artifact_reuses_its_digest_and_rejects_stale_input(self):
        import build
        d = definitions()["php-dev/8.4-trixie"]
        accepted = record(d["line_id"], d["revision"])
        accepted["input_fingerprint"] = fingerprint(d)
        with patch.object(build, "records", return_value=[accepted]):
            self.assertEqual(build.reusable_artifact(d["line_id"]), accepted["publication"]["repository"] + "@" + accepted["publication"]["digest"])
            accepted["input_fingerprint"] = "0" * 64
            self.assertIsNone(build.reusable_artifact(d["line_id"]))

    def test_toolkit_selection_requires_prepared_dependencies_and_verified_release(self):
        requirements = {"runtime_line": "8.5", "capabilities": ["ux-toolkit-validation", "symfony-toolkit-baseline"]}
        self.assertEqual(select(catalog([record("php-dev/8.5-trixie")]), requirements)["status"], "no_matching_image")
        toolkit = record("php-toolkit/8.5-trixie")
        self.assertEqual(select(catalog([toolkit]), requirements)["image"]["line_id"], "php-toolkit/8.5-trixie")
        self.assertEqual(select(catalog([]), requirements)["status"], "no_matching_image")
        toolkit["platforms"][0]["inventory"]["prepared_projects"]["validator"]["packages"]["symfony/ux-toolkit"] = "v3.4.0"
        with self.assertRaises(AssertionError):
            validate_record(toolkit)

    def test_toolkit_inputs_select_only_php_dev_build_trees(self):
        expected = ["php-dev/8.4-trixie", "php-dev/8.5-trixie"]
        for path in ("images/php-toolkit/Dockerfile", "examples/php-toolkit/validator/composer.lock",
                     "examples/php-toolkit/symfony-7.4/config/services.yaml", "tests/fixtures/php-toolkit/run.sh"):
            with self.subTest(path=path):
                self.assertEqual(affected([path], definitions()), expected)

    def test_toolkit_locked_manifests_and_baseline_source_are_release_inputs(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "images", root / "images")
            shutil.copytree(ROOT / "examples/php-toolkit", root / "examples/php-toolkit")
            defs = definitions(root)
            for relative in ("validator/composer.lock", "symfony-7.4/composer.json", "symfony-7.4/config/services.yaml"):
                before = {line: fingerprint(d, root) for line, d in defs.items()}
                path = root / "examples/php-toolkit" / relative
                path.write_bytes(path.read_bytes() + b"\n")
                changed = [line for line, d in defs.items() if fingerprint(d, root) != before[line]]
                self.assertEqual(changed, ["php-toolkit/8.4-trixie", "php-toolkit/8.5-trixie"])

    def test_tailwind_checksum_changes_only_the_project_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import shutil
            shutil.copytree(ROOT / "images", root / "images")
            defs = definitions(root)
            before = {line: fingerprint(d, root) for line, d in defs.items()}
            path = root / "images/tools.json"
            tools = json.loads(path.read_text())
            tools["tailwind"]["sha256"] = "f" * 64
            path.write_text(json.dumps(tools))
            changed = [line for line, d in defs.items() if fingerprint(d, root) != before[line]]
            self.assertEqual(changed, ["uxor-dev/8.4-trixie", "uxor-dev/8.5-trixie"])

    def test_release_matrix_preserves_incomplete_peers_and_changed_input_guards(self):
        defs = definitions()
        accepted = []
        import hashlib
        for line, d in sorted(defs.items(), key=lambda item: bool(item[1]["base"].get("parent"))):
            r = record(line, d["revision"])
            fp = fingerprint(d)
            if d["base"].get("parent"):
                parent = next(p for p in accepted if p["line_id"] == d["base"]["parent"])
                ref = parent["publication"]["repository"] + "@" + parent["publication"]["digest"]
                fp = hashlib.sha256((fp + ref).encode()).hexdigest()
            r["input_fingerprint"] = fp
            accepted.append(r)
        self.assertEqual(pending_releases(defs, []), ["harness-live/trixie", "php-dev/8.4-trixie", "php-dev/8.5-trixie", "php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie", "playwright-browser/1.58-trixie", "python-dev/3.14-trixie", "rust-dev/1.99-trixie"])
        self.assertEqual(pending_releases(defs, accepted), [])
        missing = [r for r in accepted if r["line_id"] != "php-browser/8.4-trixie"]
        self.assertEqual(pending_releases(defs, missing), ["php-dev/8.4-trixie"])
        changed = copy.deepcopy(accepted)
        next(r for r in changed if r["line_id"] == "rust-dev/1.99-trixie")["input_fingerprint"] = "0" * 64
        self.assertEqual(pending_releases(defs, changed), ["rust-dev/1.99-trixie"])

    def test_frankenphp_and_project_profile_selection_and_scope(self):
        defs = definitions()
        req = {"runtime_line": "8.5", "capabilities": ["frankenphp", "worker-server"], "extensions": ["intl", "apcu"]}
        cat = catalog([record("php-frankenphp/8.5-trixie"), record("uxor-dev/8.5-trixie", digest="e")])
        self.assertEqual(select(cat, req)["image"]["line_id"], "php-frankenphp/8.5-trixie")
        req["capabilities"].append("node")
        self.assertEqual(select(cat, req)["image"]["line_id"], "uxor-dev/8.5-trixie")
        self.assertEqual(select(catalog([]), req)["status"], "no_matching_image")
        self.assertEqual(affected(["examples/uxor/run.sh"], defs), ["php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        self.assertEqual(affected(["images/uxor-dev/Dockerfile"], defs), ["php-frankenphp/8.4-trixie", "php-frankenphp/8.5-trixie"])
        from library import children
        self.assertEqual(children("php-frankenphp/8.5-trixie", defs), ["uxor-dev/8.5-trixie"])

    def test_project_requirements_select_cached_profiles_and_reject_the_old_image(self):
        older = record("uxor-dev/8.5-trixie", "1.0.0")
        older["definition"]["capabilities"].remove("tailwind-cli")
        older["definition"]["tools"].remove("tailwindcss")
        del older["platforms"][0]["inventory"]["tools"]["tailwindcss"]
        for runtime, fixture, revision in (("8.5", "uxor.json", "1.1.0"),
                                           ("8.4", "uxor-8.4.json", "1.0.0")):
            with self.subTest(runtime=runtime):
                req = json.loads((ROOT / "tests/requirements" / fixture).read_text())
                current = record("uxor-dev/" + runtime + "-trixie", revision, "e")
                selected = select(catalog([older, current]), req)["image"]
                self.assertEqual(selected["line_id"], current["line_id"])
                self.assertEqual(selected["version"], revision)
                self.assertEqual(select(catalog([older]), req)["status"], "no_matching_image")

    def test_generated_output_is_deterministic(self):
        self.assertEqual(generated(), generated())

    def test_node_input_and_inventory_are_scoped_to_the_project_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import shutil
            shutil.copytree(ROOT / "images", root / "images")
            defs = definitions(root)
            before = {line: fingerprint(d, root) for line, d in defs.items()}
            path = root / "images/tools.json"
            tools = json.loads(path.read_text())
            tools["node"]["digest"] = "sha256:" + "f" * 64
            path.write_text(json.dumps(tools))
            changed = [line for line, d in defs.items() if fingerprint(d, root) != before[line]]
            self.assertEqual(changed, ["harness-live/trixie", "php-serena/8.5-trixie", "uxor-dev/8.4-trixie", "uxor-dev/8.5-trixie"])
        r = record("uxor-dev/8.5-trixie")
        r["platforms"][0]["inventory"]["tools"]["node"] = "v24.1.0"
        with self.assertRaisesRegex(AssertionError, "Node line must match CI"):
            validate_record(r)


class PromotionTests(unittest.TestCase):
    def test_project_publication_uses_the_exact_verified_parent(self):
        parent = record("php-frankenphp/8.5-trixie", digest="f")
        child = record("uxor-dev/8.5-trixie", digest="e")
        with tempfile.TemporaryDirectory() as tmp, patch.object(release, "ROOT", Path(tmp)), \
                patch.object(release, "publish", side_effect=[parent, child]) as publish:
            release.publish_tree("php-frankenphp/8.5-trixie", "b" * 40)
            self.assertEqual(publish.call_args_list[1].args[3], "ghcr.io/xormania/php-frankenphp@sha256:" + "f" * 64)
            self.assertEqual(json.loads((Path(tmp) / "out/uxor-dev-8.5-trixie/record.json").read_text()), child)

    def test_exact_tag_is_idempotent_but_never_reassigned(self):
        exact_guard(None, "a"); exact_guard("a", "a")
        with self.assertRaises(RuntimeError): exact_guard("a", "b")

    def test_old_job_cannot_advance_alias_over_newer_record(self):
        old = record("php-dev/8.4-trixie")
        new = record("php-dev/8.4-trixie", "1.1.0", "e")
        self.assertFalse(alias_eligible(old, [old, new]))
        self.assertTrue(alias_eligible(new, [old, new]))
        self.assertFalse(alias_eligible(new, [old]))  # unpublished candidate

    def test_last_withdrawn_or_deprecated_release_blocks_existing_alias(self):
        for lifecycle in ("withdrawn", "deprecated"):
            with self.subTest(lifecycle=lifecycle):
                r = record("php-dev/8.4-trixie")
                r["lifecycle"] = lifecycle
                with patch.object(release, "records", return_value=[r]), \
                        patch.object(release, "resolve", return_value={"digest": r["publication"]["digest"]}), \
                        patch.object(release, "run") as run:
                    with self.assertRaisesRegex(RuntimeError, "No available replacement.*php-dev:8.4-trixie-v1"):
                        release.aliases()
                    self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))

    def test_retired_alias_that_is_already_absent_needs_no_promotion(self):
        r = record("php-dev/8.4-trixie")
        r["lifecycle"] = "withdrawn"
        with patch.object(release, "records", return_value=[r]), \
                patch.object(release, "resolve", return_value=None), \
                patch.object(release, "run") as run:
            release.aliases()
            self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))

    def test_withdrawal_rolls_alias_back_to_available_revision(self):
        old = record("php-dev/8.4-trixie")
        withdrawn = record("php-dev/8.4-trixie", "1.0.1", "e")
        withdrawn["lifecycle"] = "withdrawn"
        with patch.object(release, "records", return_value=[old, withdrawn]), \
                patch.object(release, "resolve", side_effect=[
                    {"digest": old["publication"]["digest"]},
                    {"digest": withdrawn["publication"]["digest"]},
                    {"digest": old["publication"]["digest"]}]), \
                patch.object(release, "run") as run:
            release.aliases()
            promotions = [call.args for call in run.call_args_list if call.args[0] == "docker"]
            self.assertEqual(len(promotions), 1)
            self.assertEqual(promotions[0][-1], old["publication"]["repository"] + "@" + old["publication"]["digest"])

    def test_missing_later_exact_tag_prevents_every_alias_write(self):
        first = record("php-dev/8.4-trixie")
        second = record("php-dev/8.5-trixie", digest="e")
        with patch.object(release, "records", return_value=[first, second]), \
                patch.object(release, "resolve", side_effect=[
                    {"digest": first["publication"]["digest"]}, None, None]), \
                patch.object(release, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "unavailable: ghcr.io/xormania/php-dev:8.5-trixie-v1.0.0"):
                release.aliases()
            self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))

    def test_preflight_failures_write_complete_job_summary_without_alias_writes(self):
        for failure in ("blocked", "retired lookup", "missing exact", "changed exact", "exact lookup", "alias lookup"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                first = record("php-dev/8.4-trixie")
                second = record("php-dev/8.5-trixie", digest="e")
                third = record("python-dev/3.14-trixie", digest="f")
                retired = failure in ("blocked", "retired lookup")
                if retired:
                    second["lifecycle"] = "withdrawn"
                aliases = [f"{r['publication']['repository']}:{r['definition']['line']}-v1"
                           for r in (first, second, third)]
                second_exact = second["publication"]["repository"] + ":" + second["publication"]["exact_tag"]

                def resolve(reference, authenticated=False):
                    if reference == second_exact:
                        if failure == "missing exact":
                            return None
                        if failure == "changed exact":
                            return {"digest": "sha256:" + "0" * 64}
                        if failure == "exact lookup":
                            raise RuntimeError("Registry lookup failed | retry\nlater")
                        return {"digest": second["publication"]["digest"]}
                    if reference == aliases[1]:
                        if failure in ("retired lookup", "alias lookup"):
                            raise RuntimeError("Registry lookup failed | retry\nlater")
                        return {"digest": second["publication"]["digest"]}
                    return {"digest": first["publication"]["digest"]}

                summary = Path(tmp) / "summary.md"
                expected_error = "replacement" if failure == "blocked" else "lookup" if "lookup" in failure else "unavailable"
                with patch.object(release, "records", return_value=[first, second, third]), \
                        patch.object(release, "resolve", side_effect=resolve), \
                        patch.object(release, "run") as run, \
                        patch.dict(release.os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                    with self.assertRaisesRegex(RuntimeError, expected_error):
                        release.aliases()
                    self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))
                text = summary.read_text()
                self.assertIn(f"| `{aliases[0]}` | {'pending' if retired else 'unchanged'} |", text)
                self.assertIn(f"| `{aliases[1]}` | failed |", text)
                self.assertIn(f"| `{aliases[2]}` | pending |", text)
                self.assertIn(expected_error, text)
                if "lookup" in failure:
                    self.assertIn("Registry lookup failed &#124; retry later", text)

    def test_matching_alias_is_reported_without_a_registry_write(self):
        item = record("php-dev/8.4-trixie")
        with patch.object(release, "records", return_value=[item]), \
                patch.object(release, "resolve", return_value={"digest": item["publication"]["digest"]}), \
                patch.object(release, "run") as run, patch.object(release, "alias_report") as report:
            release.aliases()
            self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))
            self.assertEqual(report.call_args.args[0][0]["status"], "unchanged")

    def test_partial_write_failure_reports_results_and_retry_skips_completed_alias(self):
        first = record("php-dev/8.4-trixie")
        second = record("php-dev/8.5-trixie", digest="e")
        remote = {r["publication"]["repository"] + ":" + r["publication"]["exact_tag"]:
                  r["publication"]["digest"] for r in (first, second)}
        attempts = []
        fail = True

        def resolve(reference, authenticated=False):
            return {"digest": remote[reference]} if reference in remote else None

        def run(*args):
            if args[0] != "docker":
                return
            attempts.append(args)
            if fail and len(attempts) == 2:
                raise RuntimeError("Registry write interrupted")
            remote[args[-2]] = args[-1].split("@", 1)[1]

        with patch.object(release, "records", return_value=[first, second]), \
                patch.object(release, "resolve", side_effect=resolve), \
                patch.object(release, "run", side_effect=run), patch.object(release, "alias_report") as report:
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                release.aliases()
            self.assertEqual([item["status"] for item in report.call_args.args[0]], ["updated", "failed"])
            fail = False
            release.aliases()
            self.assertEqual([item["status"] for item in report.call_args.args[0]], ["unchanged", "updated"])
            self.assertEqual(len(attempts), 3)

    def test_blocked_major_is_detected_before_other_aliases_change(self):
        available = record("php-dev/8.4-trixie")
        withdrawn = record("php-dev/8.5-trixie")
        withdrawn["lifecycle"] = "withdrawn"
        with patch.object(release, "records", return_value=[available, withdrawn]), \
                patch.object(release, "resolve", return_value={"digest": withdrawn["publication"]["digest"]}), \
                patch.object(release, "run") as run:
            with self.assertRaises(RuntimeError):
                release.aliases()
            self.assertFalse(any(call.args[0] == "docker" for call in run.call_args_list))

    def test_retry_resumes_durable_artifact_without_rebuilding(self):
        r = record("php-dev/8.4-trixie")
        r["input_fingerprint"] = fingerprint(definitions()[r["line_id"]])
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(release, "records", return_value=[]), \
                patch.object(release, "release_asset", return_value=r), \
                patch.object(release, "resolve", return_value={"digest": r["publication"]["digest"]}), \
                patch.object(release, "build") as build, \
                patch.object(release, "promote_exact") as promote, \
                patch.object(release, "finalize_release") as finalize:
            self.assertEqual(release.publish(r["line_id"], "f" * 40, Path(tmp)), r)
            build.assert_not_called()
            promote.assert_called_once_with(r)
            finalize.assert_called_once_with(r)

    def test_changed_inputs_cannot_resume_old_revision(self):
        r = record("php-dev/8.4-trixie")
        r["input_fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(release, "records", return_value=[]), \
                patch.object(release, "release_asset", return_value=r), \
                patch.object(release, "build") as build:
            with self.assertRaisesRegex(RuntimeError, "different inputs"):
                release.publish(r["line_id"], "f" * 40, Path(tmp))
            build.assert_not_called()

    def test_ambiguous_existing_exact_tag_never_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(release, "records", return_value=[]), \
                patch.object(release, "release_asset", return_value=None), \
                patch.object(release, "resolve", return_value={"digest": "sha256:" + "a" * 64}), \
                patch.object(release, "build") as build:
            with self.assertRaisesRegex(RuntimeError, "without a durable record"):
                release.publish("php-dev/8.4-trixie", "f" * 40, Path(tmp))
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
