"""Consumer support checks bind fresh policy to engine-observed content."""
import contextlib
import datetime as dt
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from xorder import downstream as support

NOW = dt.datetime(2026, 10, 14, 8, tzinfo=dt.timezone.utc)
IDENTITY = "ghcr.io/xormania/php-dev@sha256:" + "a" * 64
PLATFORM_IDENTITY = "ghcr.io/xormania/php-dev@sha256:" + "b" * 64


def policy():
    return {"schema_version": 1, "revision": 1,
            "cadence": {"interval_days": 7, "anchor": "2026-10-19T06:00:00Z"},
            "defaults": {"support_days": 28, "warning_days": 7, "removal_grace_days": 14, "max_policy_age_hours": 24},
            "legacy": {"enforce_after": "2026-11-11T08:00:00Z"},
            "groups": [{"schema_version": 1, "id": "weekly-2026-10-12", "state": "accepted", "reason": "scheduled",
                        "accepted_at": "2026-10-12T06:00:00Z", "warning_starts_at": "2026-11-02T06:00:00Z",
                        "support_ends_at": "2026-11-09T06:00:00Z", "removal_eligible_at": "2026-11-23T06:00:00Z",
                        "replacement": None,
                        "resources": [{"line_id": "php-dev/8.5-trixie", "version": "1.0.0", "identity": IDENTITY,
                                       "platforms": [{"platform": "linux/amd64", "digest": "sha256:" + "b" * 64}], "parent": None}]}]}


def lock():
    return {"schema_version": 1, "group": "weekly-2026-10-12",
            "resources": [{"line_id": "php-dev/8.5-trixie", "version": "1.0.0", "identity": IDENTITY,
                           "platform": "linux/amd64", "service": "php"}]}


def snapshot(value=None, fetched=NOW):
    value = value or policy()
    return {"schema_version": 1, "policy": value,
            "receipt": {"url": support.DEFAULT_POLICY_URL,
                        "fetched_at": fetched.isoformat().replace("+00:00", "Z"),
                        "valid_until": (fetched + support.MAX_AGE).isoformat().replace("+00:00", "Z"),
                        "policy_sha256": hashlib.sha256(support.encoded(value)).hexdigest()}}


def image(identity=IDENTITY):
    return {"Id": "sha256:" + "c" * 64, "RepoDigests": [identity], "Os": "linux", "Architecture": "amd64"}


