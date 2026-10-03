"""Tests for the CLI: exit codes, formats, argument validation."""
import json

import pytest

import tagtruth.cli as cli_mod
from tagtruth.cli import main

CLEAN_INFO = {"versions": ["1.0", "2.0"], "sdist_url": {}}
CLEAN_TAGS = {"v1.0", "v2.0"}


def patch_network(monkeypatch, info, tags, fail=None):
    def _pypi(name):
        if fail == "pypi":
            from tagtruth.http import FetchError

            raise FetchError("boom")
        return info

    def _tags(owner, repo):
        if fail == "github":
            from tagtruth.http import FetchError

            raise FetchError("boom")
        return tags

    monkeypatch.setattr(cli_mod, "fetch_pypi_info", _pypi)
    monkeypatch.setattr(cli_mod, "fetch_github_tags", _tags)


def base_args(monkeypatch, tmp_path):
    # keep config discovery away from the real cwd
    monkeypatch.chdir(tmp_path)
    return ["check", "--package", "demo-pkg", "--repo", "o/r"]


def test_exit_0_when_clean(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS)
    assert main(base_args(monkeypatch, tmp_path)) == 0
    out = capsys.readouterr().out
    assert "0 mismatch" in out


def test_exit_1_on_missing_tag(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, {"v1.0"})
    assert main(base_args(monkeypatch, tmp_path)) == 1
    assert "MISSING_TAG" in capsys.readouterr().out


def test_exit_1_when_deep_check_inconclusive(monkeypatch, tmp_path, capsys):
    # --deep with no sdist published: unverifiable, must not exit 0.
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS)
    args = base_args(monkeypatch, tmp_path) + ["--deep"]
    assert main(args) == 1
    out = capsys.readouterr().out
    assert "NO_SDIST" in out
    assert "unverifiable" in out


def test_exit_2_on_pypi_failure(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS, fail="pypi")
    assert main(base_args(monkeypatch, tmp_path)) == 2
    assert "error" in capsys.readouterr().err


def test_exit_2_on_github_failure(monkeypatch, tmp_path):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS, fail="github")
    assert main(base_args(monkeypatch, tmp_path)) == 2


def test_exit_2_on_bad_repo(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS)
    assert main(["check", "--package", "x", "--repo", "not-a-repo"]) == 2
    assert "OWNER/REPO" in capsys.readouterr().err


def test_exit_2_on_bad_limit(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS)
    args = base_args(monkeypatch, tmp_path) + ["--limit", "0"]
    assert main(args) == 2


def test_exit_2_on_bad_map(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, CLEAN_TAGS)
    args = base_args(monkeypatch, tmp_path) + ["--map", "novalue"]
    assert main(args) == 2


def test_json_format_shape(monkeypatch, tmp_path, capsys):
    patch_network(monkeypatch, CLEAN_INFO, {"v1.0"})
    args = base_args(monkeypatch, tmp_path) + ["--format", "json"]
    assert main(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 2
    row = next(r for r in payload if r["version"] == "2.0")
    assert row["verdict"] == "MISSING_TAG"
    assert set(row) == {
        "version",
        "expected_tags",
        "found_tag",
        "sdist_version",
        "verdict",
        "detail",
    }


def test_all_flag_ignores_limit(monkeypatch, tmp_path, capsys):
    info = {"versions": ["1.0", "2.0", "3.0"], "sdist_url": {}}
    patch_network(monkeypatch, info, set())
    args = base_args(monkeypatch, tmp_path) + ["--all", "--format", "json"]
    assert main(args) == 1
    assert len(json.loads(capsys.readouterr().out)) == 3


def test_map_and_ignore_cli_options(monkeypatch, tmp_path):
    patch_network(monkeypatch, CLEAN_INFO, {"v1.0"})
    args = base_args(monkeypatch, tmp_path) + ["--map", "2.0=v1.0", "--ignore", "9.9"]
    assert main(args) == 0  # 2.0 now maps to existing tag v1.0


def test_config_file_is_loaded(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.tagtruth]\nmap = { "2.0" = "v1.0" }\n', encoding="utf-8"
    )
    patch_network(monkeypatch, CLEAN_INFO, {"v1.0"})
    assert main(base_args(monkeypatch, tmp_path)) == 0


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "tagtruth" in capsys.readouterr().out
