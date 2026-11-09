#!/usr/bin/env python3
"""Create and prepare the selected Symfony/Mago/Serena development composition."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid

HERE = Path(__file__).resolve().parent
TOOLCHAIN = HERE.parent / 'serena/toolchain.lock.json'
IDENTITY = Path('/opt/xorder/image-identity.json')
CONTEXT = 'inspection-dev'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def invoke(command, *, cwd, capture=False, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=True, timeout=300)
    if not capture:
        sys.stderr.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.stdout


def package_repository(name, version, source, autoload, requirements):
    url = 'https://github.com/' + ('carthage-software/mago' if name == 'carthage-software/mago' else 'Byte-Kitsune/mago-symfony-wiring')
    return {'type': 'package', 'package': {
        'name': name, 'version': version, 'type': 'library', 'license': ['MIT', 'Apache-2.0'] if name == 'carthage-software/mago' else 'MIT',
        'require': requirements, 'autoload': autoload,
        'source': {'type': 'git', 'url': url + '.git', 'reference': source},
        'dist': {'type': 'zip', 'url': url.replace('github.com/', 'api.github.com/repos/') + '/zipball/' + source, 'reference': source},
    }}


class Project:
    def __init__(self, root, toolchain, *, image_identity=IDENTITY):
        self.root = Path(root).resolve()
        self.lock = toolchain
        self.image_identity = Path(image_identity)
        self.php = toolchain['targets']['php']
        self.symfony = toolchain['targets']['symfony']
        self.mate = toolchain['mate']['version']
        self.mago = toolchain['mago']
        if self.mago['patched']['source_rev'] != self.mago['sdk']['source_rev']:
            raise ValueError('Mago executable and Composer SDK must use the same source revision')
        self.state = self.root / '.mago'
        self.receipt = self.state / 'preparation.json'

    def composer(self):
        version = self.mago['version']
        wiring = self.mago['symfony_wiring']
        wire_version = wiring['composer_package'].split(' ', 1)[1]
        runtime = {name: self.symfony for name in ('symfony/framework-bundle', 'symfony/console', 'symfony/runtime', 'symfony/dotenv', 'symfony/yaml', 'symfony/twig-bundle')}
        runtime.update({'php': '>=' + self.php, 'symfony/monolog-bundle': '^4'})
        development = {name: self.mate for name in ('symfony/ai-mate', 'symfony/ai-symfony-mate-extension', 'symfony/ai-monolog-mate-extension')}
        development.update({'symfony/web-profiler-bundle': self.symfony, 'carthage-software/mago': version, 'byte-kitsune/mago-symfony-wiring': wire_version})
        return {
            'name': 'app/symfony-project', 'type': 'project', 'license': 'MIT',
            'minimum-stability': 'dev', 'prefer-stable': True,
            'require': runtime, 'require-dev': development,
            'repositories': [
                package_repository('carthage-software/mago', version, self.mago['sdk']['source_rev'],
                    {'psr-4': {'Mago\\': 'composer/src/'}, 'files': ['composer/src/functions.php', 'composer/src/internal.php']},
                    {'php': '>=' + self.php, 'revolt/event-loop': '^1.0.9'}),
                package_repository('byte-kitsune/mago-symfony-wiring', wire_version, wiring['source_rev'],
                    {'psr-4': {'ByteKitsune\\MagoSymfonyWiring\\': 'src/'}},
                    {'php': '^8.2', 'carthage-software/mago': '^1.50', 'nikic/php-parser': '^5.9', 'symfony/yaml': '^7.4 || ^8.0'}),
            ],
            'config': {'allow-plugins': {'symfony/ai-mate-composer-plugin': True, 'symfony/runtime': True}, 'sort-packages': True},
            'autoload': {'psr-4': {'App\\': 'src/'}},
            'autoload-dev': {'psr-4': {'Mate\\': 'mate/src/'}},
            'extra': {'symfony': {'require': self.symfony}, 'ai-mate': {'extension': False, 'scan-dirs': ['mate/src'], 'includes': ['mate/config.php']}},
        }

    def initialize(self):
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError('Project directory exists and is not empty; initialize a new directory')
        self.root.mkdir(parents=True, exist_ok=True)
        for source in (HERE / 'templates').rglob('*'):
            if source.is_file():
                destination = self.root / source.relative_to(HERE / 'templates')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.read_text().replace('__PHP_VERSION__', self.php))
                if source.name == 'console':
                    destination.chmod(0o755)
        # Current native Mago removed the LSP config schema. Generate its
        # config from the same source settings, without server/worker sections.
        self.native_configuration()
        dump(self.root / 'composer.json', self.composer())
        (self.root / '.env').write_text('APP_ENV=dev\nAPP_DEBUG=1\n')
        secret = self.root / '.env.local'
        secret.write_text('APP_SECRET=' + secrets.token_hex(32) + '\n')
        secret.chmod(0o600)
        (self.root / '.gitignore').write_text('/vendor/\n/var/\n/.env.local\n/.mago/preparation.json\n/.mago/container-reference.dev.json\n/.mago/evidence/\n')
        (self.root / 'tests').mkdir(exist_ok=True)
        (self.root / 'mate/src').mkdir(exist_ok=True)
        dump(self.state / 'toolchain.json', self.lock)
        return {'project': str(self.root), 'next': 'composer install; library-symfony-mago prepare'}

    def dependencies(self):
        path = self.root / 'vendor/composer/installed.json'
        if not (self.root / 'composer.lock').is_file() or not path.is_file():
            raise ValueError('Install the project Composer dependencies and lock before prepare')
        data = json.loads(path.read_text())
        packages = {row['name']: row for row in data['packages']}
        for name, source in [('carthage-software/mago', self.mago['sdk']['source_rev']), ('byte-kitsune/mago-symfony-wiring', self.mago['symfony_wiring']['source_rev'])]:
            if packages.get(name, {}).get('source', {}).get('reference') != source:
                raise ValueError('Installed ' + name + ' does not match the selected tuple')
        for name, expected in [('symfony/framework-bundle', self.symfony), *[(name, self.mate) for name in ('symfony/ai-mate', 'symfony/ai-symfony-mate-extension', 'symfony/ai-monolog-mate-extension')]]:
            if packages.get(name, {}).get('version', '').removeprefix('v') != expected.removeprefix('v'):
                raise ValueError('Installed ' + name + ' does not match the selected tuple')

    def source_state(self):
        paths = {self.root / name for name in ('composer.json', 'composer.lock', 'mago.toml',
            '.env', '.env.local', '.env.dev', '.env.dev.local', '.env.local.php', '.env.dist',
            'bin/console', 'public/index.php',
            'vendor/composer/installed.json', '.mago/extensions.php', '.mago/toolchain.json')}
        for name in ('src', 'tests', 'config', 'mate'):
            paths.update(path for path in (self.root / name).rglob('*') if path.is_file())
        return {str(path.relative_to(self.root)): sha(path) for path in sorted(paths) if path.is_file()}

    def compiled_metadata(self):
        paths = list((self.root / 'var/cache/dev').glob('*DebugContainer.xml'))
        if len(paths) != 1:
            raise ValueError('Expected one compiled dev container; run prepare')
        return {str(path.relative_to(self.root)): sha(path) for path in paths}

    def prepare(self):
        self.state.mkdir(exist_ok=True)
        self.receipt.unlink(missing_ok=True)
        self.dependencies()
        environment = {**os.environ, 'APP_ENV': 'dev', 'APP_DEBUG': '1'}
        # The image stores no application cache, profiler data or service facts.
        evidence = self.state / 'evidence' / ('prepare-' + uuid.uuid4().hex)
        evidence.mkdir(parents=True)
        for name in ('var/cache/dev/profiler', 'var/log'):
            path = self.root / name
            if path.is_dir():
                shutil.copytree(path, evidence / 'runtime-before-refresh' / name)
        for command in [
            ['php', 'vendor/bin/mate', 'init', '--no-interaction'],
            ['composer', 'dump-autoload', '--no-plugins', '--no-scripts', '--no-interaction'],
            ['php', 'vendor/bin/mate', 'discover', '--no-interaction'],
            ['php', 'bin/console', 'cache:clear', '--env=dev', '--no-interaction'],
        ]:
            invoke(command, cwd=self.root, env=environment)
        with tempfile.TemporaryDirectory(prefix='xorder-wiring-') as temporary:
            private = Path(temporary)
            for name, extra in [('types', ['--types']), ('services', [])]:
                raw = invoke(['php', 'bin/console', 'debug:container', '--env=dev', '--format=json', '--no-interaction', *extra], cwd=self.root, env=environment, capture=True)
                destination = private / (name + '.json')
                destination.write_bytes(raw)
                destination.chmod(0o600)
            result = invoke(['php', 'vendor/byte-kitsune/mago-symfony-wiring/bin/create-container-reference.php', '--types=' + str(private / 'types.json'), '--services=' + str(private / 'services.json'), '--autoload=' + str(self.root / 'vendor/autoload.php')], cwd=self.root, env=environment, capture=True)
        reference = json.loads(result)
        if reference.get('environment') != 'dev' or reference.get('scope') != 'compiled_container_autowiring' or not reference.get('definitions'):
            raise ValueError('Wiring exporter did not return a populated compiled dev reference')
        target = self.state / 'container-reference.dev.json'
        target.write_bytes(result)
        record = {'schema': 1, 'environment': 'dev', 'context': CONTEXT, 'project': str(self.root),
            'source': self.source_state(), 'compiled_metadata': self.compiled_metadata(),
            'reference_sha256': sha(target), 'image_identity_sha256': sha(self.image_identity)}
        dump(self.receipt, record)
        return record

    def ready(self):
        if not self.receipt.is_file():
            raise ValueError('Project metadata is unprepared; run prepare')
        record = json.loads(self.receipt.read_text())
        if record.get('project') != str(self.root) or record.get('source') != self.source_state() or record.get('compiled_metadata') != self.compiled_metadata() or record.get('reference_sha256') != sha(self.state / 'container-reference.dev.json') or record.get('image_identity_sha256') != sha(self.image_identity):
            raise ValueError('Compiled Symfony metadata is stale; run prepare and restart the language server')
        self.dependencies()
        return record

    def native_configuration(self):
        text = (self.root / 'mago.toml').read_text()
        parsed = tomllib.loads(text)
        excluded = {'language-server', 'extension-hosts'}
        lines, skip = [], False
        for line in text.splitlines(keepends=True):
            if re.fullmatch(r'\s*\[.*\]\s*(?:#.*)?', line.rstrip('\n')):
                try:
                    header = tomllib.loads(line)
                except tomllib.TOMLDecodeError:
                    header = {}
                if header:
                    skip = next(iter(header)) in excluded
            if not skip:
                lines.append(line)
        projected = ''.join(lines)
        if tomllib.loads(projected) != {key: value for key, value in parsed.items() if key not in excluded}:
            raise ValueError('Native Mago configuration could not preserve the supported root settings')
        destination = self.state / 'native.toml'
        if not destination.is_file() or destination.read_text() != projected:
            destination.write_text(projected)
        return destination

    def native(self, arguments):
        if not arguments:
            raise ValueError('Supply native Mago arguments, such as analyze or lint')
        binary = self.lock.get('native_mago', {}).get('binary', '/usr/local/bin/mago')
        return subprocess.run([binary, '--workspace', str(self.root), '--config', str(self.native_configuration()), '--no-extensions', *arguments], cwd=self.root).returncode

    def analyze(self, arguments, symbols, wiring=True):
        self.ready()
        if not symbols:
            symbols = [r'App\Service\Greeting']
        if len(symbols) > 8 or len(set(symbols)) != len(symbols) or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\\[A-Za-z_][A-Za-z0-9_]*)*', name) for name in symbols):
            raise ValueError('Supply one to eight distinct fully qualified class names')
        if any(arg.split('=', 1)[0] in ('--reporting-format', '--workspace', '--config', '--no-extensions') for arg in arguments):
            raise ValueError('Enriched analysis owns workspace, extension selection and JSON reporting')
        evidence = self.state / 'evidence' / ('analyze-' + uuid.uuid4().hex)
        evidence.mkdir(parents=True)
        environment = {**os.environ, 'XORDER_MAGO_GRAPH': str(evidence / 'graph.json'), 'XORDER_MAGO_SYMBOLS': json.dumps(symbols), 'XORDER_MAGO_WIRING': '1' if wiring else '0'}
        result = subprocess.run(['/usr/local/bin/mago', '--workspace', str(self.root), '--colors', 'never', 'analyze', '--reporting-format', 'json', *arguments], cwd=self.root, env=environment, capture_output=True)
        (evidence / 'stdout').write_bytes(result.stdout)
        (evidence / 'stderr').write_bytes(result.stderr)
        code = result.returncode
        status = 'tool_failure'
        if code in (0, 1):
            try:
                graph = json.loads((evidence / 'graph.json').read_text())
                report = json.loads(result.stdout)
                attestations = [issue for issue in report['issues'] if issue['code'] == 'byte-kitsune/symfony-wiring/analysis-attestation']
                complete = all(json.loads(next(note for note in issue['notes'] if note.startswith('extension-attestation: ')).split(': ', 1)[1])['complete'] is True for issue in attestations)
                if graph['observer'] == 'xorder/symfony-observer' and graph['wiring_enabled'] is wiring and set(graph['symbols']) == set(symbols) and len(attestations) == int(wiring) and complete:
                    status = 'findings' if code else 'clean'
            except (OSError, ValueError, KeyError, StopIteration, TypeError):
                status = 'tool_failure'
        dump(evidence / 'result.json', {'status': status, 'native_exit': result.returncode, 'wiring_enabled': wiring})
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        print('Mago evidence: ' + str(evidence), file=sys.stderr)
        return code if status != 'tool_failure' else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='library-symfony-mago 1.0.0')
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--toolchain', type=Path, default=TOOLCHAIN)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'prepare', 'check'):
        commands.add_parser(name)
    native = commands.add_parser('native')
    native.add_argument('arguments', nargs=argparse.REMAINDER)
    analyze = commands.add_parser('analyze')
    analyze.add_argument('--symbol', action='append', default=[])
    analyze.add_argument('--extension-off', action='store_true')
    analyze.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    subject = Project(args.project, json.loads(args.toolchain.read_text()))
    if args.command == 'native':
        return subject.native(args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments)
    if args.command == 'analyze':
        return subject.analyze(args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments, args.symbol, not args.extension_off)
    result = {'init': subject.initialize, 'prepare': subject.prepare, 'check': subject.ready}[args.command]()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print('Symfony/Mago: ' + str(error), file=sys.stderr)
        sys.exit(3)
