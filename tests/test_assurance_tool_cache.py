"""Publication attempts should reuse immutable tools without retaining scanner data."""
import re
import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml"


def tool_restores(source):
    return [part.split("\n      - ", 1)[0] for part in source.split("id: tool-downloads\n")[1:]]


def render_key(template, *, run, attempt, job, index, tools="a" * 64):
    values = {"runner.os": "Linux", "hashFiles('scripts/image_assurance.py')": tools,
              "github.run_id": str(run), "github.run_attempt": str(attempt),
              "github.job": job, "strategy.job-index || 0": str(index)}
    return re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda match: values[match[1].strip()], template)


class AssuranceToolCacheTests(unittest.TestCase):
    def test_cache_identity_survives_new_jobs_runs_and_retries_but_changes_with_tools(self):
        restores = tool_restores(WORKFLOW.read_text())
        self.assertEqual(len(restores), 3)
        identities = set()
        for block in restores:
            template = re.search(r"^          key: (.+)$", block, re.M)[1]
            identities.update(render_key(template, run=run, attempt=attempt, job=job, index=index)
                              for run, attempt, job, index in (
                                  (1, 1, "publish", 0), (2, 1, "publish", 7),
                                  (2, 2, "publish-browser", 0), (3, 1, "assure-existing", 0)))
            self.assertNotEqual(render_key(template, run=1, attempt=1, job="publish", index=0),
                                render_key(template, run=1, attempt=1, job="publish", index=0, tools="b" * 64))
        self.assertEqual(len(identities), 1, "A publication attempt must not allocate another immutable tool cache")

    def test_restored_saved_and_installed_tools_share_a_dedicated_directory(self):
        source = WORKFLOW.read_text()
        paths = [re.search(r"^          path: (.+)$", block, re.M)[1]
                 for block in tool_restores(source)]
        installers = re.findall(
            r"run: python scripts/image_assurance.py install-(?:signer|scanner)[^\n]*\n"
            r"        env:\n          XORDER_DOWNLOAD_CACHE: ([^\n]+)", source)
        saves = re.findall(r"name: Retain verified assurance tools\n(.*?)\n      - ", source, re.S)
        self.assertEqual(len(installers), 6)
        self.assertEqual(len(saves), 3)
        for block in saves:
            self.assertIn("steps.install-signer.outcome == 'success'", block)
            self.assertIn("steps.install-scanner.outcome == 'success'", block)
        paths.extend(installers)
        paths.extend(re.search(r"^          path: (.+)$", block, re.M)[1] for block in saves)
        self.assertEqual(len(set(paths)), 1)
        self.assertNotIn(Path(paths[0]).name, ("xorder-build-downloads", "trivy"))
        self.assertNotIn("TRIVY_CACHE_DIR", source)


if __name__ == "__main__":
    unittest.main()
