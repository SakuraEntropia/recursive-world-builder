from __future__ import annotations

from pathlib import Path

import pytest

from recursive_world_builder.ingest import ingest_directory
from recursive_world_builder.model import (
    Entity,
    Rule,
    ValidationError,
    World,
)
from recursive_world_builder.storage import WorldStore

from ..conftest import EXAMPLES, FIXTURES


def test_load_valid_world(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    assert world.world_id == "electric_city"
    assert world.canon_version == 1
    assert len(world.entities) >= 5
    assert "mira" in world.entities
    assert "power_line" in world.entities
    assert world.validate() == []


def test_world_roundtrip(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    again = World.from_dict(world.to_dict())
    assert again.to_dict() == world.to_dict()
    assert again.canon_rules()[0].id == world.canon_rules()[0].id


def test_invalid_location_is_rejected() -> None:
    world = World(
        world_id="bad",
        title="Bad",
        entities={"x": Entity(id="x", name="X", location_id="missing")},
    )
    with pytest.raises(ValidationError, match="unknown location"):
        world.assert_valid()


def test_canon_fact_without_id_gets_a_stable_id() -> None:
    world = World.from_dict(
        {
            "world_id": "facts",
            "title": "Facts",
            "canon": [{"statement": "A statement without an id."}],
        }
    )
    assert world.canon[0].id == "CF-001"
    assert world.canon[0].statement == "A statement without an id."


def test_markdown_ingestion(markdown_source: Path) -> None:
    world = ingest_directory(markdown_source)
    assert world.title == "Markdown Test World"
    assert world.entities["tala"].properties["health"] == 50
    assert world.entities["stone"].properties["weight"] == 40
    assert world.locations["yard"].tags == ["outdoor", "test"]
    assert world.rules["r_lift_stone"].effects[1].delta == -2
    assert len(world.canon) == 2
    assert world.source_documents[0]["path"] == "notes.md"
    assert world.validate() == []


def test_rule_matcher_rejects_empty_action_types() -> None:
    rule = Rule.from_dict(
        {
            "id": "r_empty",
            "matcher": {"action_types": []},
            "effects": [{"kind": "emit_event", "event": "x"}],
        }
    )
    assert any("action_types" in error for error in rule.validate())


def test_world_fixture_files_exist() -> None:
    assert (EXAMPLES / "electric_city" / "world.json").exists()
    assert (EXAMPLES / "electric_city" / "source" / "electric_city.md").exists()
    assert (FIXTURES / "conflict_world" / "world.json").exists()


def test_yaml_world_ingestion(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    (tmp_path / "world.yaml").write_text(
        """
world_id: yaml_world
title: YAML World
locations:
  yard:
    id: yard
    name: Yard
    tags: [outdoor]
entities:
  hero:
    id: hero
    name: Hero
    type: character
    location_id: yard
    tags: [human, actor]
    properties: {health: 10}
rules:
  r_pause:
    id: r_pause
    name: Pause
    matcher:
      action_types: [wait]
      actor_tags_any: [human]
    effects:
      - kind: emit_event
        target: actor
        event: paused
""",
        encoding="utf-8",
    )
    world = ingest_directory(tmp_path)
    assert world.world_id == "yaml_world"
    assert world.entities["hero"].properties["health"] == 10
    assert world.rules["r_pause"].effects[0].event == "paused"
    assert world.validate() == []


def test_store_loads_yaml_world(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    (tmp_path / "world.yaml").write_text(
        """
world_id: yaml_store
title: YAML Store
entities:
  a:
    id: a
    name: A
    tags: [human]
    properties: {health: 1}
rules:
  r_wait:
    id: r_wait
    matcher: {action_types: [wait]}
    effects: [{kind: emit_event, event: waited}]
""",
        encoding="utf-8",
    )
    store = WorldStore(tmp_path)
    world = store.load_world()
    assert world.world_id == "yaml_store"
    assert store.world_path.name == "world.yaml"
    store.save_world(world)
    assert (tmp_path / "world.json").exists()
    assert store.load_world().world_id == "yaml_store"
