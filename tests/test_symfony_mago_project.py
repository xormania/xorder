"""Independent project readiness controls for the Symfony/Mago composition."""
import importlib.util
import json
import shutil
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'images/php-mago-serena/symfony/project.py'
spec = importlib.util.spec_from_file_location('symfony_mago_project', MODULE)
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


def locked_tuple():
    return {
        'targets': {'php': '8.4', 'symfony': '8.2.0-BETA1'},
        'mate': {'version': '1.0.0-BETA1'},
        'mago': {
            'version': '1.58.2',
            'patched': {'source_rev': 'a' * 40},
            'sdk': {'source_rev': 'a' * 40, 'protocol': 'MANA 2.1'},
            'symfony_wiring': {'source_rev': 'b' * 40, 'composer_package': 'byte-kitsune/mago-symfony-wiring dev-poc-test'},
        },
        'native_mago': {'version': '1.59.0', 'binary': '/usr/local/bin/mago-native'},
    }


class SymfonyMagoProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.app = self.directory / 'app'
        self.image = self.directory / 'image.json'
        self.image.write_text(json.dumps({'mago_binary_sha256': 'c' * 64}))
        self.subject = project.Project(self.app, locked_tuple(), image_identity=self.image)

    def initialized(self):
        self.subject.initialize()
        (self.app / 'composer.lock').write_text('{}\n')
        (self.app / 'vendor/composer').mkdir(parents=True)
        packages = [
            {'name': 'carthage-software/mago', 'version': '1.58.2', 'source': {'reference': 'a' * 40}},
            {'name': 'byte-kitsune/mago-symfony-wiring', 'version': 'dev-poc-test', 'source': {'reference': 'b' * 40}},
            {'name': 'symfony/ai-mate', 'version': 'v1.0.0-BETA1'},
            {'name': 'symfony/ai-symfony-mate-extension', 'version': 'v1.0.0-BETA1'},
            {'name': 'symfony/ai-monolog-mate-extension', 'version': 'v1.0.0-BETA1'},
            {'name': 'symfony/framework-bundle', 'version': 'v8.2.0-BETA1'},
        ]
        (self.app / 'vendor/composer/installed.json').write_text(json.dumps({'packages': packages}))
        (self.app / 'vendor/autoload.php').write_text('<?php\n')
        (self.app / 'vendor/bin').mkdir()
        (self.app / 'vendor/bin/mate').touch()
        exporter = self.app / 'vendor/byte-kitsune/mago-symfony-wiring/bin/create-container-reference.php'
        exporter.parent.mkdir(parents=True)
        exporter.touch()
        return packages

    def prepared(self):
        self.initialized()
        def invoke(command, *, capture=False, **kwargs):
            if 'cache:clear' in command:
                path = self.app / 'var/cache/dev/App_KernelDevDebugContainer.xml'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('<container />')
            if any('create-container-reference.php' in arg for arg in command):
                return json.dumps({'environment': 'dev', 'scope': 'compiled_container_autowiring', 'definitions': {'logger': {}}}).encode()
            return b'{}'
        with patch.object(project, 'invoke', side_effect=invoke):
            self.subject.prepare()

    def test_new_project_uses_selected_beta_tuple_and_real_root_extension_config(self):
        self.subject.initialize()
        composer = json.loads((self.app / 'composer.json').read_text())
        self.assertEqual(composer['require']['symfony/framework-bundle'], '8.2.0-BETA1')
        self.assertEqual(composer['require-dev']['symfony/ai-mate'], '1.0.0-BETA1')
        self.assertEqual(composer['repositories'][0]['package']['source']['reference'], 'a' * 40)
        config = tomllib.loads((self.app / 'mago.toml').read_text())
        self.assertEqual(config['extension-hosts']['php']['working-directory'], '.')
        self.assertIn('.mago/container-reference.dev.json', config['language-server']['restart-on'])
        self.assertNotIn('vendor/xormania', (self.app / 'mago.toml').read_text())
        self.assertIn('inspection-dev', (self.app / 'mate/config.php').read_text())

    def test_existing_owner_project_is_preserved_on_initialization_conflict(self):
        self.app.mkdir()
        owner = self.app / 'composer.json'
        owner.write_text('{"name":"owner/project"}\n')
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.subject.initialize()
        self.assertEqual(owner.read_text(), '{"name":"owner/project"}\n')
        self.assertFalse((self.app / 'src').exists())

    def test_incompatible_sdk_and_executable_revisions_are_rejected(self):
        data = locked_tuple()
        data['mago']['sdk']['source_rev'] = 'd' * 40
        with self.assertRaisesRegex(ValueError, 'SDK'):
            project.Project(self.app, data, image_identity=self.image)

    def test_preparation_binds_source_metadata_reference_and_image(self):
        self.prepared()
        receipt = self.subject.ready()
        self.assertEqual(receipt['context'], 'inspection-dev')
        self.assertEqual(receipt['environment'], 'dev')
        self.assertEqual(receipt['compiled_metadata'], {'var/cache/dev/App_KernelDevDebugContainer.xml': project.sha(self.app / 'var/cache/dev/App_KernelDevDebugContainer.xml')})
        self.assertFalse(list((self.app / '.mago').glob('*types*.json')))

    def test_source_edits_make_compiled_analysis_stale(self):
        self.prepared()
        (self.app / 'src/Service/Greeting.php').write_text('<?php // changed\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.subject.ready()

    def test_modified_export_and_image_cannot_reuse_fresh_receipt(self):
        for kind in ('reference', 'image'):
            with self.subTest(kind=kind):
                if self.app.exists():
                    import shutil
                    shutil.rmtree(self.app)
                self.prepared()
                target = self.app / '.mago/container-reference.dev.json' if kind == 'reference' else self.image
                target.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'stale'):
                    self.subject.ready()

    def test_dev_environment_overrides_invalidate_compiled_metadata_when_added(self):
        self.prepared()
        for name in ('.env.dev', '.env.dev.local', '.env.local.php', '.env.dist'):
            with self.subTest(name=name):
                override = self.app / name
                override.write_text('APP_SECRET=updated\n')
                with self.assertRaisesRegex(ValueError, 'stale'):
                    self.subject.ready()
                override.unlink()
                self.subject.ready()

    def test_failed_preparation_removes_previous_success_marker(self):
        self.prepared()
        with patch.object(project, 'invoke', side_effect=RuntimeError('export broke')):
            with self.assertRaisesRegex(RuntimeError, 'export broke'):
                self.subject.prepare()
        with self.assertRaisesRegex(ValueError, 'prepare'):
            self.subject.ready()

    def test_wrong_installed_sdk_is_rejected_before_any_preparation_command(self):
        packages = self.initialized()
        packages[0]['source']['reference'] = 'f' * 40
        (self.app / 'vendor/composer/installed.json').write_text(json.dumps({'packages': packages}))
        with patch.object(project, 'invoke') as invoked:
            with self.assertRaisesRegex(ValueError, 'carthage-software/mago'):
                self.subject.prepare()
        invoked.assert_not_called()

    def test_native_checks_select_current_executable_and_disable_extension_workers(self):
        self.subject.initialize()
        with patch.object(project.subprocess, 'run') as run:
            run.return_value.returncode = 1
            code = self.subject.native(['lint'])
        self.assertEqual(code, 1)
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], '/usr/local/bin/mago-native')
        self.assertIn('--no-extensions', argv)
        self.assertEqual(argv[argv.index('--config') + 1], str(self.app / '.mago/native.toml'))
        config = tomllib.loads((self.app / '.mago/native.toml').read_text())
        self.assertNotIn('language-server', config)
        self.assertNotIn('extension-hosts', config)
        self.assertEqual(config['source']['paths'], ['src', 'tests'])

    def test_missing_graph_turns_native_success_into_tool_failure(self):
        self.prepared()
        with patch.object(project.subprocess, 'run') as run, patch.object(project.sys, 'stdout'), patch.object(project.sys, 'stderr'):
            run.return_value.returncode = 0
            run.return_value.stdout = b'{"issues": []}'
            run.return_value.stderr = b''
            self.assertEqual(self.subject.analyze([], [], wiring=False), 3)

    def test_native_checks_follow_current_root_source_and_later_quality_settings(self):
        self.subject.initialize()
        root = self.app / 'mago.toml'
        root.write_text(root.read_text().replace('paths = ["src", "tests"]', 'paths = ["src", "tests", "new-capability"]')
                        + '\n[linter.rules]\nno-debug-symbols = { enabled = true, level = "error" }\n')
        with patch.object(project.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.subject.native(['lint'])
        config = tomllib.loads((self.app / '.mago/native.toml').read_text())
        self.assertEqual(config['source']['paths'], ['src', 'tests', 'new-capability'])
        self.assertTrue(config['linter']['rules']['no-debug-symbols']['enabled'])
        self.assertNotIn('language-server', config)
        self.assertNotIn('extension-hosts', config)

    def test_completed_wiring_preserves_native_findings_exit(self):
        self.prepared()
        def analyze(command, **kwargs):
            graph = Path(kwargs['env']['XORDER_MAGO_GRAPH'])
            graph.write_text(json.dumps({'observer': 'xorder/symfony-observer', 'wiring_enabled': True, 'symbols': {r'App\Service\Greeting': []}}))
            response = project.subprocess.CompletedProcess(command, 1)
            note = 'extension-attestation: ' + json.dumps({'complete': True})
            response.stdout = json.dumps({'issues': [{'code': 'byte-kitsune/symfony-wiring/analysis-attestation', 'notes': [note]}]}).encode()
            response.stderr = b''
            return response
        with patch.object(project.subprocess, 'run', side_effect=analyze), patch.object(project.sys, 'stdout'), patch.object(project.sys, 'stderr'):
            self.assertEqual(self.subject.analyze([], [], wiring=True), 1)

    def test_new_project_development_secret_is_private_and_unique(self):
        self.subject.initialize()
        secret = self.app / '.env.local'
        self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('APP_SECRET', (self.app / '.env').read_text())
        other = project.Project(self.directory / 'other', locked_tuple(), image_identity=self.image)
        other.initialize()
        self.assertNotEqual(secret.read_bytes(), (other.root / '.env.local').read_bytes())

    def test_runtime_bootstraps_preserve_production_and_explicit_debug_false(self):
        php = shutil.which('php')
        if php is None:
            self.skipTest('PHP is needed to execute the independent runtime bootstrap contract')
        self.subject.initialize()
        (self.app / 'vendor').mkdir()
        (self.app / 'vendor/autoload_runtime.php').write_text('''<?php
namespace App { final class Kernel { public function __construct(public string $environment, public bool $debug) {} } }
namespace Symfony\\Bundle\\FrameworkBundle\\Console { final class Application { public function __construct(public \\App\\Kernel $kernel) {} } }
''')
        for target in ('bin/console', 'public/index.php'):
            for environment, debug in [('prod', False), ('dev', False), ('dev', True)]:
                with self.subTest(target=target, environment=environment, debug=debug):
                    script = ('$factory = require $argv[1]; '
                        '$result = $factory(json_decode($argv[2], true)); '
                        '$kernel = $result instanceof \\App\\Kernel ? $result : $result->kernel; '
                        'echo json_encode([$kernel->environment, $kernel->debug]);')
                    result = project.subprocess.run([php, '-r', script, str(self.app / target),
                        json.dumps({'APP_ENV': environment, 'APP_DEBUG': debug})], capture_output=True, text=True, check=True)
                    self.assertEqual(json.loads(result.stdout.splitlines()[-1]), [environment, debug])


if __name__ == '__main__':
    unittest.main()
