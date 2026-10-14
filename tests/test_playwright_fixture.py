"""Parity inputs stay fixed as catalogs grow and fail closed on invalid pins."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from library import ROOT
from playwright_fixture import application_image, inputs


class PlaywrightFixtureTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"resources": [{"id": "image/uxor-dev/8.5-trixie", "version": "1.0.0",
                                      "identity": "ghcr.io/xormania/uxor-dev@sha256:" + "c" * 64,
                                      "lifecycle": "available", "verification": {"status": "passed"},
                                      "targets": ["linux/amd64"]}]}
        self.image = application_image(self.catalog)
        self.fixture = {"repository": "https://github.com/xormania/uxor.git",
                        "commit": "a" * 40, "playwright_version": "1.58.2",
                        "application_image": self.image}

    def test_new_accepted_release_does_not_change_existing_parity_inputs(self):
        before = inputs(self.fixture, self.catalog)
        latest = copy.deepcopy(next(item for item in self.catalog["resources"] if item["identity"] == self.image))
        latest.update(version="99.0.0", identity="ghcr.io/xormania/uxor-dev@sha256:" + "a" * 64)
        self.catalog["resources"].append(latest)
        self.assertEqual(inputs(self.fixture, self.catalog), before)
        self.assertEqual(application_image(self.catalog), latest["identity"])

    def test_missing_mutable_or_unaccepted_pin_fails_instead_of_using_latest(self):
        for identity in (None, "", "ghcr.io/xormania/uxor-dev:8.5-trixie-v1",
                         "ghcr.io/xormania/uxor-dev@sha256:" + "b" * 64):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                inputs(dict(self.fixture, application_image=identity), self.catalog)
        self.catalog["resources"] = [item for item in self.catalog["resources"] if item["identity"] != self.image]
        with self.assertRaisesRegex(ValueError, "not accepted"):
            inputs(self.fixture, self.catalog)

    def test_intended_revision_resolves_only_its_accepted_digest(self):
        fixture = {key: value for key, value in self.fixture.items() if key != "application_image"}
        fixture["application_resource"] = {"id": "image/uxor-dev/8.5-trixie", "version": "1.0.0"}
        newer = copy.deepcopy(self.catalog["resources"][0])
        newer.update(version="1.1.0", identity="ghcr.io/xormania/uxor-dev@sha256:" + "d" * 64)
        self.catalog["resources"].append(newer)
        self.assertEqual(inputs(fixture, self.catalog)[3], self.image)
        self.catalog["resources"] = [newer]
        with self.assertRaisesRegex(ValueError, "not accepted"):
            inputs(fixture, self.catalog)
        local = "sha256:" + "e" * 64
        self.assertEqual(inputs(fixture, self.catalog, local)[3], local)
        with self.assertRaisesRegex(ValueError, "exact Docker image ID"):
            inputs(fixture, self.catalog, "unbound-tag:latest")
        with self.assertRaisesRegex(ValueError, "explicit application resource intent"):
            inputs(self.fixture, self.catalog, local)

    def test_actual_migration_intent_does_not_claim_public_availability(self):
        fixture = json.loads((ROOT / "tests/fixtures/playwright/consumers/1.58-trixie.json").read_text())
        self.assertEqual(fixture["application_resource"], {"id": "image/uxor-dev/8.5-trixie", "version": "1.0.0"})
        with self.assertRaisesRegex(ValueError, "not accepted"):
            inputs(fixture, {"resources": []})
