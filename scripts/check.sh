#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"
echo "== ruff check =="
"$PYTHON" -m ruff check src tests scripts skills/recursive-world-builder/scripts
echo "== ruff format check =="
"$PYTHON" -m ruff format --check src tests scripts skills/recursive-world-builder/scripts
echo "== pytest =="
"$PYTHON" -m pytest
echo "== offline demo =="
"$PYTHON" scripts/run_demo.py --approve
echo "== example canon check =="
"$PYTHON" - <<'PY'
import json
from pathlib import Path

world = json.loads(Path("examples/electric_city/world.json").read_text())
assert world["canon_version"] == 1, world["canon_version"]
print("example canon v1 intact")
PY
