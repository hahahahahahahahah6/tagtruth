"""Tests for the core checker, incl. a replay of google/adk-python #6330.

Fixtures under tests/fixtures/ mirror the real evidence:
- adk_pypi.json: PyPI lists 1.36.0 and 1.36.1 (both with sdists)
- adk_tags.json:  GitHub has tags v1.36.1 and v1.35.0, but NO v1.36.0
"""
import io
import json
import os
import tarfile
import zipfile

from tagtruth.checker import (
    CHECK_FAILED,
    IGNORED,
    MISSING_TAG,
    NO_SDIST,
    OK,
    SDIST_MISMATCH,
    TAG_SDIST_MISMATCH,
    check_package,
    expected_tags_for,
    has_mismatches,
    has_problems,
)

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load_adk():
    with open(os.path.join(FIX, "adk_pypi.json"), encoding="utf-8") as fh:
        pypi = json.load(fh)
    with open(os.path.join(FIX, "adk_tags.json"), encoding="utf-8") as fh:
        tags = {t["name"] for t in json.load(fh)}
    return pypi, tags


def make_sdist_get(version_by_url):
    def _get(url, limit=None, timeout=30):
        version = version_by_url[url]
        pkg_info = f"Metadata-Version: 2.1\nName: pkg\nVersion: {version}\n"
        buf = io.BytesIO()
        if url.endswith(".zip"):
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr(f"pkg-{version}/PKG-INFO", pkg_info)
        else:
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                data = pkg_info.encode()
                info = tarfile.TarInfo(f"pkg-{version}/PKG-INFO")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return buf.getvalue(), {}

    return _get


def adk_sdist_urls(pypi):
    return {
        v: files[0]["url"]
        for v, files in pypi["releases"].items()
        if any(f["packagetype"] == "sdist" for f in files)
    }


def test_adk_replay_missing_tag():
    pypi, tags = load_adk()
    results = check_package(list(pypi["releases"]), tags)
    by_version = {c.version: c for c in results}
    assert by_version["1.36.0"].verdict == MISSING_TAG
    assert by_version["1.36.0"].found_tag is None
    assert by_version["1.36.1"].verdict == OK
    assert by_version["1.36.1"].found_tag == "v1.36.1"
    assert has_mismatches(results)


def test_adk_replay_with_deep_check():
    pypi, tags = load_adk()
    sdist_url = adk_sdist_urls(pypi)
    get = make_sdist_get({u: v for v, u in sdist_url.items()})
    results = check_package(
        list(pypi["releases"]),
        tags,
        deep=True,
        sdist_url=sdist_url,
        get=get,
    )
    by_version = {c.version: c for c in results}
    # 1.36.0 has no tag -> still missing, no sdist inspection attempted
    assert by_version["1.36.0"].verdict == MISSING_TAG
    # 1.36.1 tag + sdist agree -> OK
    assert by_version["1.36.1"].verdict == OK
    assert by_version["1.36.1"].sdist_version == "1.36.1"


def test_mapped_tag_honored():
    results = check_package(["1.36"], {"v1.36"}, mapping={"1.36": "v1.36"})
    assert results[0].verdict == OK
    assert results[0].found_tag == "v1.36"


def test_unmapped_missing_tag():
    results = check_package(["1.36"], {"release-1.36"})
    assert results[0].verdict == MISSING_TAG
    assert "v1.36" in results[0].expected_tags


def test_ignored_version_not_a_mismatch():
    results = check_package(["1.0", "2.0"], set(), ignore=["1.0"])
    by_version = {c.version: c for c in results}
    assert by_version["1.0"].verdict == IGNORED
    assert not has_mismatches([by_version["1.0"]])


def test_deep_sdist_version_mismatch():
    get = make_sdist_get({"https://x/pkg-2.0.tar.gz": "2.0.1"})
    results = check_package(
        ["2.0"],
        {"v2.0"},
        deep=True,
        sdist_url={"2.0": "https://x/pkg-2.0.tar.gz"},
        get=get,
    )
    assert results[0].verdict == SDIST_MISMATCH
    assert results[0].sdist_version == "2.0.1"
    assert has_mismatches(results)


def test_deep_tag_sdist_mismatch():
    get = make_sdist_get({"https://x/pkg-2.0.tar.gz": "2.0.1"})
    results = check_package(
        ["2.0.1"],
        {"v2.0"},  # tag claims 2.0, sdist claims 2.0.1
        deep=True,
        sdist_url={"2.0.1": "https://x/pkg-2.0.tar.gz"},
        get=get,
        mapping={"2.0.1": "v2.0"},
    )
    assert results[0].verdict == TAG_SDIST_MISMATCH
    assert results[0].sdist_version == "2.0.1"
    assert has_mismatches(results)


def test_deep_tag_name_vs_sdist_mismatch():
    get = make_sdist_get({"https://x/pkg-2.0.tar.gz": "2.0"})
    results = check_package(
        ["2.0"],
        {"release-2"},  # mapped tag, normalizes to "release-2" != "2.0"
        deep=True,
        sdist_url={"2.0": "https://x/pkg-2.0.tar.gz"},
        get=get,
        mapping={"2.0": "release-2"},
    )
    assert results[0].verdict == TAG_SDIST_MISMATCH


def test_deep_without_sdist_is_inconclusive_not_clean():
    results = check_package(["2.0"], {"v2.0"}, deep=True, sdist_url={}, get=lambda *a, **k: (b"", {}))
    assert results[0].verdict == NO_SDIST
    assert not has_mismatches(results)
    # An unverifiable check is a problem, never a pass (exit 1, not 0).
    assert has_problems(results)


def test_deep_sdist_inspection_failure_is_check_failed():
    def boom(*a, **k):
        raise OSError("network down")
    results = check_package(
        ["2.0"], {"v2.0"}, deep=True,
        sdist_url={"2.0": "https://x/pkg-2.0.tar.gz"}, get=boom,
    )
    assert results[0].verdict == CHECK_FAILED
    assert "network down" in results[0].detail
    assert has_problems(results)


def test_limit_selects_newest():
    results = check_package(["1.0", "2.0", "3.0"], set(), limit=2)
    assert [c.version for c in results] == ["3.0", "2.0"]


def test_limit_none_checks_everything():
    results = check_package(["1.0", "2.0", "3.0"], set(), limit=None)
    assert [c.version for c in results] == ["3.0", "2.0", "1.0"]


def test_expected_tags_for_default_and_mapped():
    assert expected_tags_for("1.36.0", {}) == ["v1.36.0", "1.36.0"]
    assert expected_tags_for("1.36.0", {"1.36.0": "release-1.36"}) == ["release-1.36"]
