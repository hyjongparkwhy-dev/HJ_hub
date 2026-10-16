"""Download one feed. Any network problem becomes FetchError so one bad source never stops the run."""
from __future__ import annotations

import http.client
import urllib.request

# A browser-like agent: some publishers answer 403 to unknown clients (checked 2026-10-16).
USER_AGENT = "Mozilla/5.0 (compatible; HJ_hub-collector/0.1; +https://github.com/hyjongparkwhy-dev/HJ_hub)"


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = 20, attempts: int = 2) -> bytes:
    # hnrss.org timed out on the TLS handshake in one of three tries (2026-10-16), so one retry is worth it.
    for attempt in range(attempts):
        try:
            return _fetch_once(url, timeout)
        except FetchError:
            if attempt == attempts - 1:
                raise
    raise AssertionError("unreachable")


def _fetch_once(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    # URLError, HTTPError, SSL errors and socket timeouts are OSError; a connection cut mid-body
    # (IncompleteRead) or a garbled status line are HTTPException, which is not.
    except (OSError, http.client.HTTPException) as e:
        raise FetchError(type(e).__name__) from e
