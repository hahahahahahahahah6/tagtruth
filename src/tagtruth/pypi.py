"""Fetch PyPI release metadata (stdlib only)."""
from __future__ import annotations

import json

from .http import FetchError, fetch


def fetch_pypi_info(name: str, get=fetch) -> dict:
    """Return {'versions': [...], 'sdist_url': {version: url}} for a package.

    Raises FetchError when the package does not exist or the fetch fails.
    """
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        body, _ = get(url)
    except FetchError as exc:
        if "HTTP 404" in str(exc):
            raise FetchError(f"package {name!r} not found on PyPI") from exc
        raise
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"GET {url}: invalid JSON: {exc}") from exc
    releases = data.get("releases") or {}
    sdist_url: dict[str, str] = {}
    for version, files in releases.items():
        if not isinstance(files, list):
            continue
        for entry in files:
            if isinstance(entry, dict) and entry.get("packagetype") == "sdist":
                dl = entry.get("url")
                if dl:
                    sdist_url[version] = dl
                    break
    return {"versions": list(releases.keys()), "sdist_url": sdist_url}
