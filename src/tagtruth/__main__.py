"""tagtruth: check that PyPI releases actually have matching Git tags."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
