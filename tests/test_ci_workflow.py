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

    def test_reusable_runtime_workflows_keep_their_selection_and_matrix_contracts(self):
        source = workflow()
        for name, filename, output in (('images', 'images', 'matrix'),
                                       ('resources', 'resources', 'resources'),
                                       ('environments', 'environments', 'environments'),
                                       ('application', 'application', None)):
            with self.subTest(surface=name):
                caller = job(source, name)
                self.assertIn('uses: ./.github/workflows/validate-' + filename + '.yml', caller)
                self.assertNotIn('runs-on:', caller)
                self.assertNotIn('steps:', caller)
                self.assertNotIn('secrets: inherit', caller)
                runtime = (ROOT / ('.github/workflows/validate-' + filename + '.yml')).read_text()
                self.assertIn('  workflow_call:\n', runtime)
                self.assertNotIn('  pull_request:', runtime)
                self.assertIn('    timeout-minutes:', job(runtime, name))
                self.assertIn('persist-credentials: false', runtime)
                if output:
                    self.assertIn('matrix: ${{ needs.metadata.outputs.' + output + ' }}', caller)
                    self.assertIn('matrix: ${{ fromJSON(inputs.matrix) }}', runtime)
                else:
                    self.assertNotIn('inputs.matrix', runtime)

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

    def test_runtime_skip_requires_an_explicit_unselected_surface(self):
        source = job(workflow(), 'checks')
        script = textwrap.dedent(source.split('        run: |\n', 1)[1])
        bindings = re.findall(r'([A-Z_]+): \$\{\{ needs\.([a-z-]+)\.result \}\}', source)
        selected = re.findall(r'([A-Z_]+_SELECTED): \$\{\{ needs\.metadata\.outputs\.([a-z_]+) \}\}', source)
        self.assertEqual(len(selected), 4)
        environment = {**os.environ, **{name: 'success' for name, _ in bindings},
                       **{name: 'false' for name, _ in selected}, 'SAME_HEAD': ''}
        for flag, _ in selected:
            producer = flag.removesuffix('_SELECTED')
            for selection in ('true', 'false', '', 'invalid'):
                for result in ('success', 'skipped', 'failure', 'cancelled', ''):
                    with self.subTest(surface=producer, selected=selection, result=result):
                        completed = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                            env={**environment, flag: selection, producer: result}, capture_output=True)
                        accepted = result == 'success' or (result == 'skipped' and selection == 'false')
                        self.assertEqual(completed.returncode == 0, accepted, completed.stderr)


if __name__ == '__main__':
    unittest.main()
