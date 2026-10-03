"""tagtruth CLI."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .checker import MISMATCH_VERDICTS, Check, check_package, has_mismatches
from .config import (
    find_default_config,
    load_config_file,
    merge_config,
    parse_cli_map,
)
from .github import fetch_github_tags
from .http import FetchError
from .pypi import fetch_pypi_info


def parse_repo(value: str) -> tuple[str, str]:
    if "/" not in value:
        raise ValueError("--repo must look like OWNER/REPO")
    owner, repo = value.split("/", 1)
    if not owner or not repo:
        raise ValueError("--repo must look like OWNER/REPO")
    return owner, repo


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tagtruth",
        description="Check that a PyPI package's releases have matching Git tags.",
    )
    p.add_argument("--version", action="version", version="tagtruth " + __version__)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check PyPI versions against Git tags")
    c.add_argument("--package", required=True, help="PyPI package name")
    c.add_argument("--repo", required=True, help="GitHub repo as OWNER/REPO")
    c.add_argument(
        "--limit",
        type=int,
        default=10,
        help="how many of the newest versions to check (default 10)",
    )
    c.add_argument(
        "--all",
        action="store_true",
        help="check every published version, ignoring --limit",
    )
    c.add_argument(
        "--deep",
        action="store_true",
        help="also download each sdist and compare its PKG-INFO version",
    )
    c.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="VERSION=TAG",
        help="expected tag name for a version (repeatable)",
    )
    c.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="VERSION",
        help="skip a version (repeatable)",
    )
    c.add_argument(
        "--config",
        default=None,
        help="TOML file with [tool.tagtruth] map/ignore "
        "(default: ./pyproject.toml if present)",
    )
    c.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format (default text)",
    )
    return p


def check_to_dict(check: Check) -> dict:
    return {
        "version": check.version,
        "expected_tags": check.expected_tags,
        "found_tag": check.found_tag,
        "sdist_version": check.sdist_version,
        "verdict": check.verdict,
        "detail": check.detail,
    }


def format_text(results: list[Check]) -> str:
    rows = [("version", "expected tag", "found tag", "sdist", "verdict")]
    for c in results:
        rows.append(
            (
                c.version,
                "/".join(c.expected_tags) if c.expected_tags else "-",
                c.found_tag or "-",
                c.sdist_version or "-",
                c.verdict,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    lines = []
    for i, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)).rstrip())
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    mismatches = sum(1 for c in results if c.verdict in MISMATCH_VERDICTS)
    lines.append("")
    lines.append(
        f"checked {len(results)} versions, {mismatches} mismatch(es)"
        + ("" if mismatches == 0 else ": " + ", ".join(
            f"{c.version} ({c.verdict})"
            for c in results
            if c.verdict in MISMATCH_VERDICTS
        ))
    )
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        owner, repo = parse_repo(args.repo)
    except ValueError as exc:
        print(f"tagtruth: error: {exc}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("tagtruth: error: --limit must be >= 1", file=sys.stderr)
        return 2
    try:
        cli_map = parse_cli_map(args.map)
    except ValueError as exc:
        print(f"tagtruth: error: {exc}", file=sys.stderr)
        return 2

    config_path = args.config or find_default_config()
    file_config = load_config_file(config_path) if config_path else {"map": {}, "ignore": []}
    config = merge_config(file_config, cli_map, args.ignore)

    try:
        info = fetch_pypi_info(args.package)
        tags = fetch_github_tags(owner, repo)
    except FetchError as exc:
        print(f"tagtruth: error: {exc}", file=sys.stderr)
        return 2

    limit = None if args.all else args.limit
    results = check_package(
        info["versions"],
        tags,
        mapping=config["map"],
        ignore=config["ignore"],
        limit=limit,
        deep=args.deep,
        sdist_url=info["sdist_url"],
    )

    if args.format == "json":
        print(json.dumps([check_to_dict(c) for c in results], indent=2))
    else:
        print(format_text(results))
    return 1 if has_mismatches(results) else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
