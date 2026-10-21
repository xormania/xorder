"""Authentication belongs to the initial API/registry request, never a redirect."""
import base64
import io
import os
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog_checks
import registry


class Response(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}


class AuthenticatedRedirectTests(unittest.TestCase):
    def assert_redirect_drops_authentication(self, request, expected):
        self.assertEqual(request.get_header("Authorization"), expected)
        # Exercise urllib's real redirect request construction, not a mock of
        # its header policy. No request is sent to either origin.
        redirected = urllib.request.HTTPRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, "https://different-origin.example/target")
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_catalog_api_authenticates_initial_request_but_not_redirects(self):
        for environment, expected in (({"GH_TOKEN": "synthetic-api-token"}, "Bearer synthetic-api-token"),  # nosec B105 # synthetic credential test canary
                                      ({}, None)):
            with self.subTest(authenticated=bool(expected)), patch.dict(os.environ, environment, clear=True), \
                    patch.object(catalog_checks.urllib.request, "urlopen", return_value=Response(b'{"id":1}')) as open_url:
                self.assertEqual(catalog_checks.github_json("example/repository", "releases"), {"id": 1})
                request = open_url.call_args.args[0]
                self.assertEqual(request.full_url, "https://api.github.com/repos/example/repository/releases")
                self.assert_redirect_drops_authentication(request, expected)

    def test_registry_authenticates_token_and_manifest_without_redirect_leaks(self):
        requests = []

        def open_url(request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                return Response(b'{"token":"synthetic-registry-token"}')
            return Response(b'{}', {"Docker-Content-Digest": "sha256:synthetic"})

        with patch.dict(os.environ, {"GITHUB_ACTOR": "example", "GH_TOKEN": "synthetic-login-token"  # nosec B105 # synthetic credential test canary
                }, clear=True), \
                patch.object(registry.urllib.request, "urlopen", side_effect=open_url):
            self.assertEqual(registry.resolve("ghcr.io/example/image:v1", authenticated=True),
                             {"digest": "sha256:synthetic", "platforms": {}})
        expected_basic = "Basic " + base64.b64encode(b"example:synthetic-login-token").decode()
        self.assert_redirect_drops_authentication(requests[0], expected_basic)
        self.assert_redirect_drops_authentication(requests[1], "Bearer synthetic-registry-token")
        self.assertIn("scope=repository%3Aexample%2Fimage%3Apull%2Cpush", requests[0].full_url)
        self.assertEqual(requests[1].get_header("Accept"), registry.ACCEPT)

    def test_anonymous_registry_request_does_not_send_account_credentials(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(registry.urllib.request, "urlopen", side_effect=[
                    Response(b'{"access_token":"synthetic-pull-token"}'),
                    Response(b'{}', {"Docker-Content-Digest": "sha256:synthetic"}),
                ]) as open_url:
            registry.resolve("docker.io/library/example:v1")
        token_request, manifest_request = [call.args[0] for call in open_url.call_args_list]
        self.assertIsNone(token_request.get_header("Authorization"))
        self.assert_redirect_drops_authentication(manifest_request, "Bearer synthetic-pull-token")

    def test_only_a_manifest_404_is_an_absent_tag(self):
        for code in (401, 403, 404, 429, 503):
            failure = urllib.error.HTTPError("https://ghcr.io/v2/example/image/manifests/v1", code,
                                             "synthetic failure", {}, io.BytesIO())
            with self.subTest(code=code), patch.object(registry.urllib.request, "urlopen", side_effect=[
                    Response(b'{"token":"synthetic-pull-token"}'), failure]):
                if code == 404:
                    self.assertIsNone(registry.resolve("ghcr.io/example/image:v1"))
                else:
                    with self.assertRaises(urllib.error.HTTPError) as raised:
                        registry.resolve("ghcr.io/example/image:v1")
                    self.assertEqual(raised.exception.code, code)

    def test_token_endpoint_errors_never_become_an_absent_tag(self):
        failure = urllib.error.HTTPError("https://ghcr.io/token", 404, "synthetic failure", {}, io.BytesIO())
        with patch.object(registry.urllib.request, "urlopen", side_effect=failure), \
                self.assertRaises(urllib.error.HTTPError):
            registry.resolve("ghcr.io/example/image:v1")


if __name__ == "__main__":
    unittest.main()
