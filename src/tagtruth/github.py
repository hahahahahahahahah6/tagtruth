"""Fetch GitHub tags with pagination (stdlib only)."""
from __future__ import annotations

import json
import re

from .http import FetchError, fetch

_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def next_link(link_header: str) -> str | None:
    """Extract the rel="next" URL from a GitHub Link header."""
    if not link_header:
        return None
    match = _NEXT_RE.search(link_header)
    return match.group(1) if match else None


def fetch_github_tags(owner: str, repo: str, get=fetch) -> set[str]:
    """Return the set of tag names for a GitHub repo. Follows pagination.

    Raises FetchError when the repo does not exist or the fetch fails.
    """
    tags: set[str] = set()
    url: str | None = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100"
    while url:
        try:
            body, headers = get(url)
        except FetchError as exc:
            if "HTTP 404" in str(exc):
                raise FetchError(
                    f"repo {owner}/{repo} not found on GitHub"
                ) from exc
            raise
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise FetchError(f"GET {url}: invalid JSON: {exc}") from exc
        if not isinstance(payload, list):
            raise FetchError(f"GET {url}: unexpected GitHub API response")
        for entry in payload:
            if isinstance(entry, dict) and entry.get("name"):
                tags.add(entry["name"])
        url = next_link(headers.get("Link", "") or headers.get("link", ""))
    return tags
