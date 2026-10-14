"""Service memory attribution, child OOM deltas, and unavailable observations."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/shared"))
import container_memory as memory


def container(running=True, started="2026-10-11T03:00:00Z", killed=False):
    return {"Id": "browser-exact-id", "Config": {"Labels": {"com.docker.compose.service": "browser"}},
            "HostConfig": {"Memory": 512 * 1024**2},
            "State": {"Running": running, "StartedAt": started, "OOMKilled": killed}}


def cgroup(kills=2, peak="500000000"):
    return {"version": 2, "files": {"memory.max": str(512 * 1024**2), "memory.current": "100000000",
            "memory.peak": peak, "memory.events": f"oom 0\noom_kill {kills}\nmax 7\n",
            "memory.events.local": f"oom_kill {kills}\n"}}


class ContainerMemoryTests(unittest.TestCase):
    def observe(self, item=None, probe=None, before=None):
        with patch.object(memory, "_docker", return_value=json.dumps(probe if probe is not None else cgroup())):
            return memory.memory_observations("stack", {}, [item if item is not None else container()], before=before)

    def test_child_oom_is_visible_even_with_live_container_and_false_docker_flag(self):
        before = self.observe()
        after = self.observe(probe=cgroup(kills=3), before=before)
        fact = after["services"][0]
        self.assertIs(fact["oom_killed"], False)
        self.assertEqual(fact["oom_kill_delta"], 1)
        self.assertTrue(fact["command_window_oom"])
        output = io.StringIO()
        with redirect_stdout(output):
            memory.report_failure("stack", {"BROWSER_MEMORY": "4g"}, result=after)
        for expected in ("browser-exact-id", "browser", "0.50 GiB", "oom_kill delta=1", "BROWSER_MEMORY=4g", "out of memory", "raise BROWSER_MEMORY"):
            self.assertIn(expected, output.getvalue())

    def test_historical_counters_and_restarts_are_not_claimed_as_new_command_kills(self):
        before = self.observe()
        stable = self.observe(before=before)["services"][0]
        self.assertEqual(stable["oom_kill_delta"], 0)
        self.assertFalse(stable["command_window_oom"])
        restarted = self.observe(container(started="2026-10-11T04:00:00Z"), cgroup(kills=3), before)["services"][0]
        self.assertIsNone(restarted["oom_kill_delta"])
        self.assertFalse(restarted["command_window_oom"])
        decreased = self.observe(probe=cgroup(kills=1), before=before)["services"][0]
        self.assertIsNone(decreased["oom_kill_delta"])
        self.assertFalse(decreased["command_window_oom"])

    def test_new_docker_oom_flag_and_stopped_container_retain_actual_limit(self):
        before = self.observe()
        with patch.object(memory, "_docker") as execute:
            fact = memory.memory_observations("stack", {}, [container(running=False, killed=True)], before)["services"][0]
        execute.assert_not_called()
        self.assertEqual(fact["docker_limit_bytes"], 512 * 1024**2)
        self.assertTrue(fact["oom_killed_changed"])
        self.assertTrue(fact["command_window_oom"])
        self.assertIsNone(fact["peak_bytes"])
        self.assertIn("stopped container", fact["unavailable"])

    def test_missing_peak_is_unknown_and_v1_counters_remain_observed(self):
        fact = self.observe(probe=cgroup(peak=None))["services"][0]
        self.assertIsNone(fact["peak_bytes"])
        v1 = {"version": 1, "files": {"memory.limit_in_bytes": "536870912", "memory.usage_in_bytes": "300000000",
              "memory.max_usage_in_bytes": "400000000", "memory.oom_control": "under_oom 0\noom_kill 1\n",
              "memory.failcnt": "9"}}
        fact = self.observe(probe=v1)["services"][0]
        self.assertEqual(fact["peak_bytes"], 400000000)
        self.assertEqual(fact["events"]["oom_kill"], 1)
        self.assertEqual(fact["limit_hits"], 9)

    def test_observation_failure_does_not_replace_the_command_exit(self):
        original = subprocess.CalledProcessError(17, ["docker", "compose", "exec"])
        with patch.object(memory, "memory_observations", side_effect=OSError("daemon unavailable")), redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                with memory.failure_diagnostics("stack", {}):
                    raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(raised.exception.returncode, 17)
        self.assertIn("original command failure retained", output.getvalue())

    @unittest.skipUnless(shutil.which("node"), "Node is needed to verify cgroup namespace selection")
    def test_probe_resolves_private_and_host_v2_and_subtree_v1_without_host_root_mixup(self):
        module = str(ROOT / "examples/shared/memory-probe.cjs")
        program = ("const probe=require(process.argv[1]); const files=JSON.parse(process.argv[2]); "
                   "console.log(JSON.stringify(probe({readFileSync(name){if(!(name in files))throw Error('missing');return files[name];}}))); ")
        for membership, mount, directory, version, limit_file in (
            ("0::/system.slice/docker-id.scope", "1 0 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw", "/sys/fs/cgroup/system.slice/docker-id.scope", 2, "memory.max"),
            ("0::/", "1 0 0:1 /docker/id /sys/fs/cgroup rw - cgroup2 cgroup rw", "/sys/fs/cgroup", 2, "memory.max"),
            ("3:memory:/docker/id", "1 0 0:1 /docker/id /sys/fs/cgroup/memory rw - cgroup cgroup rw,memory", "/sys/fs/cgroup/memory", 1, "memory.limit_in_bytes"),
        ):
            with self.subTest(version=version, directory=directory):
                files = {"/proc/self/cgroup": membership, "/proc/self/mountinfo": mount,
                         directory + "/" + limit_file: "536870912"}
                # An unrelated host-root value must not win on host cgroup namespaces.
                if directory != "/sys/fs/cgroup":
                    files["/sys/fs/cgroup/memory.max"] = "max"
                result = subprocess.run(["node", "-e", program, module, json.dumps(files)], text=True, capture_output=True, check=True)
                facts = json.loads(result.stdout)
                self.assertEqual(facts["directory"], directory)
                self.assertEqual(facts["version"], version)
                self.assertEqual(facts["files"][limit_file], "536870912")


if __name__ == "__main__":
    unittest.main()
