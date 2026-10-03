"""Download an sdist and read its PKG-INFO Version (stdlib only)."""
from __future__ import annotations

import io
import re
import tarfile
import zipfile

from .http import FetchError, fetch

MAX_SDIST_BYTES = 100 * 1024 * 1024
_VERSION_RE = re.compile(r"^Version:\s*(.+?)\s*$", re.MULTILINE)


def _pkg_info_version(text: str) -> str:
    match = _VERSION_RE.search(text)
    if not match:
        raise FetchError("sdist PKG-INFO has no Version field")
    return match.group(1)


def sdist_pkg_info_version(url: str, get=fetch) -> str:
    """Download an sdist and return the Version from its PKG-INFO.

    Supports .zip, .tar.gz and .tgz. Raises FetchError on any problem.
    """
    body, _ = get(url, limit=MAX_SDIST_BYTES)
    name = url.rsplit("/", 1)[-1].lower()
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                candidates = [n for n in zf.namelist() if n.endswith("/PKG-INFO")]
                if not candidates:
                    raise FetchError(f"sdist {url}: no PKG-INFO found")
                text = zf.read(candidates[0]).decode("utf-8", "replace")
        elif name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
                member = next(
                    (m for m in tf.getmembers() if m.name.endswith("/PKG-INFO")),
                    None,
                )
                if member is None:
                    raise FetchError(f"sdist {url}: no PKG-INFO found")
                extracted = tf.extractfile(member)
                if extracted is None:
                    raise FetchError(f"sdist {url}: cannot read PKG-INFO")
                text = extracted.read().decode("utf-8", "replace")
        else:
            raise FetchError(f"sdist {url}: unsupported archive type")
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError) as exc:
        raise FetchError(f"sdist {url}: unreadable archive: {exc}") from exc
    return _pkg_info_version(text)
