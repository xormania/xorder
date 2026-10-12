"""Regression coverage for cache integrity, MCP shell sessions and host budgets."""
import importlib.util
import hashlib
import io
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
sys.path.insert(0, str(ROOT / "examples/serena"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rootfs(*layers):
    """Distinct valid diff IDs with deterministic prefix relationships."""
    return {"Layers": ["sha256:" + hashlib.sha256(layer.encode()).hexdigest() for layer in layers]}


cache = load("dependency_cache", "examples/uxor/cache.py")
runtime = load("host_runtime", "examples/shared/runtime.py")
client = load("shell_serena", "examples/serena/client.py")
integration = load("serena_integration", "images/php-serena/integration.py")
trust = load("profile_trust", "examples/uxor/trust.py")


class DependencySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vendor = self.root / "one/demo/vendor"
        (self.vendor / "composer").mkdir(parents=True)
        (self.vendor / "composer/installed.json").write_text('{"dev":true,"packages":[]}')
        (self.vendor / "bin").mkdir()
        (self.vendor / "bin/tool").write_text("#!/bin/sh\nexit 0\n")
        (self.vendor / "bin/tool").chmod(0o755)
        self.vendor.joinpath("link").symlink_to("composer/installed.json")
        self.archive = self.root / "vendor.zip"
        cache.write_archive(self.vendor, self.archive, "proof")

    def test_restores_metadata_modes_and_links_in_another_worktree(self):
        target = self.root / "two/demo/vendor"
        self.assertTrue(cache.restore_archive(self.archive, target, "proof", self.root / "two"))
        self.assertEqual((target / "composer/installed.json").read_bytes(), (self.vendor / "composer/installed.json").read_bytes())
        self.assertEqual((target / "bin/tool").stat().st_mode & 0o777, 0o755)
        self.assertTrue((target / "link").is_symlink())
        self.assertFalse(cache.restore_archive(self.archive, target, "proof", self.root / "two"))

    def test_corrupt_snapshot_never_promotes_partial_dependencies(self):
        with zipfile.ZipFile(self.archive) as source:
            data = {name: source.read(name) for name in source.namelist()}
        data["files/composer/installed.json"] = b"corrupt"
        with zipfile.ZipFile(self.archive, "w") as output:
            for name, value in data.items():
                output.writestr(name, value)
        target = self.root / "two/demo/vendor"
        with self.assertRaisesRegex(ValueError, "checksum"):
            cache.restore_archive(self.archive, target, "proof", self.root / "two")
        self.assertFalse(target.exists())

    def test_lock_runtime_and_image_each_invalidate_reuse(self):
        project = self.vendor.parent
        (project / "composer.lock").write_text('{"packages":[]}')
        (project / "composer.json").write_text('{}')
        first = cache.identity(project, "vendor", "image:a", "8.5")
        self.assertNotEqual(first, cache.identity(project, "vendor", "image:b", "8.5"))
        self.assertNotEqual(first, cache.identity(project, "vendor", "image:a", "8.4"))
        (project / "composer.lock").write_text('{"packages":[{"version":"new"}]}')
        self.assertNotEqual(first, cache.identity(project, "vendor", "image:a", "8.5"))

    def test_archive_cannot_write_through_a_link_or_outside_workspace(self):
        for files in ({"../../escape": {"sha256": "bad", "mode": 0o644}},
                      {"link": {"link": "/tmp"}},
                      {"link": {"link": "composer"}, "link/file": {"sha256": "bad", "mode": 0o644}}):
            with self.subTest(files=files), zipfile.ZipFile(self.archive, "w") as output:
                output.writestr("manifest.json", json.dumps({"schema": 1, "identity": "proof", "files": files}))
            with self.assertRaises(ValueError):
                cache.restore_archive(self.archive, self.root / "two/demo/vendor", "proof", self.root / "two")

    def test_vendor_only_bundle_round_trip_without_selected_importmap(self):
        source = self.vendor.parent
        target = self.root / "two/demo"
        target.mkdir(parents=True)
        for project in (source, target):
            (project / "composer.json").write_text('{}')
            (project / "composer.lock").write_text('{"packages":[]}')
        producer_cache, consumer_cache = self.root / "producer", self.root / "consumer"
        producer_cache.mkdir()
        consumer_cache.mkdir()
        bundle = self.root / "dependencies.zip"
        with patch.dict(os.environ, {"IMPORTMAP_FILE": "custom-missing.php", "IMPORTMAP_VENDOR_DIR": "assets/vendor"}), \
                patch.object(cache.subprocess, "check_output", return_value="8.5"):
            self.assertEqual(cache.main(["export", "--project", str(source), "--cache", str(producer_cache),
                                         "--image", "image:a", "--output", str(bundle)]), 0)
            self.assertEqual(cache.main(["import", "--project", str(target), "--cache", str(consumer_cache),
                                         "--image", "image:a", "--input", str(bundle), "--sha256", cache.sha(bundle)]), 0)
        self.assertEqual((target / "vendor/bin/tool").read_bytes(), (self.vendor / "bin/tool").read_bytes())
        self.assertTrue((target / "vendor/link").is_symlink())
        self.assertFalse((target / "assets/vendor").exists())

    def test_self_consistent_poisoned_bundle_is_rejected_before_promotion(self):
        project = self.root / "two/demo"
        project.mkdir(parents=True)
        consumer_cache = self.root / "consumer"
        consumer_cache.mkdir()
        bundle = self.root / "dependencies.zip"
        with zipfile.ZipFile(bundle, "w") as output:
            output.write(self.archive, "vendor-proof.zip")
        trusted_digest = cache.sha(bundle)
        # The attacker recomputes a consistent manifest after replacing code;
        # internal checksums alone would accept this archive.
        (self.vendor / "autoload.php").write_text("<?php /* attacker payload */")
        cache.write_archive(self.vendor, self.archive, "proof")
        with zipfile.ZipFile(bundle, "w") as output:
            output.write(self.archive, "vendor-proof.zip")
        with patch.object(cache, "identity", return_value="proof"), \
                self.assertRaisesRegex(ValueError, "trusted expected digest"):
            cache.main(["import", "--project", str(project), "--cache", str(consumer_cache),
                        "--input", str(bundle), "--sha256", trusted_digest])
        self.assertFalse((project / "vendor").exists())
        self.assertEqual(list(consumer_cache.glob("*.zip")), [])

    def test_import_requires_a_trusted_digest(self):
        with self.assertRaises(SystemExit) as error:
            cache.main(["import", "--project", str(self.vendor.parent), "--cache", str(self.root),
                        "--input", str(self.archive)])
        self.assertEqual(error.exception.code, 2)

    def test_bundle_replacement_cannot_change_authenticated_bytes(self):
        digest = cache.sha(self.archive)
        with cache.authenticated_bundle(self.archive, digest) as bundle:
            self.archive.write_bytes(b"replaced after authentication")
            self.assertEqual(json.loads(bundle.read("manifest.json"))["identity"], "proof")


class HostBudgetTests(unittest.TestCase):
    def test_gc_recognizes_only_exact_current_and_historical_source_labels(self):
        images = [{"Id": name, "Config": {"Labels": {"org.opencontainers.image.source": source}}}
                  for name, source in (("current", "https://github.com/xormania/xorder"),
                                       ("legacy", "https://github.com/xormania/docker-image-library"),
                                       ("unowned", "https://github.com/xormania/docker-image-library-extra"))]
        def inspect(command, **kwargs):
            if command[1:3] == ["ps", "-aq"]:
                return ""
            if command[1:3] == ["image", "ls"]:
                return "current legacy unowned"
            return json.dumps(images)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                patch.object(runtime.subprocess, "run") as mutate, redirect_stdout(io.StringIO()) as output:
            runtime.gc(dict(os.environ, XDG_CACHE_HOME=directory))
        mutate.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["unused_images"], ["current", "legacy"])

    def test_low_free_space_warns_even_when_host_capacity_is_large(self):
        facts = {"disk_free": int(1.8 * 1024**3), "disk_used": int(36.5 * 1024**3),
                 "disk_total": 256 * 1024**3, "cpus": 4, "load": 1, "memory_available": None}
        output = io.StringIO()
        with patch.object(runtime, "resources", return_value=facts), redirect_stdout(output):
            runtime.print_resources(Path("."), {"XORDER_DISK_WARN_GIB": "3"})
        self.assertIn("disk: 1.8 GiB free", output.getvalue())
        self.assertIn("below 3 GiB free", output.getvalue())
        self.assertNotIn("14%", output.getvalue())

    def test_gc_protects_nonstack_daemons_local_parents_and_explicit_keeps(self):
        images = [
            {"Id": "base", "RootFS": rootfs("a")},
            {"Id": "parent", "RootFS": rootfs("a", "b")},
            {"Id": "local", "RootFS": rootfs("a", "b", "c")},
            {"Id": "serena", "RootFS": rootfs("a", "d")},
            {"Id": "toolkit", "RepoTags": ["toolkit:lint"], "RootFS": rootfs("a", "e")},
            {"Id": "unused", "RootFS": rootfs("a", "f")},
        ]
        for image in images:
            image["Config"] = {"Labels": {"org.opencontainers.image.source": "https://github.com/xormania/xorder"}}
        containers = [{"Id": "daemon", "Image": "serena", "Config": {}, "State": {"Running": True}},
                      {"Id": "stack", "Image": "local", "Config": {}, "State": {"Running": False}}]
        def inspect(argv, **kwargs):
            if argv[1:3] == ["ps", "-aq"]:
                return "daemon stack"
            if argv[1:3] == ["image", "ls"]:
                return " ".join(image["Id"] for image in images)
            if argv[1:3] == ["image", "inspect"]:
                return json.dumps([image for image in images if image["Id"] in argv[3:] or
                                   any(tag in argv[3:] for tag in image.get("RepoTags", []))])
            return json.dumps(containers)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                patch.object(runtime.subprocess, "run") as mutate, redirect_stdout(io.StringIO()) as output:
            runtime.gc(dict(os.environ, XDG_CACHE_HOME=directory), keep=["toolkit:lint"])
            mutate.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["unused_images"], ["unused"])

    def test_parent_metadata_and_created_container_alias_are_protected(self):
        images = [{"Id": "base"}, {"Id": "child", "Parent": "base", "RepoTags": ["child:latest"]}]
        used = runtime.referenced_images([{"Config": {"Image": "child:latest"}}], images)
        self.assertTrue({"base", "child"} <= used)

    def test_missing_actual_image_cannot_be_replaced_by_a_retagged_config_alias(self):
        images = [{"Id": "base", "RootFS": rootfs("a")},
                  {"Id": "new-tag-target", "RepoTags": ["serena:dev"], "RootFS": rootfs("a", "b")},
                  {"Id": "unrelated", "RootFS": rootfs("c")}]
        plan = runtime.image_reference_plan([{"Id": "serena-daemon", "Image": "old-missing-id", "Config": {"Image": "serena:dev"}}], images)
        self.assertEqual(plan["protected"] & {image["Id"] for image in images}, {image["Id"] for image in images})
        self.assertIn("old-missing-id", plan["unresolved"])
        # An untagged but observed immutable image ID needs no old tag fallback.
        plan = runtime.image_reference_plan([{"Id": "created", "Image": "new-tag-target", "Config": {"Image": "removed:old"}}], images)
        self.assertEqual(plan["protected"], {"base", "new-tag-target"})
        self.assertEqual(plan["unresolved"], [])

    def test_missing_layer_metadata_never_proves_an_unrelated_local_image(self):
        for metadata in (None, {}, {"Layers": None}, {"Layers": ["garbage"]}, {"Type": "unknown", **rootfs("a")}):
            with self.subTest(rootfs=metadata):
                images = [{"Id": "live", "RootFS": metadata}, {"Id": "possible-base", "RootFS": rootfs("a")}]
                plan = runtime.image_reference_plan([{"Id": "daemon", "Image": "live"}], images)
                self.assertEqual(plan["protected"], {"live", "possible-base"})
                self.assertIn("possible-base", plan["unverified"])
        images = [{"Id": "live", "RootFS": rootfs("a", "b")}, {"Id": "unknown-base"}]
        plan = runtime.image_reference_plan([{"Id": "created", "Image": "live"}], images)
        self.assertIn("unknown-base", plan["protected"])
        self.assertIn("unknown-base", plan["unverified"])

    def test_typed_scratch_root_and_equal_layer_images_are_conservatively_protected(self):
        images = [{"Id": "scratch", "RootFS": {"Type": "layers"}},
                  {"Id": "live", "RootFS": rootfs("a", "b")},
                  {"Id": "same-files-different-config", "RootFS": rootfs("a", "b")},
                  {"Id": "sibling", "RootFS": rootfs("a", "c")}]
        plan = runtime.image_reference_plan([{"Id": "created", "Image": "live", "State": {"Running": False, "Status": "created"}}], images)
        self.assertEqual(plan["protected"], {"scratch", "live", "same-files-different-config"})
        self.assertEqual(plan["unverified"], {})

    def test_gc_refuses_partial_inspect_observations_before_any_mutation(self):
        for missing in ("container", "image"):
            with self.subTest(missing=missing):
                def inspect(argv, **kwargs):
                    if argv[1:3] == ["ps", "-aq"]:
                        self.assertIn("--no-trunc", argv)
                        return "daemon"
                    if argv[1:3] == ["image", "ls"]:
                        return "image-one image-two"
                    if argv[1:3] == ["image", "inspect"]:
                        return json.dumps([{"Id": "image-one"}])
                    return "[]" if missing == "container" else json.dumps([{"Id": "daemon", "Image": "image-one"}])
                with tempfile.TemporaryDirectory() as directory, patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                        patch.object(runtime.subprocess, "run") as mutate, self.assertRaisesRegex(ValueError, "Incomplete Docker " + missing):
                    runtime.gc(dict(os.environ, XDG_CACHE_HOME=directory), apply=True)
                mutate.assert_not_called()

    def test_apply_rechecks_unknown_layer_metadata_from_a_new_other_runner(self):
        images = [{"Id": "candidate", "RootFS": rootfs("a"),
                   "Config": {"Labels": {"org.opencontainers.image.source": "https://github.com/xormania/xorder"}}},
                  {"Id": "serena", "RootFS": rootfs("b")}]
        observations = {"snapshots": 0}
        def inspect(argv, **kwargs):
            if argv[1:3] == ["ps", "-aq"]:
                observations["snapshots"] += 1
                return "created-daemon" if observations["snapshots"] > 1 else ""
            if argv[1:3] == ["image", "ls"]:
                return "candidate serena"
            if argv[1:3] == ["image", "inspect"]:
                if observations["snapshots"] > 1:
                    return json.dumps([images[0], {"Id": "serena"}])
                return json.dumps(images)
            return json.dumps([{"Id": "created-daemon", "Image": "serena", "State": {"Running": False, "Status": "created"}}])
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                patch.object(runtime.subprocess, "run") as mutate, redirect_stdout(io.StringIO()):
            runtime.gc(dict(os.environ, XDG_CACHE_HOME=directory), apply=True)
        mutate.assert_not_called()

    def test_apply_rechecks_new_container_ancestry_before_image_removal(self):
        image = {"Id": "parent", "RootFS": rootfs("a"),
                 "Config": {"Labels": {"org.opencontainers.image.source": "https://github.com/xormania/xorder"}}}
        child = {"Id": "child", "RootFS": rootfs("a", "b")}
        listings = iter(["", "new-daemon"])
        def inspect(argv, **kwargs):
            if argv[1:3] == ["ps", "-aq"]:
                return next(listings)
            if argv[1:3] == ["image", "ls"]:
                return "parent child"
            if argv[1:3] == ["image", "inspect"]:
                return json.dumps([image, child])
            return json.dumps([{"Id": "new-daemon", "Image": "child"}])
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                patch.object(runtime.subprocess, "run") as mutate, redirect_stdout(io.StringIO()):
            runtime.gc(dict(os.environ, XDG_CACHE_HOME=directory), apply=True)
            mutate.assert_not_called()

    def test_another_worktree_cannot_start_a_second_heavy_run(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, XDG_CACHE_HOME=directory, XORDER_TEST_MAX_RUNS="1")
            with runtime.heavy_run(Path(directory), env):
                script = "import sys; from pathlib import Path; import runtime;\nwith runtime.heavy_run(Path(sys.argv[1]), __import__('os').environ): pass"
                result = subprocess.run([sys.executable, "-c", script, directory],
                    env=dict(env, PYTHONPATH=str(ROOT / "examples/shared")), capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Another heavy test run", result.stderr)
            with runtime.heavy_run(Path(directory), env) as workers:
                self.assertGreaterEqual(workers, 1)

    def test_busy_host_reduces_worker_budget(self):
        facts = {"cpus": 8, "load": 7, "memory_available": 2 * 1024**3}
        with patch.object(runtime, "resources", return_value=facts):
            self.assertEqual(runtime.worker_budget(Path("."), {}), 1)

    def test_gc_does_not_touch_running_or_unowned_containers_or_referenced_images(self):
        containers = [
            {"Id": "running", "Image": "image1", "Config": {"Labels": {"dev.xorder.workspace": "/one"}}, "State": {"Running": True}},
            {"Id": "stopped", "Image": "image2", "Config": {"Labels": {"dev.xorder.workspace": "/two"}}, "State": {"Running": False}},
            {"Id": "unowned", "Image": "image4", "Config": {"Labels": {}}, "State": {"Running": False}},
        ]
        images = [{"Id": "image" + str(i), "RootFS": rootfs(str(i)),
                   "Config": {"Labels": {"org.opencontainers.image.source": "https://github.com/xormania/xorder"}}} for i in range(1, 5)]
        def inspect(argv, **kwargs):
            if argv[1:3] == ["ps", "-aq"]:
                return "running stopped unowned"
            if argv[1:3] == ["image", "ls"]:
                return "image1 image2 image3 image4"
            if argv[1:3] == ["image", "inspect"]:
                return json.dumps(images)
            return json.dumps([item for item in containers if item["Id"] in argv[2:]])
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(runtime.subprocess, "check_output", side_effect=inspect), \
                patch.object(runtime.subprocess, "run") as mutate:
            env = dict(os.environ, XDG_CACHE_HOME=directory)
            runtime.gc(env)
            mutate.assert_not_called()
            runtime.gc(env, apply=True)
            calls = [call.args[0] for call in mutate.call_args_list]
            self.assertEqual(calls, [["docker", "rm", "stopped"], ["docker", "image", "rm", "image3"]])


class TrustDedupTests(unittest.TestCase):
    def test_full_bundle_keeps_only_unique_additional_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "system"
            system.mkdir()
            certs = []
            for i in range(2):
                path = root / f"{i}.crt"
                subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                                "-subj", f"/CN=XorderFeedback{i}", "-keyout", str(root / f"{i}.key"), "-out", str(path)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                certs.append(path.read_text())
            (system / "existing.crt").write_text(certs[0])
            result = trust.additional(certs[0] + certs[1] + certs[1], system)
            self.assertEqual(len(list(trust.certificates(result))), 1)
            self.assertEqual(next(trust.certificates(result))[0], next(trust.certificates(certs[1]))[0])
            with self.assertRaises(ValueError):
                trust.additional(certs[0] + "private key or truncated data", system)


class ShellMCPTests(unittest.TestCase):
    def test_session_identity_and_execution_failure_are_machine_readable(self):
        result = integration.enrich({"result": {"content": [{"type": "text", "text": "Your Serena session id is `example`."}]}})
        self.assertEqual(result["result"]["structuredContent"]["session_id"], "example")
        error = integration.enrich({"result": {"content": [{"type": "text", "text": "RuntimeError: language server not running"}]}})
        self.assertTrue(error["result"]["isError"])

    def test_shell_client_reuses_one_protocol_session_and_does_not_hide_errors(self):
        source = '''import json,sys
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 p=m.get('params',{})
 if m['method']=='initialize': result={'protocolVersion':'2025-03-26','capabilities':{},'serverInfo':{'name':'fixture','version':'1'}}
 elif p.get('name')=='initial_instructions': result={'structuredContent':{'session_id':'fixture'},'content':[]}
 else:
  code=p['arguments']['code']; result={'content':[{'type':'text','text':'RuntimeError: failed' if code=='fail' else code}], 'isError':code=='fail'}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':result}),flush=True)
'''
        service = client.MCP([sys.executable, "-u", "-c", source], timeout=5)
        try:
            self.assertTrue(service.repl("42")["ok"])
            result = service.repl("fail")
            self.assertFalse(result["ok"])
            self.assertEqual(result["session_id"], "fixture")
            service.process.terminate(); service.process.wait()
            with self.assertRaisesRegex(RuntimeError, "not running"):
                service.repl("again")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
