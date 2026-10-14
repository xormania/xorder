"""Authenticated GitHub JSON reads with bounded transient-error retries."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "xorder-refresh"})
    origin = urllib.parse.urlsplit(url)
    if (origin.scheme == "https" and origin.hostname == "api.github.com"
            and origin.port in (None, 443) and not origin.username and not origin.password):
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            # urllib drops unredirected headers when constructing a redirected
            # request. Credentials must never follow API redirects to assets.
            request.add_unredirected_header("Authorization", "Bearer " + token)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            retry_after = error.headers.get("Retry-After")
            limited = error.code == 403 and (error.headers.get("X-RateLimit-Remaining") == "0"
                                             or retry_after is not None)
            retryable = limited or error.code in (429, 502, 503, 504)
            if not retryable or attempt == 2:
                raise
            delay = 2 ** attempt
            if retry_after is not None:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    raise  # An unknown retry window cannot justify retrying early.
            if delay > 20:
                raise  # Let the next workflow attempt retry beyond this bound.
            error.close()
            time.sleep(delay)
