"""Tests for version sorting and tag normalization."""
from tagtruth.versions import sort_versions_newest_first, strip_tag_prefix, version_key


def test_numeric_components_sort_numerically():
    assert version_key("1.10") > version_key("1.9")


def test_sort_versions_newest_first():
    assert sort_versions_newest_first(["1.36.0", "1.9", "1.36.1", "1.10"]) == [
        "1.36.1",
        "1.36.0",
        "1.10",
        "1.9",
    ]


def test_sort_versions_dedupes():
    assert sort_versions_newest_first(["1.0", "1.0", "2.0"]) == ["2.0", "1.0"]


def test_strip_tag_prefix_lowercase_v():
    assert strip_tag_prefix("v1.36.1") == "1.36.1"


def test_strip_tag_prefix_uppercase_v():
    assert strip_tag_prefix("V2.0") == "2.0"


def test_strip_tag_prefix_without_v_unchanged():
    assert strip_tag_prefix("1.36.1") == "1.36.1"


def test_strip_tag_prefix_bare_v_unchanged():
    assert strip_tag_prefix("v") == "v"
    assert strip_tag_prefix("version-1") == "version-1"
