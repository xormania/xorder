import io
import os
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import github_http


class GitHubHttpTests(unittest.TestCase):
    def test_non_http_schemes_are_rejected_before_opening(self):
        for url in ('file:///etc/passwd', 'data:application/json,%7B%7D',
                    'ftp://example.test/data', '/local/response.json'):
            with self.subTest(url=url), \
                    patch.object(github_http.urllib.request, 'urlopen') as open_url, \
                    self.assertRaisesRegex(ValueError, 'HTTP or HTTPS'):
                github_http.fetch_json(url)
            open_url.assert_not_called()

    def test_token_is_scoped_to_https_api_and_is_not_forwarded_on_redirect(self):
        api = 'https://api.github.com/repos/xormania/uxor/commits/main'
        urls = (api, 'https://raw.githubusercontent.com/xormania/uxor/main/package.json',
                'https://api.github.com.example.test/data', 'http://api.github.com/data',
                'https://api.github.com:444/data', 'https://user@api.github.com/data')
        for url in urls:
            with self.subTest(url=url), patch.dict(os.environ, {'GH_TOKEN': 'fixture-token'  # nosec B105 # synthetic credential test canary
                    }, clear=True), \
                    patch.object(github_http.urllib.request, 'urlopen', return_value=io.BytesIO(b'{}')) as open_url:
                self.assertEqual(github_http.fetch_json(url), {})
                request = open_url.call_args.args[0]
                self.assertEqual(request.get_header('Authorization'), 'Bearer fixture-token' if url == api else None)
                redirected = urllib.request.HTTPRedirectHandler().redirect_request(
                    request, None, 302, 'Found', {}, 'https://example.test/asset')
                self.assertIsNone(redirected.get_header('Authorization'))

    def test_workflow_token_fallback_and_anonymous_reads(self):
        for environment, expected in (({'GITHUB_TOKEN': 'fallback'}, 'Bearer fallback'),  # nosec B105 # synthetic credential test canary
                                      ({'GITHUB_TOKEN': 'fallback', 'GH_TOKEN': 'preferred'}, 'Bearer preferred'),  # nosec B105 # synthetic credential test canary
                                      ({}, None)):
            with patch.dict(os.environ, environment, clear=True), \
                    patch.object(github_http.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"sha":"pin"}')) as open_url:
                self.assertEqual(github_http.fetch_json('https://api.github.com/data'), {'sha': 'pin'})
                self.assertEqual(open_url.call_args.args[0].get_header('Authorization'), expected)

    def test_transient_rate_limits_retry_with_a_bounded_request_budget(self):
        url = 'https://api.github.com/data'
        errors = [urllib.error.HTTPError(url, 403, 'limited', {'X-RateLimit-Remaining': '0'}, io.BytesIO()),
                  urllib.error.HTTPError(url, 503, 'unavailable', {'Retry-After': '3'}, io.BytesIO())]
        with patch.object(github_http.urllib.request, 'urlopen', side_effect=errors + [io.BytesIO(b'{}')]) as open_url, \
                patch.object(github_http.time, 'sleep') as sleep:
            self.assertEqual(github_http.fetch_json(url), {})
            self.assertEqual(open_url.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 3])

    def test_permissions_persistent_limits_and_long_retry_windows_remain_failures(self):
        url = 'https://api.github.com/data'
        for code, headers, attempts in ((403, {}, 1), (403, {'X-RateLimit-Remaining': '0'}, 3),
                                       (429, {'Retry-After': '120'}, 1)):
            errors = [urllib.error.HTTPError(url, code, 'failure', headers, io.BytesIO()) for _ in range(attempts)]
            with self.subTest(code=code, headers=headers), \
                    patch.object(github_http.urllib.request, 'urlopen', side_effect=errors) as open_url, \
                    patch.object(github_http.time, 'sleep') as sleep, \
                    self.assertRaises(urllib.error.HTTPError):
                github_http.fetch_json(url)
            self.assertEqual(open_url.call_count, attempts)
            self.assertEqual(sleep.call_count, attempts - 1)


if __name__ == '__main__':
    unittest.main()
