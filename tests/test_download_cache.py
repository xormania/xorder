"""Durable pinned bytes must survive new consumers and unavailable origins."""
import hashlib
import io
import tempfile
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from scripts.xorder.download_cache import cached_download


class Response(io.BytesIO):
    def geturl(self):
        return "https://releases.example.test/pinned"


class DownloadCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name)
        self.payload = b"exact independently pinned upstream bytes\n"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.url = "https://releases.example.test/pinned"

    def fetch(self, **kwargs):
        return cached_download(self.url, self.digest, cache_dir=self.cache, **kwargs)

    def test_fresh_consumer_reuses_verified_bytes_with_origin_unavailable(self):
        with patch("urllib.request.OpenerDirector.open", return_value=Response(self.payload)) as upstream:
            first = self.fetch()
            self.assertEqual(first.read_bytes(), self.payload)
            self.assertEqual(upstream.call_count, 1)
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("origin unavailable")):
            self.assertEqual(self.fetch().read_bytes(), self.payload)

    def test_corrupt_cache_is_replaced_only_by_verified_bytes(self):
        (self.cache / self.digest).write_bytes(b"corrupt")
        with patch("urllib.request.OpenerDirector.open", return_value=Response(self.payload)) as upstream:
            self.assertEqual(self.fetch().read_bytes(), self.payload)
            self.assertEqual(upstream.call_count, 1)

    def test_corrupt_origin_never_becomes_a_cache_hit(self):
        with patch("urllib.request.OpenerDirector.open", return_value=Response(b"wrong bytes")) as upstream:
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                self.fetch()
            self.assertEqual(upstream.call_count, 1)
        self.assertFalse((self.cache / self.digest).exists())

    def test_parallel_consumers_acquire_the_same_pin_once(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=lambda *args, **kwargs: Response(self.payload)) as upstream:
            with ThreadPoolExecutor(max_workers=4) as pool:
                paths = list(pool.map(lambda _: self.fetch(), range(8)))
            self.assertEqual(upstream.call_count, 1)
            self.assertEqual(len(set(paths)), 1)

    def test_transient_http_failure_retries_but_404_does_not(self):
        unavailable = urllib.error.HTTPError(self.url, 503, "Unavailable", {}, None)
        with patch("urllib.request.OpenerDirector.open", side_effect=[unavailable, Response(self.payload)]) as upstream, \
                patch("scripts.xorder.download_cache.time.sleep"):
            self.assertEqual(self.fetch().read_bytes(), self.payload)
            self.assertEqual(upstream.call_count, 2)
        (self.cache / self.digest).unlink()
        missing = urllib.error.HTTPError(self.url, 404, "Missing", {}, None)
        with patch("urllib.request.OpenerDirector.open", side_effect=missing) as upstream:
            with self.assertRaises(urllib.error.HTTPError):
                self.fetch()
            self.assertEqual(upstream.call_count, 1)

    def test_cache_hit_does_not_bypass_url_policy(self):
        (self.cache / self.digest).write_bytes(self.payload)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            cached_download("http://releases.example.test/pinned", self.digest, cache_dir=self.cache)

    def test_symlink_entry_is_not_trusted_or_followed(self):
        outside = self.cache / "outside"
        outside.write_bytes(b"unrelated")
        (self.cache / self.digest).symlink_to(outside)
        with patch("urllib.request.OpenerDirector.open", return_value=Response(self.payload)):
            path = self.fetch()
        self.assertFalse(path.is_symlink())
        self.assertEqual(path.read_bytes(), self.payload)
        self.assertEqual(outside.read_bytes(), b"unrelated")


if __name__ == "__main__":
    unittest.main()
