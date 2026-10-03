"""Tests for GitHub tag fetching incl. pagination (network mocked)."""
import json

import pytest

from tagtruth.github import fetch_github_tags, next_link
from tagtruth.http import FetchError


def fake_get(pages):
    """pages: list of (payload_obj, link_header)."""
    state = {"i": 0}

    def _get(url, limit=None, timeout=30):
        payload, link = pages[state["i"]]
        state["i"] += 1
        return json.dumps(payload).encode(), {"Link": link} if link else {}

    return _get


def test_single_page_tags():
    tags = fetch_github_tags(
        "o", "r", get=fake_get([([{"name": "v1.0"}, {"name": "1.1"}], "")])
    )
    assert tags == {"v1.0", "1.1"}


def test_pagination_follows_next_link():
    page1 = [{"name": "v2.0"}]
    page2 = [{"name": "v1.0"}]
    link = '<https://api.github.com/repos/o/r/tags?page=2>; rel="next", <https://api.github.com/repos/o/r/tags?page=2>; rel="last"'
    tags = fetch_github_tags("o", "r", get=fake_get([(page1, link), (page2, "")]))
    assert tags == {"v2.0", "v1.0"}


def test_empty_tag_list():
    assert fetch_github_tags("o", "r", get=fake_get([([], "")])) == set()


def test_404_becomes_not_found():
    def _get(url, limit=None, timeout=30):
        raise FetchError("GET https://api.github.com/repos/o/r/tags: HTTP 404")

    with pytest.raises(FetchError, match="not found on GitHub"):
        fetch_github_tags("o", "r", get=_get)


def test_non_list_payload_raises():
    with pytest.raises(FetchError, match="unexpected GitHub API response"):
        fetch_github_tags("o", "r", get=fake_get([({"oops": True}, "")]))


def test_next_link_parsing():
    assert next_link("") is None
    assert next_link('<https://x>; rel="last"') is None
    assert (
        next_link('<https://x?page=2>; rel="next", <https://x?page=9>; rel="last"')
        == "https://x?page=2"
    )
