"""Core check logic: match PyPI versions against Git tags."""
from __future__ import annotations

from dataclasses import dataclass, field

from .sdist import sdist_pkg_info_version
from .versions import sort_versions_newest_first, strip_tag_prefix

# Verdicts
OK = "OK"
IGNORED = "IGNORED"
MISSING_TAG = "MISSING_TAG"
SDIST_MISMATCH = "SDIST_MISMATCH"  # PyPI version != sdist PKG-INFO Version
TAG_SDIST_MISMATCH = "TAG_SDIST_MISMATCH"  # tag name != sdist PKG-INFO Version
NO_SDIST = "NO_SDIST"  # deep check requested but no sdist published
CHECK_FAILED = "CHECK_FAILED"  # sdist existed but download/inspection failed

MISMATCH_VERDICTS = {MISSING_TAG, SDIST_MISMATCH, TAG_SDIST_MISMATCH}
# The deep check could not be completed at all. This is deliberately NOT a
# clean bill of health: an unverified version must never exit 0.
INCONCLUSIVE_VERDICTS = {NO_SDIST, CHECK_FAILED}


@dataclass
class Check:
    version: str
    expected_tags: list[str] = field(default_factory=list)
    found_tag: str | None = None
    sdist_version: str | None = None
    verdict: str = OK
    detail: str = ""


class DeepChecker:
    """Optional deep check: compare a version's sdist content with its tag.

    The MVP implementation downloads the sdist and compares its PKG-INFO
    Version against the PyPI version and the tag name. A future version can
    additionally fetch the tag's commit content (e.g. version.py) and compare
    that too -- the hook is here on purpose.

    If the sdist cannot be obtained or inspected, the check is INCONCLUSIVE
    (NO_SDIST / CHECK_FAILED) -- never OK. An unverified version must not
    look like a verified one.
    """

    def __init__(self, get):
        self._get = get

    def check(self, check: Check, sdist_url: str | None) -> None:
        if not sdist_url:
            check.verdict = NO_SDIST
            check.detail = "no sdist published for this version; deep check impossible"
            return
        try:
            pkg_version = sdist_pkg_info_version(sdist_url, get=self._get)
        except Exception as exc:  # noqa: BLE001 - surfaced as detail, not crash
            # A failed inspection is a failed check, never a pass.
            check.verdict = CHECK_FAILED
            check.detail = f"could not inspect sdist: {exc}"
            return
        check.sdist_version = pkg_version
        if pkg_version != check.version:
            check.verdict = SDIST_MISMATCH
            check.detail = (
                f"PyPI lists {check.version} but the sdist says {pkg_version}"
            )
            return
        if check.found_tag and strip_tag_prefix(check.found_tag) != pkg_version:
            check.verdict = TAG_SDIST_MISMATCH
            check.detail = (
                f"tag {check.found_tag} does not match sdist version {pkg_version}"
            )
            return
        check.verdict = OK
        check.detail = ""


def expected_tags_for(version: str, mapping: dict) -> list[str]:
    """Expected tag names for a PyPI version, honoring explicit mappings."""
    if version in mapping:
        return [mapping[version]]
    return [f"v{version}", version]


def check_package(
    versions: list[str],
    tags: set[str],
    *,
    mapping: dict | None = None,
    ignore: list | None = None,
    limit: int | None = 10,
    deep: bool = False,
    sdist_url: dict | None = None,
    get=None,
) -> list[Check]:
    """Check PyPI versions against Git tags. Returns one Check per version."""
    mapping = mapping or {}
    ignored = set(ignore or [])
    sdist_url = sdist_url or {}

    ordered = sort_versions_newest_first(versions)
    if limit is not None:
        ordered = ordered[:limit]

    deep_checker = DeepChecker(get) if deep else None
    results: list[Check] = []
    for version in ordered:
        check = Check(version=version)
        if version in ignored:
            check.verdict = IGNORED
            check.detail = "ignored by config"
            results.append(check)
            continue
        check.expected_tags = expected_tags_for(version, mapping)
        check.found_tag = next(
            (t for t in check.expected_tags if t in tags), None
        )
        if check.found_tag is None:
            check.verdict = MISSING_TAG
            check.detail = (
                "no tag named "
                + " or ".join(repr(t) for t in check.expected_tags)
            )
        elif deep_checker is not None:
            deep_checker.check(check, sdist_url.get(version))
        results.append(check)
    return results


def has_mismatches(results: list[Check]) -> bool:
    return any(c.verdict in MISMATCH_VERDICTS for c in results)


def has_problems(results: list[Check]) -> bool:
    """True when anything needs attention: a mismatch OR an unverifiable check.

    An inconclusive deep check (NO_SDIST / CHECK_FAILED) is a problem, not a
    pass — "could not verify" must never be reported as clean.
    """
    return any(
        c.verdict in MISMATCH_VERDICTS or c.verdict in INCONCLUSIVE_VERDICTS
        for c in results
    )
