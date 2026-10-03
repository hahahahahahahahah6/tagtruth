"""Tests for [tool.tagtruth] config parsing and merging."""
import pytest

from tagtruth.config import (
    load_config_file,
    merge_config,
    parse_cli_map,
    parse_tagtruth_toml,
)


def test_parse_map_and_ignore():
    text = """
[tool.tagtruth]
ignore = ["1.36.0rc1", "0.0.0-nightly"]
map = { "1.36.0" = "v1.36", "2.0" = "release-2.0" }
"""
    assert parse_tagtruth_toml(text) == {
        "map": {"1.36.0": "v1.36", "2.0": "release-2.0"},
        "ignore": ["1.36.0rc1", "0.0.0-nightly"],
    }


def test_other_sections_ignored():
    text = """
[tool.other]
map = { "x" = "y" }

[tool.tagtruth]
ignore = ["1.0"]
"""
    assert parse_tagtruth_toml(text) == {"map": {}, "ignore": ["1.0"]}


def test_empty_document_gives_empty_config():
    assert parse_tagtruth_toml("") == {"map": {}, "ignore": []}
    assert parse_tagtruth_toml("[project]\nname = \"x\"\n") == {"map": {}, "ignore": []}


def test_malformed_lines_tolerated():
    text = "[tool.tagtruth]\nignore = [\"a\"]\nthis line has no equals at all\nmap = \n"
    assert parse_tagtruth_toml(text) == {"map": {}, "ignore": ["a"]}


def test_parse_cli_map_valid():
    assert parse_cli_map(["1.36.0=v1.36", "2.0 = release-2.0"]) == {
        "1.36.0": "v1.36",
        "2.0": "release-2.0",
    }


@pytest.mark.parametrize("bad", ["novalue", "=tag", "1.0=", ""])
def test_parse_cli_map_invalid_raises(bad):
    with pytest.raises(ValueError):
        parse_cli_map([bad])


def test_merge_config_cli_map_wins():
    merged = merge_config(
        {"map": {"1.0": "v1"}, "ignore": ["0.9"]},
        {"1.0": "release-1"},
        ["0.8"],
    )
    assert merged == {"map": {"1.0": "release-1"}, "ignore": ["0.9", "0.8"]}


def test_merge_config_ignore_dedupes():
    merged = merge_config({"map": {}, "ignore": ["0.9"]}, {}, ["0.9"])
    assert merged["ignore"] == ["0.9"]


def test_load_config_file_missing_returns_empty(tmp_path):
    assert load_config_file(str(tmp_path / "nope.toml")) == {"map": {}, "ignore": []}


def test_load_config_file_reads_section(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[tool.tagtruth]\nignore = ["1.0"]\n', encoding="utf-8")
    assert load_config_file(str(path)) == {"map": {}, "ignore": ["1.0"]}
