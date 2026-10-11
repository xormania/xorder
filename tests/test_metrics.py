"""Release measurement provenance, publication boundaries, and generated views."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

import jsonschema
from test_library import record
import build
import release
from library import ROOT, definitions, generated, read, records, validate_record


EVIDENCE = "https://example.test/ci"
DATE = "2026-01-01T00:00:00Z"
FACTS = {"image_size_bytes": 629145600, "size_method": "docker-image-inspect-size", "image_store": "overlay2/classic"}


def metrics(size=629145600, evidence=EVIDENCE):
    return {**FACTS, "image_size_bytes": size, "measured_at": DATE, "evidence": evidence,
            "verification_seconds": 2.5, "build_seconds": 12.34, "cache_source": "restored"}


def measured_record():
    old = record("php-dev/8.4-trixie")
    new = record("php-dev/8.4-trixie", "1.0.1", "f")
    new["platforms"][0]["metrics"] = metrics()
    new["platforms"][0]["metrics"]["baseline"] = {
        **FACTS, "image_size_bytes": 1073741824, "measured_at": DATE, "evidence": EVIDENCE,
        "version": "1.0.0", "digest_reference": old["publication"]["repository"] + "@" + old["publication"]["digest"]}
    return old, new


class MeasurementTests(unittest.TestCase):
    def test_image_measurements_identify_classic_and_containerd_stores(self):
        for info, expected in [({"Driver": "overlay2", "DriverStatus": [["Backing Filesystem", "extfs"]]}, "overlay2/classic"),
                               ({"Driver": "overlayfs", "DriverStatus": [["driver-type", "io.containerd.snapshotter.v1"]]}, "overlayfs/io.containerd.snapshotter.v1")]:
            with self.subTest(expected=expected), patch.object(build.subprocess, "check_output", side_effect=[json.dumps(info), json.dumps([{"Size": 629145600}])]):
                measured = build.image_measurements("test@sha256:" + "a" * 64)
                self.assertEqual(measured["image_store"], expected)
                self.assertEqual(measured["image_size_bytes"], 629145600)

    def test_schema_accepts_legacy_and_measured_records_and_rejects_bad_metrics(self):
        old, new = measured_record()
        schema = read(ROOT / "schemas/release-record.schema.json")
        for r in (old, new):
            jsonschema.validate(r, schema, format_checker=jsonschema.FormatChecker())
            validate_record(r)
        for field, value in [("image_size_bytes", -1), ("verification_seconds", -0.1), ("cache_source", "warm"), ("measured_at", "yesterday")]:
            with self.subTest(field=field):
                bad = copy.deepcopy(new)
                bad["platforms"][0]["metrics"][field] = value
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(bad, schema, format_checker=jsonschema.FormatChecker())
        for change in (lambda m: m.update(evidence="https://example.test/unrelated"),
                       lambda m: m.update(build_seconds=float("nan")),
                       lambda m: m.pop("cache_source"),
                       lambda m: m["baseline"].update(image_store="overlayfs/io.containerd.snapshotter.v1"),
                       lambda m: m["baseline"].update(version="1.0.1")):
            bad = copy.deepcopy(new)
            change(bad["platforms"][0]["metrics"])
            with self.assertRaises(AssertionError):
                validate_record(bad)

    def test_legacy_baseline_is_pulled_anonymously_and_measured_in_current_store(self):
        old = record("php-dev/8.4-trixie")
        baseline_facts = {**FACTS, "image_size_bytes": 1073741824}
        env = {"DOCKER_CONFIG": "/anonymous"}
        with patch.object(release, "image_measurements", side_effect=[FACTS, baseline_facts]), \
                patch.object(release, "run") as run, patch.object(release, "now", return_value=DATE):
            measured = release.release_measurements(old["line_id"], "1.0.1", "new-artifact", [old], EVIDENCE, DATE, 2.5, env)
        reference = old["publication"]["repository"] + "@" + old["publication"]["digest"]
        run.assert_called_once_with("docker", "pull", "--platform", "linux/amd64", reference, env=env)
        self.assertEqual(measured["baseline"]["image_size_bytes"], 1073741824)
        self.assertEqual(measured["baseline"]["evidence"], EVIDENCE)
        self.assertNotIn("build_seconds", measured)  # Resumed artifacts have no fictional build time.
        self.assertNotIn("metrics", old["platforms"][0])

    def test_compatible_baseline_reuses_verified_provenance_and_other_store_is_remeasured(self):
        old = record("php-dev/8.4-trixie")
        old["platforms"][0]["metrics"] = metrics(1073741824, "https://example.test/old-ci")
        old["verification"]["evidence"] = old["publication"]["evidence"] = "https://example.test/old-ci"
        validate_record(old)
        with patch.object(release, "image_measurements", return_value=FACTS) as measure, patch.object(release, "run") as run:
            current = release.release_measurements(old["line_id"], "1.0.1", "new-artifact", [old], EVIDENCE, DATE, 2.5, {})
        measure.assert_called_once_with("new-artifact")
        run.assert_not_called()
        self.assertEqual(current["baseline"]["evidence"], "https://example.test/old-ci")
        old["platforms"][0]["metrics"]["image_store"] = "overlayfs/io.containerd.snapshotter.v1"
        with patch.object(release, "image_measurements", side_effect=[FACTS, {**FACTS, "image_size_bytes": 1000000000}]), \
                patch.object(release, "run") as run, patch.object(release, "now", return_value=DATE):
            current = release.release_measurements(old["line_id"], "1.0.1", "new-artifact", [old], EVIDENCE, DATE, 2.5, {})
        self.assertEqual(run.call_count, 1)
        self.assertEqual(current["baseline"]["image_store"], "overlay2/classic")
        self.assertEqual(current["baseline"]["image_size_bytes"], 1000000000)

    def test_generated_views_use_verified_ledger_and_check_baseline_identity(self):
        old, new = measured_record()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "images", root / "images")
            shutil.copy(ROOT / "README.md", root / "README.md")
            paths = []
            for r in (old, new):
                path = root / "release-records" / r["line_id"] / (r["version"] + ".json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(r))
                paths.append(path)
            outputs = generated(root)
            self.assertIn("| 600.0 | 1,024.0 (v1.0.0) | -41.4% | 12.34 | 2.50 |", outputs[root / "docs/metrics.md"])
            for relative in ("docs/images/php-dev-8.4-trixie.md", "docs/releases/php-dev-8.4-trixie-v1.0.1.md"):
                self.assertIn("2 GiB free for a cold pull", outputs[root / relative])
                self.assertIn("629,145,600 bytes", outputs[root / relative])
                self.assertIn("overlay2/classic", outputs[root / relative])
                self.assertIn(EVIDENCE, outputs[root / relative])
            self.assertEqual(json.loads(outputs[root / "catalog.json"])["images"][1]["platforms"][0]["metrics"], new["platforms"][0]["metrics"])
            self.assertEqual(outputs, generated(root))
            paths[0].unlink()
            with self.assertRaisesRegex(AssertionError, "baseline is absent"):
                records(root)
            paths[0].write_text(json.dumps(old))
            new["platforms"][0]["metrics"]["baseline"]["digest_reference"] = old["publication"]["repository"] + "@sha256:" + "d" * 64
            paths[1].write_text(json.dumps(new))
            with self.assertRaises(AssertionError):
                records(root)

    def test_empty_or_legacy_ledger_has_no_invented_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "images", root / "images")
            shutil.copy(ROOT / "README.md", root / "README.md")
            self.assertIn("No verified release measurements yet", generated(root)[root / "docs/metrics.md"])
            old = record("php-dev/8.4-trixie")
            path = root / "release-records/php-dev/8.4-trixie/1.0.0.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(old))
            outputs = generated(root)
            self.assertIn("No verified release measurements yet", outputs[root / "docs/metrics.md"])
            self.assertNotIn("Release measurements", outputs[root / "docs/images/php-dev-8.4-trixie.md"])

    def test_publication_persists_verified_metrics_and_retry_preserves_them(self):
        line = "php-dev/8.4-trixie"
        old = record(line)
        d = definitions()[line]
        new = record(line, d["revision"], "f")
        digest = new["publication"]["digest"]
        resolved = {"digest": digest, "platforms": {"linux/amd64": digest}}

        def verify(_line, _image, destination):
            Path(destination).write_text(json.dumps(new["platforms"][0]["inventory"]))

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(release, "records", return_value=[old]), \
                patch.object(release, "release_asset", return_value=None), \
                patch.object(release, "resolve", side_effect=[None, None, resolved, resolved]), \
                patch.object(release, "build") as build_image, \
                patch.object(release, "cache_source", return_value="empty"), \
                patch.object(release, "verify", side_effect=verify) as verification, \
                patch.object(release, "image_measurements", side_effect=[FACTS, {**FACTS, "image_size_bytes": 1073741824}]), \
                patch.object(release.time, "monotonic", side_effect=[1, 11, 12, 14.5]), \
                patch.object(release, "run"), patch.object(release, "gh", return_value="[[]]"), \
                patch.object(release.subprocess, "check_output", return_value=""), \
                patch.object(release, "promote_exact"), patch.object(release, "finalize_release"), \
                patch.object(release, "stage_assurance", return_value={"receipt_url": "https://github.com/xormania/xorder/releases/download/" + quote(new["source_tag"], safe="") + "/assurance.json", "receipt_sha256": "a" * 64, "predicate_type": "https://github.com/xormania/xorder/assurance/v1"}), \
                patch("image_assurance.verify_record"), \
                patch.dict(release.os.environ, {"GITHUB_REPOSITORY": "xormania/docker-image-library", "GITHUB_RUN_ID": "42"}):
            published = release.publish(line, "f" * 40, Path(tmp))
            self.assertEqual(published, read(Path(tmp) / "record.json"))
            measured = published["platforms"][0]["metrics"]
            self.assertEqual(measured["build_seconds"], 10)
            self.assertEqual(measured["verification_seconds"], 2.5)
            self.assertEqual(measured["cache_source"], "empty")
            self.assertEqual(measured["image_size_bytes"], 629145600)
            self.assertEqual(measured["baseline"]["image_size_bytes"], 1073741824)
            self.assertEqual(measured["evidence"], "https://github.com/xormania/docker-image-library/actions/runs/42")
            self.assertEqual(verification.call_count, 2)
            build_image.assert_called_once()
            jsonschema.validate(published, read(ROOT / "schemas/release-record.schema.json"))
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(release, "records", return_value=[old]), \
                patch.object(release, "release_asset", return_value=published), \
                patch.object(release, "resolve", return_value=resolved), \
                patch.object(release, "build") as build_image, \
                patch.object(release, "image_measurements") as measure, \
                patch.object(release, "promote_exact"), patch.object(release, "finalize_release"), \
                patch("image_assurance.verify_record"):
            self.assertEqual(release.publish(line, "f" * 40, Path(tmp)), published)
            build_image.assert_not_called()
            measure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
