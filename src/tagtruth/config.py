"""Version-mapping config: [tool.tagtruth] in a TOML file + CLI overrides.

Minimal TOML subset parser (stdlib only, works on Python 3.9+):

    [tool.tagtruth]
    ignore = ["1.36.0rc1", "0.0.0-nightly"]
    map = { "1.36.0" = "v1.36", "2.0" = "release-2.0" }

Only the [tool.tagtruth] section is read. Supported value shapes:
ignore = [ "a", "b" ]            (array of strings)
map = { "a" = "b", ... }         (inline table of string -> string)
"""
from __future__ import annotations

import os
import re

CONFIG_SECTION = "tool.tagtruth"

_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_PAIR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"')


def _unquote(token: str) -> str:
    return token.replace(r"\"", '"').replace(r"\\", "\\")


def parse_tagtruth_toml(text: str) -> dict:
    """Extract {'map': {...}, 'ignore': [...]} from a TOML document's section."""
    result: dict = {"map": {}, "ignore": []}
    in_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            name = line.strip("[]").strip()
            in_section = name == CONFIG_SECTION
            continue
        if not in_section or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "ignore" and value.startswith("["):
            result["ignore"] = [
                _unquote(m.group(1)) for m in _STR_RE.finditer(value)
            ]
        elif key == "map" and value.startswith("{"):
            result["map"] = {
                _unquote(m.group(1)): _unquote(m.group(2))
                for m in _PAIR_RE.finditer(value)
            }
    return result


def load_config_file(path: str) -> dict:
    """Load [tool.tagtruth] from a TOML file. Missing file -> empty config."""
    if not os.path.isfile(path):
        return {"map": {}, "ignore": []}
    with open(path, encoding="utf-8") as fh:
        return parse_tagtruth_toml(fh.read())


def find_default_config() -> str | None:
    """Return ./pyproject.toml if it exists, else None."""
    candidate = os.path.join(os.getcwd(), "pyproject.toml")
    return candidate if os.path.isfile(candidate) else None


def parse_cli_map(entries: list[str]) -> dict[str, str]:
    """Parse ['1.36.0=v1.36', ...] into a dict. Raises ValueError on bad input."""
    mapping: dict[str, str] = {}
    for entry in entries or []:
        if "=" not in entry:
            raise ValueError(f"--map expects VERSION=TAG, got {entry!r}")
        version, _, tag = entry.partition("=")
        version, tag = version.strip(), tag.strip()
        if not version or not tag:
            raise ValueError(f"--map expects VERSION=TAG, got {entry!r}")
        mapping[version] = tag
    return mapping


def merge_config(file_config: dict, cli_map: dict, cli_ignore: list[str]) -> dict:
    """Merge file config with CLI overrides (CLI wins per key)."""
    merged_map = dict(file_config.get("map") or {})
    merged_map.update(cli_map or {})
    merged_ignore = list(file_config.get("ignore") or [])
    for item in cli_ignore or []:
        if item not in merged_ignore:
            merged_ignore.append(item)
    return {"map": merged_map, "ignore": merged_ignore}
