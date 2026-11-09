"""PHP build boundaries through the same input model used for publication."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import components
from library import definitions


ROOT = Path(__file__).resolve().parents[1]


class PhpComponentBoundaries(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="xorder-php-components-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("images", "scripts", "schemas", "examples"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / ".dockerignore", self.root / ".dockerignore")
        self.ids = {"php-cli-foundation-84", "php-cli-foundation-85", "php-native-84",
                    "php-native-85", "php-tools-portable", "php-tool-downloads"}
        self.tools = json.loads((self.root / "images/tools.json").read_text())

    def keys(self, tools=None):
        return {name: components.build_key(name, self.root, tools=tools) for name in self.ids}

    def changed_keys(self, before, after):
        return {name for name in before if before[name] != after[name]}

    def test_portable_tool_lock_change_preserves_both_native_abis_and_foundations(self):
        before = self.keys()
        lock = self.root / "images/shared/php-tools-composer.lock"
        lock.write_bytes(lock.read_bytes() + b"\n")
        self.assertEqual(self.changed_keys(before, self.keys()), {"php-tools-portable"})
        self.assertEqual(components.affected_components([str(lock.relative_to(self.root))], self.root),
                         ["php-tools-portable"])

    def test_symfony_and_infection_refresh_do_not_compile_native_extensions(self):
        before = self.keys()
        for tool in ("symfony", "infection"):
            with self.subTest(tool=tool):
                changed = copy.deepcopy(self.tools)
                changed[tool]["sha256"] = "e" * 64
                changed[tool]["url"] += "/refresh"
                self.assertEqual(self.changed_keys(before, self.keys(changed)), {"php-tool-downloads"})

    def test_apt_and_runtime_base_refreshes_preserve_downloaded_tool_component(self):
        before = components.build_key("php-tool-downloads", self.root)
        refreshed = copy.deepcopy(self.tools)
        refreshed["apt_indexes"] = {url: "f" * 64 for url in refreshed["apt_indexes"]}
        self.assertEqual(components.build_key("php-tool-downloads", self.root, tools=refreshed), before)
        # The downloader has its own qualified immutable Python donor, rather than
        # following either runtime image's refresh policy.
        for family, variant in (("php-dev", "8.4-trixie"), ("python-dev", "3.14-trixie")):
            with self.subTest(family=family):
                path = self.root / "images" / family / "definition.json"
                definition = json.loads(path.read_text())
                definition["lines"][variant]["base"]["digest"] = "sha256:" + "e" * 64
                path.write_text(json.dumps(definition))
                self.assertEqual(components.build_key("php-tool-downloads", self.root), before)

    def test_native_extension_pin_changes_do_not_prepare_portable_php_tools(self):
        before = self.keys()
        for tool in ("redis_version", "xdebug_version", "pcov_version"):
            with self.subTest(tool=tool):
                changed = copy.deepcopy(self.tools)
                changed[tool] += ".changed"
                self.assertEqual(self.changed_keys(before, self.keys(changed)),
                                 {"php-native-84", "php-native-85"})

    def test_node_and_npm_refreshes_preserve_compatibility_python_and_phpactor(self):
        ids = ("php-serena-python-85", "phpactor-payload")
        before = {name: components.build_key(name, self.root) for name in ids}
        changed = copy.deepcopy(self.tools)
        changed["node"]["digest"] = "sha256:" + "e" * 64
        javascript = components.build_key("php-serena-javascript", self.root)
        self.assertNotEqual(components.build_key("php-serena-javascript", self.root, tools=changed), javascript)
        for name in ids:
            self.assertEqual(components.build_key(name, self.root, tools=changed), before[name])
        lock = self.root / "images/php-serena/package-lock.json"
        lock.write_bytes(lock.read_bytes() + b"\n")
        self.assertNotEqual(components.build_key("php-serena-javascript", self.root), javascript)
        for name in ids:
            self.assertEqual(components.build_key(name, self.root), before[name])
        self.assertEqual(components.affected_components([str(lock.relative_to(self.root))], self.root),
                         ["php-serena-javascript"])

    def test_compatibility_security_lock_reprepares_python_without_phpactor_download(self):
        ids = ("php-serena-python-85", "phpactor-payload", "php-serena-javascript")
        before = {name: components.build_key(name, self.root) for name in ids}
        lock = self.root / "images/php-serena/security-uv.lock"
        lock.write_bytes(lock.read_bytes() + b"\n")
        self.assertNotEqual(components.build_key(ids[0], self.root), before[ids[0]])
        self.assertEqual(components.build_key(ids[1], self.root), before[ids[1]])
        self.assertEqual(components.build_key(ids[2], self.root), before[ids[2]])
        self.assertEqual(components.affected_components([str(lock.relative_to(self.root))], self.root), [ids[0]])

    def test_compatibility_venv_uses_final_parents_debian_python_donor(self):
        images = definitions(self.root)
        image = images["php-serena/8.5-trixie"]
        parent = images[image["base"]["parent"]]
        prepared = components.build_inputs(image["build_components"]["SERENA_PYTHON_IMAGE"], self.root)
        runtime_donor = prepared["components"]["BASE_IMAGE"]
        self.assertEqual(runtime_donor["id"], parent["build_components"]["PHP_EXTENSIONS_IMAGE"])
        self.assertEqual(runtime_donor["key"], components.build_key(runtime_donor["id"], self.root))

    def test_toolkit_project_locks_are_not_compiled_runtime_or_general_tool_inputs(self):
        before = self.keys()
        for project in ("validator", "symfony-7.4"):
            with self.subTest(project=project):
                path = self.root / "examples/php-toolkit" / project / "composer.lock"
                path.write_bytes(path.read_bytes() + b"\n")
                self.assertEqual(self.changed_keys(before, self.keys()), set())
                self.assertEqual(components.affected_components([str(path.relative_to(self.root))], self.root), [])

    def test_native_component_matches_public_runtime_and_portable_payload_is_shared(self):
        images = definitions(self.root)
        portable = set()
        for line, definition in images.items():
            if definition["family"] != "php-dev":
                continue
            with self.subTest(line=line):
                inputs = components.image_inputs(definition, self.root)
                self.assertEqual(inputs["PHP_EXTENSIONS_IMAGE"]["abi"],
                                 "php-cli-" + definition["runtime_line"] + "-trixie")
                portable.add(inputs["PHP_TOOLS_IMAGE"]["key"])
        self.assertEqual(len(portable), 1)
        for line, definition in images.items():
            if definition["family"] in {"php-frankenphp", "uxor-dev"}:
                with self.subTest(unchanged=line):
                    self.assertFalse(definition.get("build_components"))


if __name__ == "__main__":
    unittest.main()
