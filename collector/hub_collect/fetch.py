"""Download one feed. Any network problem becomes FetchError so one bad source never stops the run."""
from __future__ import annotations

import urllib.request

# A browser-like agent: some publishers answer 403 to unknown clients (checked 2026-10-16).
USER_AGENT = "Mozilla/5.0 (compatible; HJ_hub-collector/0.1; +https://github.com/hyjongparkwhy-dev/HJ_hub)"


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except OSError as e:  # URLError, HTTPError and socket timeouts are all OSError
        raise FetchError(type(e).__name__) from e
