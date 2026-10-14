import argparse
import importlib.util
import json
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load('serena_runner', 'examples/serena/run.py')
launcher = load('serena_launcher', 'images/php-serena/launch.py')
acceptance = load('serena_acceptance', 'tests/fixtures/serena/check.py')


class SerenaTests(unittest.TestCase):
    def test_textual_repl_error_cannot_pass_as_successful_mcp(self):
        client = acceptance.Client.__new__(acceptance.Client)
        client.session = 'test-session'
        client.call = lambda *args: {'content': [{'type': 'text', 'text': 'RuntimeError: failed\n  line 1: answer = 42'}]}
        with self.assertRaisesRegex(AssertionError, 'RuntimeError'):
            client.repl('answer = 42')
        self.assertIn('RuntimeError', client.repl('answer = 42', expected_error=True))

    def test_runner_keeps_sibling_sources_visible_and_enforces_readonly(self):
        with tempfile.TemporaryDirectory(prefix='serena checkout ') as directory:
            root = Path(directory)
            (root / 'demo').mkdir()
            args = argparse.Namespace(workspace=root, project='demo', image='local:proof', read_only=True)
            command = runner.command(args)
            self.assertIn(f'type=bind,src={root},dst=/workspace,readonly', command)
            self.assertEqual(command[-3:], ['--project', '/workspace/demo', '--read-only'])
            self.assertIn('--network=none', command)
            self.assertIn('--pull=never', command)
            self.assertNotIn('--tty', command)
            args.project = '..'
            with self.assertRaisesRegex(ValueError, 'inside'):
                runner.command(args)

    def test_project_configuration_is_preserved_and_conflicts_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.serena').mkdir()
            source = root / '.serena/project.yml'
            source.write_text(json.dumps({'project_name': 'consumer', 'ignored_paths': ['generated']}))
            original = source.read_bytes()
            config = launcher.project_config(root, True, json.loads)
            self.assertEqual(config['language_servers'], ['php_phpactor'])
            self.assertEqual(config['ignored_paths'], ['generated'])
            self.assertTrue(config['read_only'])
            self.assertEqual(source.read_bytes(), original)
            (root / '.serena/project.local.yml').write_text('{"language_servers": ["php"]}')
            with self.assertRaisesRegex(ValueError, 'php_phpactor'):
                launcher.project_config(root, False, json.loads)

    def test_runner_defaults_to_readonly_and_requires_explicit_write(self):
        with tempfile.TemporaryDirectory() as directory:
            for flags, readonly in (([], True), (['--write'], False)):
                with self.subTest(flags=flags), patch.object(sys, 'argv',
                        ['run.py', directory, '--image', 'local:proof', *flags]), \
                        patch.object(runner.os, 'execvp') as execute:
                    runner.main()
                    argv = execute.call_args.args[1]
                    self.assertEqual(argv[-1], '--read-only' if readonly else '--write')
                    self.assertEqual(any(value.endswith('dst=/workspace,readonly') for value in argv), readonly)

    def test_mounted_configuration_cannot_override_the_prepared_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.serena').mkdir()
            for name in ('project.yml', 'project.local.yml'):
                source = root / '.serena' / name
                for option, value in (('phpactor_version', 'different-version'), ('ls_path', '/workspace/replacement')):
                    with self.subTest(name=name, option=option):
                        source.write_text(json.dumps({'ls_specific_settings': {'php_phpactor': {option: value}}}))
                        with self.assertRaisesRegex(ValueError, 'prepared PHPactor'):
                            launcher.project_config(root, False, json.loads)
                source.unlink()

    def test_mounted_configuration_does_not_authorize_automatic_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.serena').mkdir()
            source = root / '.serena/project.yml'
            source.write_text(json.dumps({'project_name': 'consumer', 'activation_command': 'touch /workspace/canary',
                                         'ls_specific_settings': {'php_phpactor': {'ignore_vendor': False}}}))
            original = source.read_bytes()
            config = launcher.project_config(root, False, json.loads)
            self.assertEqual(config['project_name'], 'consumer')
            self.assertNotIn('activation_command', config)
            self.assertNotIn('ls_specific_settings', config)
            self.assertEqual(source.read_bytes(), original)

    def test_serena_inputs_select_only_the_php85_parent_tree(self):
        from library import affected, definitions
        for path in ('images/php-serena/Dockerfile', 'images/php-serena/requirements-build.txt',
                     'images/php-serena/security.patch', 'images/php-serena/security-uv.lock',
                     'examples/serena/run.py', 'tests/fixtures/serena/check.py',
                     'tests/fixtures/serena/consumer.json'):
            with self.subTest(path=path):
                self.assertEqual(affected([path], definitions()), ['php-dev/8.5-trixie'])

    def test_security_closure_pins_fixed_versions_with_artifact_hashes(self):
        lock = tomllib.loads((ROOT / 'images/php-serena/security-uv.lock').read_text())
        packages = {item['name']: item for item in lock['package']}
        for name, expected in (('anyio', '4.14.2'), ('pyjwt', '2.14.0')):
            with self.subTest(package=name):
                package = packages[name]
                self.assertEqual(package['version'], expected)
                self.assertTrue(package['wheels'])
                for artifact in [package['sdist'], *package['wheels']]:
                    self.assertRegex(artifact['hash'], r'^sha256:[a-f0-9]{64}$')
                    self.assertTrue(artifact['url'].startswith('https://files.pythonhosted.org/'))


if __name__ == '__main__':
    unittest.main()
