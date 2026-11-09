"""Content-addressed build downloads, separate from installation recovery blobs."""
import fcntl
import hashlib
import os
import re
import time
import urllib.error
from pathlib import Path

from .transport import _check_url, download


def default_cache():
    configured = os.environ.get("XORDER_DOWNLOAD_CACHE")
    if configured:
        return Path(configured)
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "xorder" / "build-downloads" / "sha256"


def _valid(path, expected):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == expected


def _retryable(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 429, 500, 502, 503, 504}
    return isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError))


def cached_download(url, expected_sha256, *, cache_dir=None, attempts=3):
    """Return exact verified bytes, fetching atomically only on a cache miss.

    Each hit is rehashed. The existing transfer primitive validates HTTPS and
    redirects and never replaces an entry with unverified bytes. A per-digest
    advisory lock prevents parallel Linux build consumers downloading one pin
    repeatedly. Completed entries remain useful if a later build step fails.
    Publication availability checks must continue to call transport.download
    directly, because a cache hit cannot demonstrate public availability.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise ValueError("expected_sha256 must be a 64-character SHA-256 hex digest")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= 5:
        raise ValueError("attempts must be between 1 and 5")
    _check_url(url, False)
    expected = expected_sha256.lower()
    cache = Path(cache_dir) if cache_dir is not None else default_cache()
    cache.mkdir(parents=True, exist_ok=True)
    locks = cache / ".locks"
    locks.mkdir(exist_ok=True)
    destination = cache / expected
    descriptor = os.open(locks / expected, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _valid(destination, expected):
            return destination
        for attempt in range(attempts):
            try:
                download(url, destination, expected)
                return destination
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                if attempt == attempts - 1 or not _retryable(error):
                    raise
                time.sleep(2 ** attempt)
    raise AssertionError("unreachable download attempt state")
