# Enables `python -m relio ...` (same entry point as the `relio` console script).
from .cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
