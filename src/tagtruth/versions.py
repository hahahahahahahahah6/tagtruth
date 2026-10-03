"""Version sorting and tag-name normalization (no external deps)."""
from __future__ import annotations

import re


def _split(version: str) -> list:
    parts = re.split(r"[.\-+_]", version.strip())
    key: list = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return key


def version_key(version: str) -> list:
    """Sort key for version strings. Numeric components sort numerically."""
    return _split(version)


def sort_versions_newest_first(versions) -> list[str]:
    """Return versions sorted newest-first (best effort, no PEP 440)."""
    return sorted(set(versions), key=version_key, reverse=True)


def strip_tag_prefix(tag: str) -> str:
    """Normalize a tag name to a bare version: 'v1.2.3' -> '1.2.3'."""
    name = tag.strip()
    if len(name) > 1 and name[0] in ("v", "V") and name[1].isdigit():
        return name[1:]
    return name
