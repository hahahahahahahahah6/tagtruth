"""Minimal HTTP helpers (stdlib only)."""
from __future__ import annotations

import urllib.error
import urllib.request

USER_AGENT = "tagtruth (+https://github.com/hahahahahahahahah6/tagtruth)"


class FetchError(Exception):
    """Raised when an HTTP fetch fails."""


def fetch(url: str, limit: int | None = None, timeout: int = 30) -> tuple[bytes, dict]:
    """GET url. Returns (body, headers dict). Raises FetchError on failure.

    If limit is set, at most limit bytes are read; exceeding it is an error.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = dict(resp.headers)
            if limit is None:
                return resp.read(), headers
            chunks: list[bytes] = []
            remaining = limit + 1
            while remaining > 0:
                chunk = resp.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            body = b"".join(chunks)
            if len(body) > limit:
                raise FetchError(f"GET {url}: response exceeds {limit} bytes")
            return body, headers
    except urllib.error.HTTPError as exc:
        raise FetchError(f"GET {url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"GET {url}: network error: {exc}") from exc
