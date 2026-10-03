"""Tests for sdist download + PKG-INFO version extraction (network mocked)."""
import io
import tarfile
import zipfile

import pytest

from tagtruth.http import FetchError
from tagtruth.sdist import sdist_pkg_info_version

PKG_INFO = "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.36.1\n"


def make_zip(version="1.36.1"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "demo_pkg-1.36.1/PKG-INFO",
            PKG_INFO.replace("1.36.1", version),
        )
    return buf.getvalue()


def make_tarball(version="1.36.1"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = PKG_INFO.replace("1.36.1", version).encode()
        info = tarfile.TarInfo("demo_pkg-1.36.1/PKG-INFO")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def fake_get(body):
    def _get(url, limit=None, timeout=30):
        if limit is not None and len(body) > limit:
            raise FetchError(f"GET {url}: response exceeds {limit} bytes")
        return body, {}

    return _get


def test_zip_pkg_info_version():
    assert (
        sdist_pkg_info_version(
            "https://x/demo-1.36.1.zip", get=fake_get(make_zip())
        )
        == "1.36.1"
    )


def test_tarball_pkg_info_version():
    assert (
        sdist_pkg_info_version(
            "https://x/demo-1.36.1.tar.gz", get=fake_get(make_tarball())
        )
        == "1.36.1"
    )


def test_tgz_suffix_supported():
    assert (
        sdist_pkg_info_version(
            "https://x/demo-1.36.1.tgz", get=fake_get(make_tarball())
        )
        == "1.36.1"
    )


def test_zip_without_pkg_info_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo_pkg-1.36.1/setup.py", "x = 1")
    with pytest.raises(FetchError, match="no PKG-INFO"):
        sdist_pkg_info_version("https://x/a.zip", get=fake_get(buf.getvalue()))


def test_corrupt_archive_raises():
    with pytest.raises(FetchError, match="unreadable archive"):
        sdist_pkg_info_version("https://x/a.zip", get=fake_get(b"definitely not a zip"))


def test_unsupported_suffix_raises():
    with pytest.raises(FetchError, match="unsupported archive type"):
        sdist_pkg_info_version("https://x/a.whl", get=fake_get(b"data"))


def test_missing_version_field_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo_pkg-1.36.1/PKG-INFO", "Metadata-Version: 2.1\nName: x\n")
    with pytest.raises(FetchError, match="no Version field"):
        sdist_pkg_info_version("https://x/a.zip", get=fake_get(buf.getvalue()))


def test_oversize_sdist_raises():
    # force the limit path via a tiny fake limit
    import tagtruth.sdist as sdist_mod

    real = sdist_mod.MAX_SDIST_BYTES
    sdist_mod.MAX_SDIST_BYTES = 10
    try:
        with pytest.raises(FetchError, match="exceeds"):
            sdist_pkg_info_version("https://x/a.zip", get=fake_get(make_zip()))
    finally:
        sdist_mod.MAX_SDIST_BYTES = real
