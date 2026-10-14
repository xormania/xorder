"""A publication retry resumes its first durable inputs rather than allocating images."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import encoded
from publication_attempt import reserve, validate_attempt


class PublicationAttemptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'images/demo').mkdir(parents=True)
        (self.root / '.dockerignore').write_text('.git\n')
        (self.root / 'images/demo/Dockerfile').write_text(
            'ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\nARG SYMFONY_URL\nARG SYMFONY_SHA256\n'
            'COPY images/demo/launch.sh /launch\nARG SOURCE_COMMIT\nARG IMAGE_VERSION\n'
            'LABEL source=${SOURCE_COMMIT} version=${IMAGE_VERSION}\n')
        self.launch = self.root / 'images/demo/launch.sh'
        self.launch.write_text('echo ready\n')
        self.tools = {'symfony': {'url': 'https://example.test/cli', 'sha256': 'b' * 64, 'version': '1.0'}}
        self.write_tools()
        self.definition = {'family': 'demo', 'line': '1-trixie', 'line_id': 'demo/1-trixie',
                           'revision': '1.0.0', 'platforms': ['linux/amd64'],
                           'base': {'tag': 'example.test/demo:1', 'digest': 'sha256:' + 'a' * 64},
                           'purpose': 'Original intent'}
        self.source = 'c' * 40
        self.releases = []
        self.receipt = None
        self.calls = []

    def write_tools(self):
        (self.root / 'images/tools.json').write_text(json.dumps(self.tools))

    def gh(self, *args):
        self.assertEqual(args, ('api', '--paginate', '--slurp', 'repos/xormania/xorder/releases'))
        return json.dumps([self.releases])

    def run_command(self, *args):
        self.calls.append(args)
        self.assertEqual(args[:2], ('gh', 'release'))
        action = args[2]
        if action == 'create':
            self.assertFalse(self.releases)
            self.releases.append({'tag_name': args[3], 'target_commitish': args[args.index('--target') + 1], 'assets': []})
        elif action == 'upload':
            self.receipt = json.loads(Path(args[4]).read_text())
            self.releases[0]['assets'].append({'name': 'candidate.json'})
        elif action == 'download':
            folder = Path(args[args.index('--dir') + 1])
            (folder / 'candidate.json').write_text(encoded(self.receipt))
        else:
            self.fail(f'Unexpected mutation in a reservation: {action}')

    def reserve(self, definition=None, source=None, fingerprint=None):
        return reserve(definition or self.definition, source or self.source, None, self.root / 'out',
                       root=self.root, tools=self.tools, fingerprint=fingerprint or 'd' * 64,
                       gh=self.gh, run=self.run_command, encoded=encoded,
                       now=lambda: '2026-10-14T08:00:00Z', repository='xormania/xorder')

    def test_metadata_and_new_source_resume_the_original_receipt_without_allocating(self):
        first = self.reserve()
        original = copy.deepcopy(first)
        changed = copy.deepcopy(self.definition)
        changed.update(purpose='Clarified intent', changes=['Documentation only'], migration='New instructions')
        self.tools['symfony']['version'] = 'Descriptive version annotation'
        self.write_tools()
        resumed = self.reserve(changed, source='e' * 40, fingerprint='f' * 64)
        self.assertEqual(resumed, original)
        self.assertEqual(resumed['source_commit'], self.source)
        self.assertEqual(resumed['definition']['purpose'], 'Original intent')
        self.assertEqual(resumed['tools']['symfony']['version'], '1.0')
        self.assertEqual(resumed['input_fingerprint'], 'd' * 64)
        self.assertEqual([call[2] for call in self.calls], ['create', 'upload', 'download'])
        self.assertIn(first['build_key'], first['candidate'])
        self.assertNotIn(self.source, first['candidate'])

    def test_same_digest_with_a_new_informational_base_tag_resumes(self):
        first = self.reserve()
        changed = copy.deepcopy(self.definition)
        changed['base']['tag'] = 'example.test/demo:stable'
        resumed = self.reserve(changed, source='e' * 40)
        self.assertEqual(resumed, first)
        self.assertEqual(resumed['resolved_base'], 'example.test/demo:1@sha256:' + 'a' * 64)

    def test_copied_runtime_change_cannot_reuse_the_reserved_revision(self):
        self.reserve()
        original = copy.deepcopy(self.receipt)
        self.launch.write_text('echo changed-runtime\n')
        with self.assertRaisesRegex(ValueError, 'requested build inputs'):
            self.reserve(source='e' * 40)
        self.assertEqual(self.receipt, original)
        self.assertEqual([call[2] for call in self.calls], ['create', 'upload', 'download'])

    def test_consumed_pin_change_cannot_reuse_the_reserved_revision(self):
        self.reserve()
        self.tools['symfony']['sha256'] = 'e' * 64
        self.write_tools()
        with self.assertRaisesRegex(ValueError, 'requested build inputs'):
            self.reserve(source='e' * 40)
        self.assertEqual([call[2] for call in self.calls], ['create', 'upload', 'download'])

    def test_candidate_reference_and_release_target_cannot_drift(self):
        original = self.reserve()
        corrupt = dict(original, candidate=original['candidate'] + '-different')
        with self.assertRaisesRegex(ValueError, 'reserved build inputs'):
            validate_attempt(corrupt, self.definition, None, self.root)
        self.releases[0]['target_commitish'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'Release target'):
            self.reserve(source='e' * 40)

    def test_partial_receipt_reservation_requires_recovery_before_more_mutations(self):
        self.reserve()
        self.releases[0]['assets'] = []
        calls = copy.deepcopy(self.calls)
        with self.assertRaisesRegex(ValueError, 'recover it'):
            self.reserve(source='e' * 40)
        self.assertEqual(self.calls, calls)

    def test_invalid_source_is_refused_before_any_external_lookup(self):
        for source in ('local', 'a' * 39, 'a' * 41):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'exact source commit'):
                self.reserve(source=source)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
