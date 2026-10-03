"""Tests for PyPI metadata fetching (network mocked)."""
import json

import pytest

from tagtruth.http import FetchError
from tagtruth.pypi import fetch_pypi_info

PAYLOAD = {
    "info": {"name": "demo-pkg"},
    "releases": {
        "1.0": [
            {
                "filename": "demo_pkg-1.0.tar.gz",
                "packagetype": "sdist",
                "url": "https://files.example.com/demo_pkg-1.0.tar.gz",
            },
            {
                "filename": "demo_pkg-1.0-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "url": "https://files.example.com/demo_pkg-1.0-py3-none-any.whl",
            },
        ],
        "2.0": [
            {
                "filename": "demo_pkg-2.0-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "url": "https://files.example.com/demo_pkg-2.0-py3-none-any.whl",
            }
        ],
    },
}


def fake_get(payload, headers=None):
    def _get(url, limit=None, timeout=30):
        return payload, headers or {}

    return _get


def test_versions_and_sdist_urls():
    info = fetch_pypi_info("demo-pkg", get=fake_get(json.dumps(PAYLOAD).encode()))
    assert sorted(info["versions"]) == ["1.0", "2.0"]
    assert info["sdist_url"] == {
        "1.0": "https://files.example.com/demo_pkg-1.0.tar.gz"
    }


def test_version_without_sdist_has_no_url():
    info = fetch_pypi_info("demo-pkg", get=fake_get(json.dumps(PAYLOAD).encode()))
    assert "2.0" not in info["sdist_url"]


def test_404_becomes_not_found():
    def _get(url, limit=None, timeout=30):
        raise FetchError("GET https://pypi.org/pypi/nope/json: HTTP 404")

    with pytest.raises(FetchError, match="not found on PyPI"):
        fetch_pypi_info("nope", get=_get)


def test_invalid_json_raises():
    with pytest.raises(FetchError, match="invalid JSON"):
        fetch_pypi_info("demo-pkg", get=fake_get(b"not json"))


def test_network_error_propagates():
    def _get(url, limit=None, timeout=30):
        raise FetchError("GET https://pypi.org/pypi/x/json: network error: boom")

    with pytest.raises(FetchError, match="network error"):
        fetch_pypi_info("x", get=_get)
