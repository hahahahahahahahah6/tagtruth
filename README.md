# tagtruth

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![No dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](pyproject.toml)

**Your PyPI package says 1.36.1. The Git tag says 1.36.0.**

Real case: [`google-adk==1.36.0`](https://github.com/google/adk-python/issues/6330)
exists on PyPI, but there is **no** GitHub release or tag for v1.36.0 —
[`releases/tag/v1.36.0`](https://github.com/google/adk-python/releases/tag/v1.36.0)
returns 404 and `git ls-remote --tags` shows only v1.36.1. Worse, the v1.36.1
tag points at a commit whose `version.py` still says `__version__ = "1.36.0"`
while the PyPI 1.36.1 sdist says `1.36.1`. The tag doesn't even match the code
that shipped.

tagtruth checks that a package's published PyPI versions actually correspond to
tags in its GitHub repo — the release-integrity question nobody's CI asks.

Part of the release-integrity series: [readmeta](https://github.com/hahahahahahahahah6/readmeta)
(did your README render?), [wheeltruth](https://github.com/hahahahahahahahah6/wheeltruth)
(did your wheel ship complete?), tagtruth (does the tag match the release?).

## Quickstart

```bash
pip install tagtruth
tagtruth check --package google-adk --repo google/adk-python
```

```
version  expected tag   found tag   sdist   verdict
-------  -------------  ---------   -----   -------
1.36.1   v1.36.1        v1.36.1     -       OK
1.36.0   v1.36.0/1.36.0 -           -       MISSING_TAG

checked 2 versions, 1 mismatch(es): 1.36.0 (MISSING_TAG)
```

Exit codes: `0` clean, `1` mismatches found, `2` errors (fetch failures, bad args).

Options:

```bash
tagtruth check --package <pypi-name> --repo <owner/repo> \
  [--limit 10 | --all] \     # how many of the newest versions to check
  [--deep] \                 # also download each sdist, compare PKG-INFO Version
  [--map 1.36.0=v1.36] \     # expected tag name for a version (repeatable)
  [--ignore 1.0rc1] \        # skip a version (repeatable)
  [--config path.toml] \     # TOML file with [tool.tagtruth] (default: ./pyproject.toml)
  [--format json]            # machine-readable output
```

`--deep` additionally verifies that each version's sdist actually claims the
version PyPI lists, and that the tag name agrees with the sdist:

```
version  expected tag  found tag  sdist   verdict
1.36.1   v1.36.1       v1.36.1    1.36.1  OK
```

New verdicts under `--deep`: `SDIST_MISMATCH` (PyPI says X, sdist says Y),
`TAG_SDIST_MISMATCH` (tag name disagrees with the sdist).

## Config: killing false positives

Many projects intentionally skip tags or name them differently. Without a
mapping file, tagtruth drowns in false positives — so mapping is a first-class
feature, not an afterthought. Put this in your `pyproject.toml`:

```toml
[tool.tagtruth]
ignore = ["0.0.0-nightly", "1.0.0rc1"]
map = { "1.36.0" = "v1.36", "2.0" = "release-2.0" }
```

CLI flags `--map` and `--ignore` do the same thing ad hoc and override the
file per key.

## CI snippet

```yaml
- name: Check release/tag integrity
  run: |
    pip install tagtruth
    tagtruth check --package my-pkg --repo myorg/myrepo --all
```

Add it as a post-release job: if a release ever ships without its tag, the
pipeline fails loudly instead of rotting silently.

## How it works

- PyPI versions: `https://pypi.org/pypi/<name>/json` (`releases` keys, sdist URLs).
- GitHub tags: `https://api.github.com/repos/<owner>/<repo>/tags` (paginated).
- Expected tag for version `X` is `vX` or `X`, unless `--map`/`map` says otherwise.
- `--deep` downloads each sdist (capped at 100 MB) and reads `PKG-INFO`'s
  `Version:` field from the zip/tarball.

Zero dependencies, Python 3.9+. Unauthenticated GitHub API calls are fine for
occasional checks (60 req/hour); the deep sdist check is structured so a
future version can also compare the tag's commit content.

## Limitations

- Tag-name comparison is syntactic: it can't tell you the tag *points at the
  wrong commit* (the second half of the adk story). That's the next check on
  the roadmap.
- Version ordering is best-effort without PEP 440 (no dependency means no
  `packaging`); exotic schemes may sort oddly — use `--all` and eyeball it.
