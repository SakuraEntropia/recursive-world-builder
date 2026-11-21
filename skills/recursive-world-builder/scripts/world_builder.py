#!/usr/bin/env python3
"""Skill entry point.

Works both from a checkout (adds ``src/`` to sys.path) and from an installed
package.  All actual command parsing lives in the Python package.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from recursive_world_builder.cli import main
except ImportError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "src"))
    try:
        from recursive_world_builder.cli import main
    except ImportError as exc:  # pragma: no cover
        print(
            "recursive-world-builder is not installed. From the repository root run:\n"
            "  python -m pip install -e .\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

if __name__ == "__main__":
    raise SystemExit(main())
