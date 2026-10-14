"""Retention proposals require exact lifecycle and reference evidence."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retention


PACKAGE = "ghcr.io/xormania/php-dev"
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def ref(letter, package=PACKAGE):
    return package + "@sha256:" + letter * 64


def item(letter, kind="image", **extra):
    return {"identity": ref(letter), "kind": kind, "created_at": "2026-10-01T00:00:00Z",
            "tags": [], "version_ids": [int(letter, 16) + 1], "dependencies": [],
            "references_complete": True, **extra}


def snapshot(*items, **extra):
    return {"schema_version": 1, "observed_at": "2026-11-20T00:00:00Z",
            "scope": {"repository": "xormania/xorder", "packages": [PACKAGE]},
            "versions_complete": True, "references_complete": True,
            "publications_complete": True, "items": list(items), "publications": [], **extra}


def group(letter, *, support="2026-11-01T00:00:00Z", removal="2026-11-15T00:00:00Z", name="weekly-1"):
    return {"id": name, "state": "accepted", "accepted_at": "2026-10-01T00:00:00Z",
            "support_ends_at": support, "warning_starts_at": "2026-10-25T00:00:00Z",
            "removal_eligible_at": removal, "replacement": "weekly-2", "resources": [
                {"line_id": "php-dev/8.5-trixie", "version": "1.0.0", "identity": ref(letter),
                 "platforms": [{"platform": "linux/amd64", "digest": "sha256:" + letter * 64}]}]}


def policy(*groups, legacy_end=None):
    return {"schema_version": 1, "revision": 1,
            "defaults": {"max_policy_age_hours": 24, "removal_grace_days": 14},
            "legacy": {"enforce_after": legacy_end}, "groups": list(groups)}


def record(letter, parent="docker.io/library/php@sha256:" + "9" * 64):
    return {"line_id": "php-dev/8.5-trixie", "version": "1.0.0", "lifecycle": "available",
            "publication": {"repository": PACKAGE, "digest": "sha256:" + letter * 64},
            "platforms": [{"platform": "linux/amd64", "digest": "sha256:" + letter * 64}],
            "resolved_base": parent}


class RetentionTests(unittest.TestCase):
    def plan(self, inventory, support=None, releases=(), **kwargs):
        return retention.plan(inventory, support or policy(), releases, NOW, **kwargs)

    def identities(self, result, state):
        return {row["identity"] for row in result["sets"][state]}

    def test_multiple_tags_are_one_digest_and_pin_does_not_extend_expiry(self):
        inventory = snapshot(item("a", tags=["v1", "candidate-old", "v1.0.0"]),
                             pins=[{"consumer": "xormania/uxor", "identity": ref("a")}])
        result = self.plan(inventory, policy(group("a")), [record("a")])
        self.assertEqual(result["counts"]["distinct_package_digests"], 1)
        self.assertEqual(result["counts"]["tags"], 3)
        self.assertEqual(self.identities(result, "removal"), {ref("a")})
        self.assertEqual(result["migration_notices"][0]["state"], "expired")
        self.assertEqual(result["mode"], "dry-run")

    def test_same_digest_in_current_group_protects_parent_and_evidence(self):
        current = group("a", name="weekly-2", support="2026-12-01T00:00:00Z", removal="2026-12-15T00:00:00Z")
        inventory = snapshot(item("a", dependencies=[ref("b")]), item("b"),
                             item("c", "evidence", owners=[ref("a")], dependencies=[ref("a")]))
        result = self.plan(inventory, policy(group("a"), group("b"), current))
        self.assertEqual(self.identities(result, "keep"), {ref("a"), ref("b"), ref("c")})
        self.assertFalse(result["sets"]["removal"])

    def test_supported_release_parent_is_protected_from_ledger_even_if_snapshot_omits_edge(self):
        support = policy(group("a", support="2026-12-01T00:00:00Z", removal="2026-12-15T00:00:00Z"), group("b"))
        result = self.plan(snapshot(item("a"), item("b")), support, [record("a", ref("b"))])
        self.assertEqual(self.identities(result, "keep"), {ref("a"), ref("b")})

    def test_supported_child_outside_scoped_packages_still_protects_scoped_parent(self):
        package = "ghcr.io/xormania/php-browser"
        child = record("a", ref("b"))
        child["publication"]["repository"] = package
        current = group("a", support="2026-12-01T00:00:00Z", removal="2026-12-15T00:00:00Z")
        current["resources"][0]["identity"] = ref("a", package)
        result = self.plan(snapshot(item("b")), policy(current, group("b")), [child])
        self.assertEqual(self.identities(result, "keep"), {ref("b")})

    def test_supported_historical_group_parent_is_protected_without_current_record(self):
        current = group("a", support="2026-12-01T00:00:00Z", removal="2026-12-15T00:00:00Z")
        current["resources"][0]["parent"] = ref("b")
        result = self.plan(snapshot(item("a"), item("b")), policy(current, group("b")))
        self.assertEqual(self.identities(result, "keep"), {ref("a"), ref("b")})

    def test_recent_abandoned_attempt_keeps_shared_expired_release_for_recovery(self):
        attempts = [{"id": "retry", "state": "abandoned", "identities": [ref("a")], "ended_at": "2026-11-18T00:00:00Z"}]
        result = self.plan(snapshot(item("a"), publications=attempts), policy(group("a")))
        self.assertEqual(self.identities(result, "expire"), {ref("a")})
        self.assertEqual(result["sets"]["expire"][0]["removal_eligible_at"], "2026-11-25T00:00:00Z")

    def test_expired_group_observes_grace_and_transitive_dependencies(self):
        support = policy(group("a", removal="2026-11-22T00:00:00Z"), group("b"), group("c"))
        result = self.plan(snapshot(item("a", dependencies=[ref("b")]), item("b", dependencies=[ref("c")]), item("c")), support)
        self.assertEqual(self.identities(result, "expire"), {ref("a")})
        self.assertEqual(self.identities(result, "keep"), {ref("b"), ref("c")})

    def test_retired_root_and_owned_signature_sbom_can_retire_together(self):
        result = self.plan(snapshot(item("a"), item("b", "evidence", owners=[ref("a")], dependencies=[ref("a")])), policy(group("a")))
        self.assertEqual(self.identities(result, "removal"), {ref("a"), ref("b")})

    def test_all_groups_must_pass_their_grace_before_shared_digest_removal(self):
        support = policy(group("a"), group("a", name="weekly-2", removal="2026-11-22T00:00:00Z"))
        result = self.plan(snapshot(item("a")), support)
        self.assertEqual(self.identities(result, "expire"), {ref("a")})

    def test_legacy_stays_until_announced_migration_and_grace(self):
        inventory = snapshot(item("a"))
        self.assertEqual(self.identities(self.plan(inventory, releases=[record("a")]), "keep"), {ref("a")})
        result = self.plan(inventory, policy(legacy_end="2026-11-01T00:00:00Z"), [record("a")])
        self.assertEqual(self.identities(result, "removal"), {ref("a")})

    def test_active_attempt_wins_expired_group_and_abandoned_waits_seven_days(self):
        attempts = [{"id": "attempt-active", "state": "active", "identities": [ref("a")]},
                    {"id": "attempt-recent", "state": "abandoned", "identities": [ref("b")], "ended_at": "2026-11-18T00:00:00Z"},
                    {"id": "attempt-old", "state": "abandoned", "identities": [ref("c")], "ended_at": "2026-11-13T00:00:00Z"}]
        result = self.plan(snapshot(item("a", "candidate"), item("b", "candidate"), item("c", "candidate"), publications=attempts), policy(group("a")))
        self.assertEqual(self.identities(result, "keep"), {ref("a")})
        self.assertEqual(self.identities(result, "expire"), {ref("b")})
        self.assertEqual(self.identities(result, "removal"), {ref("c")})

    def test_closed_and_inactive_branch_caches_have_bounded_windows(self):
        inventory = snapshot(item("a", "cache", last_used_at="2026-11-19T00:00:00Z", branch={"state": "closed", "closed_at": "2026-11-17T00:00:00Z"}),
                             item("b", "cache", last_used_at="2026-11-01T00:00:00Z", branch={"state": "open"}),
                             item("c", "cache", last_used_at="2026-11-19T00:00:00Z", branch={"state": "open"}),
                             item("d", "cache", last_used_at="2026-10-01T00:00:00Z", branch={"state": "unknown"}))
        result = self.plan(inventory)
        self.assertEqual(self.identities(result, "removal"), {ref("a"), ref("b")})
        self.assertEqual(self.identities(result, "keep"), {ref("c"), ref("d")})

    def test_incomplete_or_stale_inventory_never_proves_removal(self):
        variations = [{"versions_complete": False}, {"references_complete": False}, {"publications_complete": False},
                      {"observed_at": "2026-11-18T00:00:00Z"}]
        for variation in variations:
            with self.subTest(variation=variation):
                result = self.plan(snapshot(item("a"), **variation), policy(group("a")))
                self.assertFalse(result["sets"]["removal"])
                self.assertTrue(result["unknown_facts"])
        inventory = snapshot(item("a"), item("b", references_complete=False))
        result = self.plan(inventory, policy(group("a")))
        self.assertFalse(result["sets"]["removal"])

    def test_missing_manifest_or_parent_produces_explicit_unknown_fact(self):
        result = self.plan(snapshot(item("a", dependencies=[ref("b")])), policy(group("a")))
        self.assertFalse(result["sets"]["removal"])
        self.assertIn("missing", result["unknown_facts"][0])

    def test_unowned_objects_and_untracked_candidate_remain_unknown(self):
        result = self.plan(snapshot(item("a", "unknown"), item("b", "candidate"), item("c", "evidence")))
        self.assertEqual(self.identities(result, "keep"), {ref("a"), ref("b"), ref("c")})
        self.assertTrue(all("unknown" in row["reasons"][0] for row in result["sets"]["keep"]))

    def test_exclusive_blob_bytes_only_and_total_reclamation_unknown(self):
        blobs = [{"digest": "sha256:" + "1" * 64, "size_bytes": 100, "references_complete": True, "references": [ref("a")]},
                 {"digest": "sha256:" + "2" * 64, "size_bytes": 200, "references_complete": True, "references": [ref("a"), ref("b")]},
                 {"digest": "sha256:" + "3" * 64, "size_bytes": 300, "references_complete": False, "references": [ref("a")]}]
        result = self.plan(snapshot(item("a"), item("b"), blobs=blobs), policy(group("a")))
        self.assertEqual(result["reclaim"]["known_exclusive_blob_bytes"], 100)
        self.assertIsNone(result["reclaim"]["total_reclaimable_bytes"])
        self.assertEqual(len(result["reclaim"]["unknown_blob_digests"]), 1)

    def test_false_scope_duplicate_digests_tags_versions_and_future_facts_fail(self):
        bad = [snapshot(item("a"), item("a")), snapshot(item("a", tags=["v1"]), item("b", tags=["v1"])),
               snapshot(item("a", version_ids=[1]), item("b", version_ids=[1])),
               snapshot(item("a", created_at="2026-12-01T00:00:00Z")),
               snapshot(item("a"), observed_at="2026-12-01T00:00:00Z"),
               snapshot(item("a"), scope={"repository": "elsewhere/repo", "packages": [PACKAGE]})]
        for inventory in bad:
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                self.plan(inventory)

    def test_expiry_boundary_and_readable_output(self):
        result = self.plan(snapshot(item("a")), policy(group("a", removal="2026-11-20T00:00:00Z")))
        self.assertEqual(self.identities(result, "removal"), {ref("a")})
        text = retention.readable(result)
        self.assertIn("dry-run", text)
        self.assertIn("Removal (1 digests)", text)
        self.assertIn(ref("a"), text)

    def test_planning_does_not_change_input_facts(self):
        inventory, support = snapshot(item("a")), policy(group("a"))
        originals = copy.deepcopy((inventory, support))
        self.plan(inventory, support)
        self.assertEqual((inventory, support), originals)

    def test_checked_in_ledger_projection_cannot_prove_registry_removal(self):
        import library
        root = Path(__file__).resolve().parents[1]
        inventory = json.loads((root / "tests/fixtures/retention-example.json").read_text())
        records = library.records(root)
        accepted = {ref for record in records for ref in retention.release_references(record)}
        self.assertTrue(all(item["identity"] in accepted for item in inventory["items"]))
        self.assertTrue(all(not item["version_ids"] and not item["references_complete"] for item in inventory["items"]))
        result = retention.plan(inventory, policy(legacy_end="2026-11-11T08:00:00Z"), records,
                                retention.timestamp("2026-11-26T08:00:00Z"))
        self.assertFalse(result["sets"]["removal"])
        self.assertEqual(result["reclaim"]["known_exclusive_blob_bytes"], 0)
        self.assertTrue(any("stale" in fact for fact in result["unknown_facts"]))


if __name__ == "__main__":
    unittest.main()
