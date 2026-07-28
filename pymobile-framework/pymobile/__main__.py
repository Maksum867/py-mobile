"""Allow ``python -m pymobile`` as an alias for the ``pymobile`` command.

Useful when pip's scripts directory is not on ``PATH`` — a very common
situation on Windows — because the module form always works.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
