"""Current discovery stays small, honest, and tied to exact accepted releases."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from xorder import model
from xorder.inspect import _probe, inspect_target
import library


class DiscoveryContracts(unittest.TestCase):
    def test_current_projection_preserves_recorded_assurance_without_inventing_history(self):
        record = copy.deepcopy(next(item for item in library.records() if item['lifecycle'] == 'available'))
        record.pop('assurance', None)  # Exercise the historical shape explicitly.
        self.assertNotIn('assurance', model.resource_summary(model.image_entry(record)))
        assurance = {'receipt_url': 'https://github.com/xormania/xorder/releases/download/test-assurance/assurance.json',
                     'receipt_sha256': 'd' * 64,
                     'predicate_type': 'https://github.com/xormania/xorder/assurance/v1'}
        record['assurance'] = copy.deepcopy(assurance)
        cat = model.catalog(image_records=[record])
        model.validate_schema(cat, 'catalog-v2.schema.json')
        index = model.discovery(cat)
        selected = next(item for item in index['resources'] if item['id'] == 'image/' + record['line_id'])
        self.assertEqual(selected['assurance'], assurance)
        self.assertEqual(selected['identity'], record['publication']['repository'] + '@' + record['publication']['digest'])
        self.assertEqual(selected['release_record'], f"release-records/{record['line_id']}/{record['version']}.json")
        selected['assurance']['receipt_url'] = 'https://example.test/local-change'
        self.assertEqual(record['assurance'], assurance)
        entry = next(item for item in cat['resources'] if item['id'] == selected['id'])
        self.assertEqual(entry['assurance'], assurance)

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
        # Exercise an unpublished profile independently of which releases the
        # live repository ledger has accepted since this test was authored.
        cat['resources'] = [item for item in cat['resources']
                            if item['id'] != 'image/uxor-dev/8.5-trixie']
        index = model.discovery(cat)
        self.assertLess(len(model.encoded(index)), len(model.encoded(cat)) // 2)
        self.assertEqual(len(index['resources']), len({item['id'] for item in index['resources']}))
        by_id = {item['id']: item for item in index['resources']}
        self.assertNotIn('image/uxor-dev/8.5-trixie', by_id)
        uxor = next(p for p in index['profiles'] if p['id'] == 'profile/uxor')
        self.assertEqual(uxor['catalog_status'], 'missing_required_releases')
        self.assertEqual(uxor['roles'][0]['alternatives'],
                         [{'id': 'image/uxor-dev/8.5-trixie', 'version': '1.0.0'}])
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

    def test_navigation_offers_a_profile_when_its_exact_release_is_accepted(self):
        cat = model.catalog()
        cat['resources'] = [item for item in cat['resources']
                            if item['id'] != 'image/uxor-dev/8.5-trixie']
        accepted = copy.deepcopy(next(item for item in cat['resources']
                                      if item['kind'] == 'image' and item['lifecycle'] == 'available'))
        accepted.update(id='image/uxor-dev/8.5-trixie', version='1.0.0',
                        documentation='docs/images/uxor-dev-8.5-trixie.md',
                        release_record='release-records/uxor-dev/8.5-trixie/1.0.0.json')
        cat['resources'].append(accepted)
        index = model.discovery(cat)
        offered = next(item for item in index['resources'] if item['id'] == accepted['id'])
        self.assertEqual(offered['identity'], accepted['identity'])
        self.assertEqual(offered['release_record'], accepted['release_record'])
        profile = next(item for item in index['profiles'] if item['id'] == 'profile/uxor')
        self.assertEqual(profile['catalog_status'], 'required_releases_available')
        self.assertNotIn('missing_roles', profile)

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

    @unittest.skipUnless(os.name == 'posix', 'Probe groups require POSIX')
    def test_probe_terminates_children_on_timeout_and_after_wrapper_returns(self):
        for wrapper_exits in (False, True):
            with self.subTest(wrapper_exits=wrapper_exits), tempfile.TemporaryDirectory() as folder:
                startup = Path(folder) / 'started'
                survived = Path(folder) / 'survived'
                child = ('import time; from pathlib import Path; '
                         f'Path({str(startup)!r}).write_text("running"); time.sleep(1); '
                         f'Path({str(survived)!r}).write_text("survived")')
                wrapper = ('import subprocess, sys, time; from pathlib import Path; '
                           f'p = subprocess.Popen([sys.executable, "-c", {child!r}], '
                           'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n'
                           f'while not Path({str(startup)!r}).exists(): time.sleep(0.01)\n'
                           + ('print("ready")' if wrapper_exits else 'time.sleep(30)'))
                started = time.monotonic()
                result = _probe([sys.executable, '-c', wrapper], 0.4)
                self.assertLess(time.monotonic() - started, 3)
                self.assertTrue(startup.is_file(), 'Reproduction must execute the child before the deadline')
                self.assertEqual(result['status'], 'passed' if wrapper_exits else 'timed_out')
                time.sleep(1.1)
                # Durable markers remain meaningful across PID namespaces,
                # unlike reading /proc or signalling a serialized child PID.
                self.assertFalse(survived.exists(), 'A probe descendant survived process-group cleanup')

    def test_non_posix_probe_reports_unsupported_without_starting_processes(self):
        with patch('xorder.inspect.os.name', 'nt'), patch('xorder.inspect.subprocess.Popen') as spawn:
            self.assertEqual(_probe(['docker', 'info'], 0.1), {'status': 'unsupported_platform'})
            spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