@unittest.skipUnless(os.name == "posix", "Support subprocess observations require POSIX")
class ProcessObservationBoundsTests(unittest.TestCase):
    def failing_child(self, script, message, *arguments, timeout=0.25):
        launched = []
        original = subprocess.Popen
        def launch(*args, **kwargs):
            process = original(*args, **kwargs)
            launched.append(process)
            return process
        started = time.monotonic()
        with patch.object(support, "TIMEOUT", timeout), patch.object(support.subprocess, "Popen", side_effect=launch):
            with self.assertRaisesRegex(ValueError, message):
                support._process_json([sys.executable, "-c", script, *arguments])
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].returncode, "The probe's direct process must be reaped")
        self.assertLess(time.monotonic() - started, 2)

    def test_real_stdout_stderr_and_combined_floods_hit_output_cap(self):
        scripts = {
            "stdout": "import os\nwhile True: os.write(1, b'x' * 8192)",
            "stderr": "import os\nos.write(1, b'{}')\nwhile True: os.write(2, b'x' * 8192)",
            "both": "import os\nwhile True:\n os.write(1, b'x' * 8192)\n os.write(2, b'x' * 8192)",
        }
        for stream, script in scripts.items():
            with self.subTest(stream=stream):
                self.failing_child(script, "combined 2 MiB stdout/stderr limit", timeout=1)

    def test_binary_utf8_json_and_exact_combined_limit_are_accepted(self):
        script = "import os,sys\nos.write(1, b'{}')\nos.write(2, b'x' * (int(sys.argv[1]) - 2))"
        self.assertEqual(support._process_json([sys.executable, "-c", script, str(support.MAX_BYTES)]), {})
        script = "import json,os\nos.write(1,json.dumps({'value':'漢'},ensure_ascii=False).encode('utf-8'))"
        self.assertEqual(support._process_json([sys.executable, "-c", script]), {"value": "漢"})

    def test_hard_wall_deadline_covers_continuous_output_and_closed_pipes(self):
        scripts = {
            "streaming": "import os,time\nwhile True:\n os.write(1,b' ')\n time.sleep(0.01)",
            "closed-pipes": "import os,time\nos.close(1)\nos.close(2)\ntime.sleep(60)",
        }
        for mode, script in scripts.items():
            with self.subTest(mode=mode):
                self.failing_child(script, "timed out")

    def assert_descendant_stopped(self, pid):
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            try:
                state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                return
            if state == "Z":
                return  # Orphan reaping belongs to PID 1; the process is stopped.
            time.sleep(0.005)
        self.fail("Owned probe descendant remained running after cleanup")

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "Linux process observations are required")
    def test_timeout_cleans_only_owned_process_group(self):
        script = """import os,sys,time
from pathlib import Path
pid = os.fork()
if pid == 0:
    os.close(1); os.close(2)
    time.sleep(60)
    os._exit(0)
Path(sys.argv[1]).write_text(str(pid))
print('{}', flush=True)
time.sleep(60)
"""
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"],
                                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "descendant.pid"
                self.failing_child(script, "timed out", str(path))
                self.assert_descendant_stopped(int(path.read_text()))
            self.assertIsNone(unrelated.poll(), "Cleanup must not stop a process outside its owned group")
        finally:
            unrelated.kill()
            unrelated.wait(timeout=1)

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "Linux process observations are required")
    def test_success_also_stops_owned_descendants_after_pipes_close(self):
        script = """import os,sys,time
from pathlib import Path
pid = os.fork()
if pid == 0:
    os.close(1); os.close(2)
    time.sleep(60)
    os._exit(0)
Path(sys.argv[1]).write_text(str(pid))
print('{}', flush=True)
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "descendant.pid"
            self.assertEqual(support._process_json([sys.executable, "-c", script, str(path)]), {})
            self.assert_descendant_stopped(int(path.read_text()))


class PolicyAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "snapshot.json"

    def write(self, value):
        self.path.write_text(json.dumps(value))

    def test_explicit_offline_snapshot_has_bounded_validity(self):
        self.write(snapshot())
        value, fetched, receipt = support.load_policy(policy_file=self.path, now=NOW)
        self.assertEqual(value, policy())
        self.assertEqual(fetched, "2026-10-14T08:00:00Z")
        self.assertEqual(receipt["valid_until"], "2026-10-15T08:00:00Z")
        with self.assertRaisesRegex(ValueError, "expired"):
            support.load_policy(policy_file=self.path, now=NOW + support.MAX_AGE)

    def test_snapshot_tampering_future_receipt_and_extended_validity_fail(self):
        cases = [snapshot(), snapshot(fetched=NOW + dt.timedelta(seconds=1)), snapshot()]
        cases[0]["policy"]["revision"] = 9
        cases[2]["receipt"]["valid_until"] = "2026-10-16T08:00:00Z"
        for value in cases:
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaises(ValueError):
                    support.load_policy(policy_file=self.path, now=NOW)

    def test_bare_policy_checkout_is_not_a_freshness_receipt(self):
        self.write(policy())
        with self.assertRaisesRegex(ValueError, "bare checkout"):
            support.load_policy(policy_file=self.path, now=NOW)

    def test_urls_are_bounded_to_current_public_policy(self):
        for url in ("http://localhost/policy", support.DEFAULT_POLICY_URL.replace("master", "a" * 40),
                    support.DEFAULT_POLICY_URL + "?token=secret", "https://user:password@raw.githubusercontent.com/xormania/xorder/master/lifecycle/release-groups.json"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "canonical"):
                support.fetch_snapshot(url)

    def test_fresh_fetch_does_not_forward_github_tokens_or_follow_redirects(self):
        class Response:
            def __init__(self):
                self.body = io.BytesIO(json.dumps(policy()).encode())
            def geturl(self):
                return support.DEFAULT_POLICY_URL
            def read1(self, size):
                return self.body.read(size)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        with patch.object(support.urllib.request, "build_opener") as opener, patch.dict("os.environ", {"GITHUB_TOKEN": "secret"}):
            opener.return_value.open.return_value = Response()
            value = support._fetch_policy_body(support.DEFAULT_POLICY_URL)
        request = opener.return_value.open.call_args.args[0]
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("Cookie", request.headers)
        self.assertEqual(request.get_header("Cache-control"), "no-cache")
        self.assertEqual(value, policy())
        with self.assertRaisesRegex(ValueError, "redirects"):
            support._NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://example.test")

    def test_policy_worker_has_a_wall_deadline_and_no_repository_credentials(self):
        with patch.object(support, "_process_json", return_value=policy()) as process, \
                patch.dict("os.environ", {"GITHUB_TOKEN": "secret", "GH_TOKEN": "secret", "HTTPS_PROXY": "http://proxy.example:8080"}):
            value = support.fetch_snapshot(now=NOW)
        arguments = process.call_args
        self.assertNotIn("GITHUB_TOKEN", arguments.kwargs["env"])
        self.assertNotIn("GH_TOKEN", arguments.kwargs["env"])
        self.assertEqual(arguments.kwargs["env"]["HTTPS_PROXY"], "http://proxy.example:8080")
        self.assertEqual(value["policy"], policy())

    def test_oversized_file_is_refused(self):
        self.path.write_bytes(b" " * (support.MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "2 MiB"):
            support.read_json(self.path)


class IdentityObservationTests(unittest.TestCase):
    def test_alias_is_checked_using_observed_digest(self):
        with patch.object(support, "_docker", return_value=[image()]) as docker:
            actual = support.observe_images(lock(), {"php": "ghcr.io/xormania/php-dev:8.5-trixie-v1"})
        self.assertEqual(actual[0]["identity"], IDENTITY)
        self.assertEqual(docker.call_args.args[0], ["image", "inspect", "--", "ghcr.io/xormania/php-dev:8.5-trixie-v1"])

    def test_configured_digest_does_not_substitute_for_missing_engine_evidence(self):
        with patch.object(support, "_docker", return_value=[{**image(), "RepoDigests": []}]):
            with self.assertRaisesRegex(ValueError, "observed repository digest"):
                support.observe_images(lock(), {"php": IDENTITY})

    def test_running_container_is_inspected_by_actual_engine_image_id(self):
        container = {"Image": "sha256:" + "c" * 64, "Config": {"Image": IDENTITY,
                     "Labels": {"com.docker.compose.service": "php"}}, "State": {"Running": True}}
        with patch.object(support, "_docker", return_value=[image()]) as docker:
            actual = support.observe_containers(lock(), [container])
        self.assertEqual(docker.call_args.args[0][-1], container["Image"])
        self.assertEqual(actual[0]["identity"], IDENTITY)

    def test_missing_or_duplicate_service_never_passes(self):
        with self.assertRaisesRegex(ValueError, "unique running"):
            support.observe_containers(lock(), [])
        duplicate = lock()
        duplicate["resources"].append(duplicate["resources"][0])
        with self.assertRaisesRegex(ValueError, "unique service"):
            support.observe_images(duplicate, {"php": IDENTITY})

    def test_wrong_repository_is_observed_and_cannot_be_hidden_by_lock(self):
        wrong = "ghcr.io/xormania/uxor-dev@sha256:" + "a" * 64
        with patch.object(support, "_docker", return_value=[image(wrong)]):
            actual = support.observe_images(lock(), {"php": wrong})
        self.assertEqual(actual[0]["identity"], wrong)


class RegistryOwnershipTests(unittest.TestCase):
    def test_known_repository_union_includes_policy_bootstrap_and_withdrawn_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / "release-records/old-toolchain/line/1.0.0.json"
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({"lifecycle": "withdrawn", "verification": {"status": "passed"},
                "publication": {"repository": "ghcr.io/xormania/old-toolchain", "public_pull_verified_at": "2026-10-01T00:00:00Z"}}))
            bootstrap = root / "lifecycle/bootstrap-group.json"
            bootstrap.parent.mkdir()
            bootstrap.write_text(json.dumps({"resources": [{"identity": "ghcr.io/xormania/php-toolkit@sha256:" + "c" * 64}]}))
            current = policy()
            current["groups"].append({"support_ends_at": "2026-10-01T00:00:00Z", "resources": [
                {"identity": "ghcr.io/xormania/historical-toolchain@sha256:" + "d" * 64}]})
            self.assertEqual(support.known_image_repositories(current, root=root), {
                "ghcr.io/xormania/php-dev", "ghcr.io/xormania/php-toolkit", "ghcr.io/xormania/old-toolchain",
                "ghcr.io/xormania/historical-toolchain"})

    def test_registry_references_are_parsed_completely(self):
        self.assertEqual(support._registry_repository(IDENTITY), "ghcr.io/xormania/php-dev")
        self.assertEqual(support._registry_repository("ghcr.io/xormania/php-dev:Alias-v1"), "ghcr.io/xormania/php-dev")
        self.assertEqual(support._registry_repository("ghcr.io/xormania/php-dev-worker:latest"), "ghcr.io/xormania/php-dev-worker")
        for malformed in ("ghcr.io/xormania/php-dev:one:two", "ghcr.io/xormania/php-dev@sha256:short",
                          "ghcr.io/xormania/php-dev/../app:latest"):
            with self.subTest(reference=malformed), self.assertRaisesRegex(ValueError, "complete repository"):
                support._registry_repository(malformed)
        self.assertIsNone(support._registry_repository("ghcr.io/xormania.example/php-dev:latest"))


class EnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.path = self.workspace / "snapshot.json"
        self.path.write_text(json.dumps(snapshot()))
        self.actual = [{"line_id": "php-dev/8.5-trixie", "identity": IDENTITY, "platform": "linux/amd64", "service": "php"}]

    def check_at(self, now):
        self.path.write_text(json.dumps(snapshot(fetched=now)))
        return support.check(lock(), self.actual, policy_file=self.path, now=now)

    def test_warning_and_exact_expiry_boundaries(self):
        self.assertEqual(self.check_at(NOW)["status"], "supported")
        warning = self.check_at(dt.datetime(2026, 11, 2, 6, tzinfo=dt.timezone.utc))
        self.assertTrue(warning["ok"])
        self.assertEqual(warning["status"], "warning")
        expired = self.check_at(dt.datetime(2026, 11, 9, 6, tzinfo=dt.timezone.utc))
        self.assertFalse(expired["ok"])
        self.assertEqual(expired["status"], "unsupported")
        self.assertTrue(expired["errors"][0]["action"])

    def test_cached_wrong_digest_and_wrong_platform_fail(self):
        for field, value in (("identity", "ghcr.io/xormania/php-dev@sha256:" + "d" * 64), ("platform", "linux/arm64")):
            with self.subTest(field=field):
                self.actual[0][field] = value
                report = self.check_at(NOW)
                self.assertFalse(report["ok"])

    def test_platform_manifest_is_allowed_with_group_index_lock(self):
        self.actual[0]["identity"] = PLATFORM_IDENTITY
        self.assertTrue(self.check_at(NOW)["ok"])

    def test_absent_unannounced_policy_does_not_change_consumers(self):
        with patch.object(support, "announced_rollout", return_value=None), patch.object(support, "load_policy") as load:
            result = support.runner_check(self.workspace, {})
        self.assertEqual(result["status"], "not_adopted")
        load.assert_not_called()

    def test_missing_lock_warns_until_announced_deadline_then_fails(self):
        for now, expired in ((NOW, False), (dt.datetime(2026, 11, 11, 8, tzinfo=dt.timezone.utc), True)):
            self.path.write_text(json.dumps(snapshot(fetched=now)))
            with patch.object(support, "announced_rollout", return_value="2026-11-11T08:00:00Z"), \
                    patch.object(support, "utc_now", return_value=now), contextlib.redirect_stdout(io.StringIO()) as output:
                if expired:
                    with self.assertRaisesRegex(ValueError, "adoption deadline"):
                        support.runner_check(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)})
                else:
                    report = support.runner_check(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)})
                    self.assertTrue(report["ok"])
                    self.assertIn("commit xorder-support.lock.json", output.getvalue())

    def test_adopted_runner_cannot_ignore_missing_current_policy(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        with patch.object(support, "observe_images", return_value=self.actual), \
                patch.object(support, "load_policy", side_effect=ValueError("Current support policy is unavailable")):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                support.runner_check(self.workspace, {}, configuration={"services": {"php": {"image": IDENTITY}}})

    def test_missing_xorder_service_lock_fails_before_workload(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        for family in ("playwright-browser", "php-toolkit"):
            configuration = {"services": {"php": {"image": IDENTITY}, "extra": {"image": "ghcr.io/xormania/" + family + ":latest"}}}
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, "missing from support lock: extra"):
                support.runner_check(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)}, configuration=configuration)
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, "missing from support lock: extra"):
                support.runner_precheck(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)}, configuration)

    def test_unrelated_same_owner_app_is_outside_both_release_group_gates(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        configuration = {"services": {"php": {"image": IDENTITY}, "worker": {"image": "ghcr.io/xormania/my-project-worker:latest"}}}
        with patch.object(support, "observe_images", return_value=self.actual):
            prepared = support.runner_precheck(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)}, configuration)
            result = support.runner_check(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)},
                                          configuration=configuration, prepared=prepared)
        self.assertEqual(prepared["services"], ["php"])
        self.assertTrue(result["ok"])

    def test_source_validation_requires_exact_builder_owned_ids(self):
        observed = [{"service": "php", "image_id": "sha256:" + "c" * 64}]
        proof = {"scope": "xorder-source-validation", "source_commit": "a" * 40, "images": observed}
        self.assertEqual(support.source_validation_check(observed, proof)["status"], "source_validation")
        with self.assertRaisesRegex(ValueError, "differ"):
            support.source_validation_check([{**observed[0], "image_id": "sha256:" + "d" * 64}], proof)
        with self.assertRaisesRegex(ValueError, "provenance"):
            support.source_validation_check(observed, {"scope": "source-validation"})

    def test_startup_precheck_rejects_expiry_before_observation_or_pull(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        now = dt.datetime(2026, 11, 9, 6, tzinfo=dt.timezone.utc)
        self.path.write_text(json.dumps(snapshot(fetched=now)))
        with patch.object(support, "utc_now", return_value=now), patch.object(support, "_docker") as docker:
            with patch("release_groups.clock", side_effect=lambda value=None: support.timestamp(value) if isinstance(value, str) else value or now):
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    support.runner_precheck(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)},
                                            {"services": {"php": {"image": IDENTITY}}})
        docker.assert_not_called()

    def test_startup_precheck_preserves_aliases_and_excludes_external_services(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        with patch.object(support, "utc_now", return_value=NOW), \
                patch("release_groups.clock", side_effect=lambda value=None: support.timestamp(value) if isinstance(value, str) else value or NOW):
            prepared = support.runner_precheck(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)},
                {"services": {"php": {"image": "ghcr.io/xormania/php-dev:8.5-trixie-v1"},
                              "database": {"image": "postgres:18"}}})
        self.assertEqual(prepared["services"], ["php"])

    def test_explicit_wrong_digest_fails_before_large_pull(self):
        (self.workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        with patch.object(support, "utc_now", return_value=NOW), \
                patch("release_groups.clock", side_effect=lambda value=None: support.timestamp(value) if isinstance(value, str) else value or NOW):
            with self.assertRaisesRegex(ValueError, "digest differs"):
                support.runner_precheck(self.workspace, {"XORDER_SUPPORT_POLICY_FILE": str(self.path)},
                    {"services": {"php": {"image": "ghcr.io/xormania/php-dev@sha256:" + "d" * 64}}})


class StartupGateOrderingTests(unittest.TestCase):
    def run_startup(self, actual_identity=IDENTITY, now=NOW):
        spec = importlib.util.spec_from_file_location("support_order_runner", ROOT / "examples/uxor/runner.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workspace = Path(temporary.name)
        (workspace / "demo").mkdir()
        (workspace / support.LOCK_NAME).write_text(json.dumps(lock()))
        policy_path = workspace / "policy.json"
        policy_path.write_text(json.dumps(snapshot(fetched=now)))
        events = []
        configuration = {"services": {"php": {"image": IDENTITY}, "browser": {"image": "mcr.microsoft.com/playwright:v1.58.2-noble"},
                                      "database": {"image": "postgres:18"}}}
        def call(arguments, env, **kwargs):
            if "config" in arguments:
                return SimpleNamespace(returncode=0, stdout=json.dumps(configuration), stderr="")
            if "pull" in arguments:
                events.append(("pull", arguments[arguments.index("--") + 1:]))
            if "up" in arguments:
                events.append(("up", []))
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        def inspect(arguments, env=None):
            events.append(("inspect", []))
            return [image(actual_identity)]
        def execute(*args, **kwargs):
            events.append(("project-hook", []))
            return SimpleNamespace(returncode=0, stdout="ready", stderr="")
        env = {**os.environ, "WORKSPACE": str(workspace), "IMAGE": IDENTITY,
               "BROWSER_IMAGE": "mcr.microsoft.com/playwright:v1.58.2-noble", "XORDER_SHARED_CACHE": "0",
               "XORDER_SUPPORT_POLICY_FILE": str(policy_path), "XDG_CACHE_HOME": str(workspace / "cache")}
        observed_container = {"Id": "php", "Image": "sha256:" + "c" * 64,
                              "State": {"Running": True}, "Config": {"Labels": {"com.docker.compose.service": "php"}}}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict("os.environ", env, clear=True))
            for name, value in (("shared_paths", []), ("playwright", "1.58.2"), ("containers", [observed_container]),
                                ("input_fingerprint", "source"), ("service_fingerprint", "service")):
                stack.enter_context(patch.object(runner, name, return_value=value))
            stack.enter_context(patch.object(runner, "ensure_daemon"))
            stack.enter_context(patch.object(runner, "check_ports"))
            stack.enter_context(patch.object(runner, "container_environment", return_value={"NO_PROXY": "localhost", "no_proxy": "localhost"}))
            stack.enter_context(patch.object(runner, "preflight", side_effect=lambda *args: events.append(("preflight", []))))
            stack.enter_context(patch.object(runner, "call", side_effect=call))
            stack.enter_context(patch.object(runner, "php_exec", side_effect=execute))
            stack.enter_context(patch.object(runner, "failure_diagnostics", side_effect=lambda *args: contextlib.nullcontext()))
            stack.enter_context(patch.object(runner, "stack_activity", side_effect=lambda *args: contextlib.nullcontext()))
            stack.enter_context(patch.object(support, "_docker", side_effect=inspect))
            stack.enter_context(patch.object(support, "utc_now", return_value=now))
            stack.enter_context(patch("release_groups.clock", side_effect=lambda value=None: support.timestamp(value) if isinstance(value, str) else value or now))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            try:
                runner.main(["up"])
            except ValueError as error:
                return events, error
        return events, None

    def test_cold_pull_and_actual_gate_precede_all_project_hooks(self):
        events, error = self.run_startup()
        self.assertIsNone(error)
        self.assertEqual(events[:4], [("preflight", []), ("pull", ["php"]), ("inspect", []), ("up", [])])
        self.assertLess(events.index(("inspect", [])), events.index(("project-hook", [])))

    def test_wrong_cached_image_and_expired_group_fail_before_project_hooks(self):
        events, error = self.run_startup("ghcr.io/xormania/php-dev@sha256:" + "d" * 64)
        self.assertIsNotNone(error)
        self.assertNotIn(("up", []), events)
        self.assertNotIn(("project-hook", []), events)
        events, error = self.run_startup(now=dt.datetime(2026, 11, 9, 6, tzinfo=dt.timezone.utc))
        self.assertIsNotNone(error)
        self.assertEqual(events, [])


class TrustedSourceProofTests(unittest.TestCase):
    source = "a" * 40
    ids = {"php": "sha256:" + "c" * 64, "browser": "sha256:" + "e" * 64}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "consumer"
        self.workspace.mkdir()
        self.proof_path = self.root / "source-validation.json"
        self.observed = [{"service": service, "image_id": image_id} for service, image_id in sorted(self.ids.items())]
        support.write_source_proof(self.proof_path, self.observed, self.source)
        self.env = {"XORDER_SOURCE_VALIDATION_PROOF": str(self.proof_path)}

    def test_builder_authors_actual_allowlist_for_publication_and_discards_inherited_proof(self):
        import build
        candidates = [("uxor-dev/8.5-trixie", "php"), ("playwright-browser/1.58-trixie", "browser")]
        for line, service in candidates:
            with self.subTest(line=line), patch.dict("os.environ", {
                    "XORDER_SOURCE_VALIDATION_PROOF": "/untrusted/inherited.json", "XORDER_PARITY_LOCAL_APPLICATION": "stale"}), \
                    patch.object(support, "source_commit", return_value=self.source), \
                    patch.object(support, "observe_source_images", return_value=[{"service": service, "image_id": self.ids[service]}]), \
                    patch.object(build, "inspect"), patch.object(build.subprocess, "run") as run:
                def verify_fixture(arguments, **kwargs):
                    path = Path(kwargs["env"]["XORDER_SOURCE_VALIDATION_PROOF"])
                    self.assertNotEqual(str(path), "/untrusted/inherited.json")
                    self.assertTrue(path.is_file())
                    value = support.read_json(path)
                    self.assertEqual(value["source_commit"], self.source)
                    self.assertEqual(value["images"], [{"service": service, "image_id": self.ids[service]}])
                    if service == "browser":
                        self.assertNotIn("XORDER_PARITY_LOCAL_APPLICATION", kwargs["env"])
                run.side_effect = verify_fixture
                # source_validation defaults false, as it does for publication.
                build.verify(line, IDENTITY, self.root / "inventory.json")
                run.assert_called_once()

    def test_trusted_fixture_adds_companion_only_after_main_candidate_matches(self):
        builder = self.root / "builder.json"
        support.write_source_proof(builder, [{"service": "php", "image_id": self.ids["php"]}], self.source)
        with patch.object(support, "source_commit", return_value=self.source), \
                patch.object(support, "observe_source_images", return_value=self.observed):
            value = support.prepare_fixture_proof(builder, {"php": "candidate:test", "browser": "pinned:test"}, self.proof_path)
        self.assertEqual(value["images"], self.observed)
        with patch.object(support, "source_commit", return_value=self.source), \
                patch.object(support, "observe_source_images", return_value=[
                    {"service": "php", "image_id": "sha256:" + "f" * 64}, self.observed[0]]):
            with self.assertRaisesRegex(ValueError, "differs from builder-owned"):
                support.prepare_fixture_proof(builder, {"php": "candidate:test", "browser": "pinned:test"}, self.proof_path)

    def test_source_scope_uses_exact_ids_without_fetching_downstream_policy_after_deadline(self):
        configuration = {"services": {"php": {"image": "local-candidate:test"}, "browser": {"image": "pinned-companion:test"}}}
        with patch.object(support, "source_commit", return_value=self.source), \
                patch.object(support, "observe_source_images", return_value=self.observed), \
                patch.object(support, "load_policy") as policy_loader:
            prepared = support.runner_precheck(self.workspace, self.env, configuration)
            result = support.runner_check(self.workspace, self.env, configuration=configuration, prepared=prepared)
        policy_loader.assert_not_called()
        self.assertEqual(result["status"], "source_validation")
        self.assertTrue(prepared["source_validation"])

    def test_proof_inside_consumer_or_for_another_checkout_fails(self):
        inside = self.workspace / "forged.json"
        support.write_source_proof(inside, self.observed, self.source)
        with self.assertRaisesRegex(ValueError, "outside the consumer"):
            support.runner_check(self.workspace, {"XORDER_SOURCE_VALIDATION_PROOF": str(inside)})
        with patch.object(support, "source_commit", return_value="b" * 40):
            with self.assertRaisesRegex(ValueError, "validating xorder checkout"):
                support.runner_check(self.workspace, self.env)

    def test_running_image_switch_and_omitted_xorder_service_fail(self):
        containers = [{"Image": self.ids[service], "State": {"Running": True},
                       "Config": {"Labels": {"com.docker.compose.service": service}}} for service in self.ids]
        with patch.object(support, "source_commit", return_value=self.source):
            self.assertEqual(support.runner_check(self.workspace, self.env, containers=containers)["status"], "source_validation")
            containers[0]["Image"] = "sha256:" + "f" * 64
            with self.assertRaisesRegex(ValueError, "differ"):
                support.runner_check(self.workspace, self.env, containers=containers)
            with self.assertRaisesRegex(ValueError, "omits selected xorder service"):
                support.runner_precheck(self.workspace, self.env, {"services": {"third": {"image": "ghcr.io/xormania/php-dev:latest"}}})

    def test_source_scope_excludes_unrelated_same_owner_app(self):
        configuration = {"services": {"php": {"image": "candidate:test"}, "browser": {"image": "companion:test"},
                                      "worker": {"image": "ghcr.io/xormania/my-project-worker:latest"}}}
        with patch.object(support, "source_commit", return_value=self.source), \
                patch.object(support, "observe_source_images", return_value=self.observed) as observe:
            result = support.runner_check(self.workspace, self.env, configuration=configuration)
        self.assertEqual(result["status"], "source_validation")
        self.assertEqual(set(observe.call_args.args[0]), {"php", "browser"})


if __name__ == "__main__":
    unittest.main()
