"""Startup budget decisions, actual cooperative leases and passive activity signals."""
from contextlib import redirect_stdout
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
import pull_budget
import runtime


def manifest(size=100):
    return {"config": {"digest": "sha256:config", "size": 10}, "layers": [
        {"digest": "sha256:shared", "size": size, "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip"}]}


class PullBudgetTests(unittest.TestCase):
    def test_index_uses_daemon_platform_and_retains_registry_port(self):
        index = {"manifests": [
            {"digest": "sha256:amd", "platform": {"os": "linux", "architecture": "amd64"}},
            {"digest": "sha256:arm", "platform": {"os": "linux", "architecture": "arm64"}}]}
        with patch.object(pull_budget, "docker_json", side_effect=[index, manifest()]) as docker:
            self.assertEqual(pull_budget.image_manifest("registry.test:443/kit:latest", "linux/amd64", {}), manifest())
        self.assertEqual(docker.call_args.args[0], ["manifest", "inspect", "registry.test:443/kit@sha256:amd"])
        with patch.object(pull_budget, "docker_json", return_value=index):
            self.assertIsNone(pull_budget.image_manifest("kit:latest", None, {}))

    def test_invalid_descriptor_size_is_unknown(self):
        for invalid in (-1, True, "100", None):
            with self.subTest(size=invalid):
                self.assertIsNone(pull_budget.manifest_blobs(manifest(invalid)))

    def run_preflight(self, free, images=("one:tag", "two:tag"), known=None, confirm_root=True, **env):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            if confirm_root:
                env["XORDER_DOCKER_DATA_DIR"] = directory
            info = {"DockerRootDir": directory, "OSType": "linux", "Architecture": "x86_64"}
            def docker(arguments, environment):
                return info if arguments[0] == "info" else [] if arguments[:2] == ["image", "inspect"] else manifest()
            output = io.StringIO()
            with patch.object(pull_budget, "docker_json", side_effect=docker), \
                    patch.object(pull_budget, "recorded_sizes", return_value=known or {}), \
                    patch.object(shutil, "disk_usage", return_value=shutil._ntuple_diskusage(free * 2, free, free)), \
                    redirect_stdout(output):
                facts = pull_budget.preflight(workspace, {"services": {str(n): {"image": image}
                    for n, image in enumerate(images)}}, env, ROOT)
            return facts, output.getvalue()

    def test_shared_registry_blobs_count_once_and_estimate_stays_explicit(self):
        facts, output = self.run_preflight(5 * pull_budget.GIB, XORDER_DISK_RESERVE_GIB="0")
        self.assertEqual(facts["advertised_unique_blob_bytes"], 110)
        self.assertEqual(facts["pull_estimate_bytes"], 660)
        self.assertIn("compressed layers", output)
        self.assertIn("unpacked size unknown", output)

    def test_measured_size_and_reserve_can_refuse_before_startup(self):
        with self.assertRaisesRegex(ValueError, "Docker data filesystem is below"):
            self.run_preflight(2 * pull_budget.GIB, images=("one:tag",), known={"one:tag": pull_budget.GIB})
        facts, output = self.run_preflight(2 * pull_budget.GIB, images=("one:tag",),
            known={"one:tag": pull_budget.GIB}, XORDER_DISK_PREFLIGHT="warn")
        self.assertEqual(facts["pull_estimate_bytes"], 2 * pull_budget.GIB)
        self.assertIn("WARNING: disk preflight", output)
        with tempfile.TemporaryDirectory() as directory, patch.object(pull_budget, "docker_json") as network, \
                patch.object(shutil, "disk_usage", return_value=shutil._ntuple_diskusage(100, 90, 10)):
            with self.assertRaisesRegex(ValueError, "configured stack reserve"):
                pull_budget.preflight(Path(directory), {"services": {}}, {}, ROOT)
            network.assert_not_called()

    def test_accessible_daemon_reported_root_is_not_assumed_to_be_client_local(self):
        # The reported root happens to exist on the client, but can belong to a
        # Desktop VM or mounted socket's host. It cannot justify disk refusal.
        facts, output = self.run_preflight(2 * pull_budget.GIB, images=("one:tag",),
            known={"one:tag": pull_budget.GIB}, confirm_root=False)
        self.assertIsNone(facts["docker_free_bytes"])
        self.assertFalse(facts["docker_data_root_confirmed"])
        self.assertTrue(facts["daemon_reported_data_root"])
        self.assertIn("does not establish filesystem locality", output)

    def test_correct_local_image_variant_needs_no_cold_pull_allowance(self):
        info = {"OSType": "linux", "Architecture": "arm"}
        local = [{"Os": "linux", "Architecture": "arm", "Variant": "v7"}]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(pull_budget, "docker_json", side_effect=[info, local]) as docker, \
                redirect_stdout(io.StringIO()) as output:
            facts = pull_budget.preflight(Path(directory), {"services": {"php": {
                "image": "kit:arm", "platform": "linux/arm/v7"}}}, {"XORDER_DISK_RESERVE_GIB": "0"}, ROOT)
        self.assertEqual(facts["pull_estimate_bytes"], 0)
        self.assertIn("already local", output.getvalue())
        self.assertEqual(docker.call_count, 2)

    def test_missing_metadata_and_remote_disk_do_not_become_zero_size_claims(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(pull_budget, "docker_json", return_value=None), \
                redirect_stdout(io.StringIO()) as output:
            facts = pull_budget.preflight(Path(directory), {"services": {"php": {"image": "unknown:tag"}}}, {}, ROOT)
        self.assertEqual(facts["unknown_images"], ["unknown:tag"])
        self.assertIsNone(facts["docker_free_bytes"])
        self.assertIn("cannot fully budget", output.getvalue())
        self.assertIn("daemon/VM disk separately", output.getvalue())


class LeaseAndActivityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.env = dict(os.environ, XDG_CACHE_HOME=str(self.workspace), XORDER_TEST_MAX_RUNS="1",
                        XORDER_TEST_WAIT_SECONDS="0", XORDER_TEST_MEASURE="0", FLOWBITE_PROJECT="lease-owner")

    def child(self, **overrides):
        code = ("import os; from pathlib import Path; import runtime;\n"
                "with runtime.heavy_run(Path(os.environ['XDG_CACHE_HOME']), os.environ): print('acquired', flush=True)")
        return subprocess.Popen([sys.executable, "-c", code], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(self.env, PYTHONPATH=str(ROOT / "examples/shared"), **overrides))

    def test_busy_refusal_identifies_holder_and_queued_process_eventually_runs(self):
        with runtime.heavy_run(self.workspace, self.env):
            refused = self.child()
            stdout, stderr = refused.communicate(timeout=5)
            self.assertNotEqual(refused.returncode, 0)
            for expected in ("lease-owner", str(self.workspace), "age=", "PID=", "--wait"):
                self.assertIn(expected, stderr)
            queued = self.child(XORDER_TEST_WAIT_SECONDS="3")
            self.addCleanup(lambda: queued.kill() if queued.poll() is None else None)
            # Observe its queue announcement while the parent still holds the lease.
            self.assertIn("Waiting for host test budget", queued.stdout.readline())
            self.assertIsNone(queued.poll())
        stdout, stderr = queued.communicate(timeout=5)
        self.assertEqual(queued.returncode, 0, stderr)
        self.assertIn("acquired", stdout)

    def test_measurement_excludes_other_slots_and_refuses_heavy_host(self):
        quiet = {"cpus": 4, "load": 1, "memory_available": 4 * 1024**3}
        measured = dict(self.env, XORDER_TEST_MEASURE="1", XORDER_TEST_MAX_RUNS="2")
        with patch.object(runtime, "resources", return_value=quiet), redirect_stdout(io.StringIO()):
            with runtime.heavy_run(self.workspace, measured):
                child = self.child(XORDER_TEST_MAX_RUNS="4")
                stdout, stderr = child.communicate(timeout=5)
                self.assertNotEqual(child.returncode, 0)
                self.assertIn("mode=measure", stderr)
        with patch.object(runtime, "resources", return_value=dict(quiet, load=8)):
            with self.assertRaisesRegex(ValueError, "load 8.00, CPU budget 4"):
                with runtime.heavy_run(self.workspace, measured):
                    self.fail("A busy host cannot pass the measuring lease")
        with runtime.heavy_run(self.workspace, self.env):
            pass  # Busy-host refusal releases both the gate and every slot.

    def test_measurement_prevents_new_numbered_slots_from_legacy_runners(self):
        quiet = {"cpus": 4, "load": 0, "memory_available": 4 * 1024**3}
        measured = dict(self.env, XORDER_TEST_MEASURE="1")
        with patch.object(runtime, "resources", return_value=quiet), redirect_stdout(io.StringIO()):
            with runtime.heavy_run(self.workspace, measured):
                # A legacy runner configured for extra runs could otherwise
                # create/acquire a previously absent slot without reading gate.
                for slot in (1, 63):
                    with (runtime.state_root(self.env) / "test-runs" / f"{slot}.lock").open("a+") as legacy:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_nonfinite_wait_settings_are_rejected(self):
        for value in ("nan", "inf", "-1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "XORDER_TEST_WAIT_SECONDS"):
                with runtime.heavy_run(self.workspace, dict(self.env, XORDER_TEST_WAIT_SECONDS=value)):
                    pass

    def test_passive_status_does_not_refresh_idle_clock_or_misread_stale_commands(self):
        self.assertEqual(runtime.activity_status(self.workspace, "app", self.env)["state"], "unknown")
        with runtime.stack_activity(self.workspace, "app", self.env, "exec"):
            self.assertEqual(runtime.activity_status(self.workspace, "app", self.env)["state"], "active")
        folder = runtime._activity_folder(self.workspace, "app", self.env)
        previous = json.loads((folder / "last.json").read_text())
        previous["completed_at"] = time.time() - 4000
        (folder / "last.json").write_text(json.dumps(previous))
        (folder / "active-crashed.json").write_text(json.dumps(previous))
        before = (folder / "last.json").read_bytes()
        with runtime.stack_activity(self.workspace, "app", self.env, "status"):
            self.assertEqual(runtime.activity_status(self.workspace, "app", self.env)["state"], "idle")
        self.assertEqual((folder / "last.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
