"""Owned browser rendering assertions and offline public-verifier dispatch."""
import base64
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]


def pixel_png(rgb, alpha=255):
    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data)))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes([0, *rgb, alpha]))) + chunk(b'IEND', b''))


class OwnedBrowserTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the rendering assertion canary')
    def test_rendered_pixel_assertion_accepts_color_and_rejects_blank_or_transparent_samples(self):
        script = ("const assert = require('node:assert/strict');"
                  "const pixel = require(process.argv[1]);"
                  "assert.deepEqual(pixel(Buffer.from(process.argv[2], 'base64')), [12, 34, 56]);")
        for data, passed in ((pixel_png((12, 34, 56)), True), (pixel_png((255, 255, 255)), False),
                             (pixel_png((12, 34, 56), 0), False), (b'not a PNG', False)):
            with self.subTest(passed=passed):
                result = subprocess.run(['node', '-e', script,
                    str(ROOT / 'tests/fixtures/playwright/capabilities/pixel.cjs'),
                    base64.b64encode(data).decode()], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, passed, result.stderr)

    def test_public_browser_recipe_runs_owned_fixture_offline_without_application_or_git(self):
        for exit_code in (0, 37):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as temporary:
                area = Path(temporary)
                repository, binaries = area / 'repo', area / 'bin'
                (repository / 'scripts').mkdir(parents=True)
                (repository / 'tests/fixtures/playwright').mkdir(parents=True)
                binaries.mkdir()
                shutil.copy(ROOT / 'scripts/verify-image.sh', repository / 'scripts')
                # Any accidental legacy integration call must fail this canary.
                (repository / 'tests/fixtures/playwright/parity.sh').write_text('exit 99\n')
                git = binaries / 'git'
                git.write_text('#!/bin/sh\nexit 98\n')
                git.chmod(0o755)
                docker = binaries / 'docker'
                docker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
assert args[:2] == ['run', '--rm']
assert '--network=none' in args
assert args[-3:] == ['candidate:test', 'node', '/proof/check.cjs']
assert any(a.endswith('/tests/fixtures/playwright/capabilities:/proof:ro') for a in args)
for arg in args:
    if arg.endswith(':/workspace'):
        for name in ('chromium', 'firefox', 'webkit'):
            (pathlib.Path(arg.removesuffix(':/workspace')) / (name + '.png')).write_bytes(b'proof')
print(json.dumps({'status': 'passed'}))
raise SystemExit(int(os.environ['OWNED_FIXTURE_EXIT']))
''')
                docker.chmod(0o755)
                env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                           OWNED_FIXTURE_EXIT=str(exit_code))
                env.pop('CA_CERTIFICATE', None)
                result = subprocess.run(['bash', str(repository / 'scripts/verify-image.sh'),
                    'playwright-browser/1.58-trixie', 'candidate:test'],
                    env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                proof = repository / 'out/playwright/acceptance.json'
                self.assertEqual(json.loads(proof.read_text()), {'status': 'passed'})


if __name__ == '__main__':
    unittest.main()
