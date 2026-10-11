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
        self.catalog = json.loads((ROOT / "catalog-v2.json").read_text())
        self.image = application_image(self.catalog)
        self.fixture = {"repository": "https://github.com/xormania/uxor.git",
                        "commit": "a" * 40, "playwright_version": "1.58.2",
                        "application_image": self.image}

    def test_new_accepted_release_does_not_change_existing_parity_inputs(self):
        before = inputs(self.fixture, self.catalog)
        latest = copy.deepcopy(next(item for item in self.catalog["resources"] if item["identity"] == self.image))
        latest.update(version="99.0.0", identity="ghcr.io/xormania/flowbite-xor-dev@sha256:" + "a" * 64)
        self.catalog["resources"].append(latest)
        self.assertEqual(inputs(self.fixture, self.catalog), before)
        self.assertEqual(application_image(self.catalog), latest["identity"])

    def test_missing_mutable_or_unaccepted_pin_fails_instead_of_using_latest(self):
        for identity in (None, "", "ghcr.io/xormania/flowbite-xor-dev:8.5-trixie-v1",
                         "ghcr.io/xormania/flowbite-xor-dev@sha256:" + "b" * 64):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                inputs(dict(self.fixture, application_image=identity), self.catalog)
        self.catalog["resources"] = [item for item in self.catalog["resources"] if item["identity"] != self.image]
        with self.assertRaisesRegex(ValueError, "not accepted"):
            inputs(self.fixture, self.catalog)
