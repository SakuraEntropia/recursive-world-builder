"""Load/save worlds, and read Markdown canon into plain notes."""
from __future__ import annotations

import json
from pathlib import Path

from .model import World

WORLD_FILE = "world.json"
CANON_DIR = "canon"


def load_world(root: str | Path) -> World:
    root = Path(root)
    path = root / WORLD_FILE
    if not path.exists():
        raise FileNotFoundError(f"no {WORLD_FILE} in {root}")
    return World.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_world(world: World, root: str | Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / WORLD_FILE
    path.write_text(json.dumps(world.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_canon_notes(root: str | Path) -> list[dict[str, str]]:
    """Read every .md under canon/ as reference material.

    Notes are context for the host agent; they are not parsed into rules.
    """
    root = Path(root) / CANON_DIR
    notes: list[dict[str, str]] = []
    if not root.exists():
        return notes
    for p in sorted(root.rglob("*.md")):
        notes.append({"path": str(p.relative_to(root.parent)), "text": p.read_text(encoding="utf-8")})
    return notes
