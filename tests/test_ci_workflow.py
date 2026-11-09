"""Behavioral checks for the required validation aggregate and its parallel jobs."""
import os
from pathlib import Path
import re
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return (ROOT / '.github/workflows/validate.yml').read_text()


def job(source, name):
    match = re.search(rf'^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z-]*:\n|\Z)', source, re.M | re.S)
    if not match:
        raise AssertionError(f'Missing required job: {name}')
    return match[1]


class ValidationWorkflowTests(unittest.TestCase):
    def test_runtime_checks_start_from_metadata_without_waiting_for_unit_tests(self):
        source = workflow()
        self.assertNotIn('unittest discover', job(source, 'metadata'))
        for name in ('images', 'resources', 'environments', 'application', 'unit-tests'):
            with self.subTest(job=name):
                self.assertIn('    needs: [metadata, fast-checks]\n', job(source, name))
        units = job(source, 'unit-tests')
        self.assertIn('python -m unittest discover -s tests -v', units)
        self.assertIn('python -m compileall', units)
        self.assertIn('bash -n', units)

    def test_skipping_unit_job_requires_same_head_validation_evidence(self):
        source = workflow()
        self.assertIn('same_head: ${{ steps.validation-base.outputs.same_head }}', job(source, 'metadata'))
        self.assertIn("if: needs.metadata.outputs.same_head != 'true'", job(source, 'unit-tests'))

    def test_required_aggregate_fails_closed_on_unit_job_outcomes(self):
        source = job(workflow(), 'checks')
        needs = re.search(r'needs: \[([^]]+)\]', source)[1].split(', ')
        self.assertIn('unit-tests', needs)
        bindings = re.findall(r'([A-Z_]+): \$\{\{ needs\.([a-z-]+)\.result \}\}', source)
        variable = next(name for name, producer in bindings if producer == 'unit-tests')
        script = textwrap.dedent(source.split('        run: |\n', 1)[1])
        environment = {**os.environ, **{name: 'success' for name, _ in bindings}, 'SAME_HEAD': ''}
        for result, reused, accepted in (
            ('success', '', True), ('success', 'true', True),
            ('skipped', 'true', True), ('skipped', '', False), ('skipped', 'false', False),
            ('failure', '', False), ('failure', 'true', False),
            ('cancelled', '', False), ('cancelled', 'true', False), ('', '', False),
        ):
            with self.subTest(result=result, reused=reused):
                run = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                     env={**environment, variable: result, 'SAME_HEAD': reused}, capture_output=True)
                self.assertEqual(run.returncode == 0, accepted, run.stderr)
        run = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                             env={**environment, variable: 'skipped', 'SAME_HEAD': 'true', 'METADATA': 'failure'},
                             capture_output=True)
        self.assertNotEqual(run.returncode, 0)


if __name__ == '__main__':
    unittest.main()
