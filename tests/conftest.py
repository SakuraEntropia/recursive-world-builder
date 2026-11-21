from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from recursive_world_builder.storage import WorldStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = PROJECT_ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def electric_store(tmp_path: Path) -> WorldStore:
    target = tmp_path / "electric_city"
    shutil.copytree(EXAMPLES / "electric_city", target)
    return WorldStore(target)


@pytest.fixture
def weird_store(tmp_path: Path) -> WorldStore:
    target = tmp_path / "weird_physics"
    shutil.copytree(EXAMPLES / "weird_physics", target)
    return WorldStore(target)


@pytest.fixture
def conflict_world_path() -> Path:
    return FIXTURES / "conflict_world" / "world.json"


@pytest.fixture
def markdown_source(tmp_path: Path) -> Path:
    target = tmp_path / "markdown_world"
    shutil.copytree(FIXTURES / "markdown_world", target)
    return target
