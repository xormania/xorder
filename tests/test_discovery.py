"""Current discovery stays small, honest, and tied to exact accepted releases."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from xorder import model
from xorder.inspect import _probe, inspect_target


class DiscoveryContracts(unittest.TestCase):
    def test_latest_skips_unavailable_and_retains_exact_release_identity(self):
        cat = model.catalog()
        newest = model.latest_resources(cat)
        selected = newest[0]
        replacement = copy.deepcopy(selected)
        replacement.update(version='999.0.0', lifecycle='withdrawn', identity='unavailable')
        cat['resources'].append(replacement)
        self.assertEqual(model.latest_resources(cat), newest)
        self.assertEqual(model.latest_resources(cat, include_unavailable=True)[0]['identity'], 'unavailable')
        summary = model.resource_summary(selected)
        self.assertEqual(summary['identity'], selected['identity'])
        self.assertEqual(summary['release_record'], selected['release_record'])
        self.assertNotIn('details', summary)

    def test_navigation_is_compact_and_authored_profiles_do_not_establish_availability(self):
        cat = model.catalog()
        index = model.discovery(cat)
        self.assertLess(len(model.encoded(index)), len(model.encoded(cat)) // 2)
        self.assertEqual(len(index['resources']), len({item['id'] for item in index['resources']}))
        by_id = {item['id']: item for item in index['resources']}
        self.assertEqual(by_id['image/flowbite-xor-dev/8.5-trixie']['identity'],
                         next(item for item in model.latest_resources(cat)
                              if item['id'] == 'image/flowbite-xor-dev/8.5-trixie')['identity'])
        empty = model.discovery({'generated_at': None, 'resources': []})
        self.assertEqual(empty['resources'], [])
        self.assertTrue(all(not group['resources'] for group in empty['groups']))
        self.assertTrue(all(p['catalog_status'] == 'missing_required_releases' for p in empty['profiles']))
        # Existing intentionally older exact profile revisions remain independent
        # of the navigation's newest-resource recommendation.
        tests = next(p for p in index['profiles'] if p['id'] == 'profile/php-tests')
        self.assertEqual(tests['roles'], model.profiles()['profile/php-tests']['roles'])
        self.assertEqual(by_id['image/php-dev/8.5-trixie']['version'],
                         max((item['version'] for item in cat['resources']
                              if item['id'] == 'image/php-dev/8.5-trixie'
                              and item['lifecycle'] == 'available'), key=model.version))

    def test_public_cli_retains_history_and_supports_concise_explicit_lookup(self):
        cli = [sys.executable, str(model.ROOT / 'scripts/xorder_cli.py')]
        def command(*args):
            return json.loads(subprocess.check_output(cli + list(args), text=True))
        history = command('list')
        summary = command('list', '--latest', '--summary')
        self.assertGreater(len(history['resources']), len(summary['resources']))
        self.assertNotIn('details', summary['resources'][0])
        shown = command('show', 'image/php-dev/8.5-trixie', '--version', '1.2.0')
        self.assertEqual(len(shown['resources']), 1)
        self.assertEqual(shown['resources'][0]['version'], '1.2.0')

    def test_navigation_rejects_missing_links(self):
        with self.assertRaisesRegex(ValueError, 'Missing or uncontained'):
            model._discovery_link('docs/not-a-real-guide.md', model.ROOT)
        with self.assertRaisesRegex(ValueError, 'contained relative'):
            model._discovery_link('../outside.md', model.ROOT)

    def test_doctor_reports_missing_engine_without_guessing_target_platform(self):
        selected = next(item for item in model.latest_resources(model.catalog()) if item['kind'] == 'image')
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'composer.lock').write_text('{}')
            with patch('xorder.inspect.shutil.which', return_value=None):
                result = inspect_target(folder, selected)
            self.assertEqual(result['status'], 'prerequisites_missing')
            self.assertEqual(result['gaps'][0]['command'], 'docker')
            self.assertNotIn('platform', result['target'])
            self.assertEqual(result['workspace']['lockfiles'], ['composer.lock'])
            self.assertEqual(result['application_readiness'], 'not_probed')

    def test_doctor_uses_engine_platform_and_fixed_bounded_probes(self):
        selected = next(item for item in model.latest_resources(model.catalog()) if item['kind'] == 'image')
        with tempfile.TemporaryDirectory() as folder:
            with patch('xorder.inspect.platform.system', return_value='Darwin'), \
                 patch('xorder.inspect.shutil.which', return_value='/bin/tool'), \
                 patch('xorder.inspect._probe', side_effect=[{'status': 'passed', 'value': 'linux/x86_64'},
                                                           {'status': 'passed', 'value': '2.1'}]) as probe:
                result = inspect_target(folder, selected, timeout=0.1)
            self.assertEqual(result['status'], 'facts_observed')
            self.assertEqual(result['target']['platform'], 'linux/amd64')
            self.assertTrue(result['host_platform'].startswith('darwin/'))
            self.assertEqual(probe.call_args_list[0].args,
                             (['docker', 'info', '--format', '{{.OSType}}/{{.Architecture}}'], 0.1))
            with self.assertRaisesRegex(ValueError, 'at most 10'):
                inspect_target(folder, timeout=11)
        with patch('xorder.inspect.subprocess.run', side_effect=subprocess.TimeoutExpired(['docker'], 0.1)):
            self.assertEqual(_probe(['docker', 'info'], 0.1), {'status': 'timed_out'})


if __name__ == '__main__':
    unittest.main()
