from __future__ import annotations

from recursive_world_builder.engine import RuleEngine
from recursive_world_builder.model import (
    Action,
    Assumption,
    Scenario,
    World,
)
from recursive_world_builder.storage import WorldStore


def _touch(world: World, target: str = "power_line", actor: str = "mira", **kwargs) -> Scenario:
    return Scenario(
        id="test-touch",
        title="Test touch",
        actor=actor,
        target=target,
        action=Action("touch", tags=["contact"]),
        **kwargs,
    )


def test_undefined_interaction(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    observation = RuleEngine().simulate(world, _touch(world))
    assert observation.error == ""
    assert observation.matched_rule_ids == []
    assert observation.undefined_behavior is True
    assert observation.effects == []
    assert "no canonical rule" in observation.summary()


def test_existing_rule_produces_effects(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(
        id="test-collide",
        title="Car hits crate",
        actor="car",
        target="crate",
        action=Action("collide"),
    )
    observation = RuleEngine().simulate(world, scenario)
    assert observation.matched_rule_ids == ["r_collision_fragile"]
    crate_effect = next(
        effect for effect in observation.effects if effect.get("property") == "integrity"
    )
    assert crate_effect["before"] == 50
    assert crate_effect["after"] == 30
    assert "damaged" in observation.events[0].values() or any(
        effect.get("tag") == "damaged" for effect in observation.effects
    )


def test_prohibition_is_explicit_violation(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(
        id="test-prohibited",
        title="Enter the substation",
        actor="mira",
        target="substation",
        action=Action("enter"),
    )
    observation = RuleEngine().simulate(world, scenario)
    assert len(observation.violations) == 1
    assert observation.violations[0]["constraint_id"] == "C-SUBSTATION-1"
    assert observation.matched_rule_ids == []
    assert observation.undefined_behavior is False


def test_assumptions_do_not_mutate_the_world(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    baseline = world.entities["mira"].tags[:]
    scenario = _touch(
        world,
        assumptions=[Assumption("mira", add_tags=["electrically_insulated"])],
    )
    RuleEngine().simulate(world, scenario)
    assert world.entities["mira"].tags == baseline


def test_priority_suppresses_conflicting_state_write() -> None:
    world = World.from_dict(
        {
            "world_id": "priority",
            "title": "Priority",
            "locations": {"room": {"id": "room", "name": "Room", "tags": []}},
            "entities": {
                "a": {"id": "a", "name": "A", "tags": ["actor"], "properties": {"health": 10}},
                "b": {"id": "b", "name": "B", "tags": ["target"], "properties": {}},
            },
            "rules": {
                "high": {
                    "id": "high",
                    "matcher": {"action_types": ["hit"], "target_tags_any": ["target"]},
                    "effects": [
                        {
                            "kind": "set_property",
                            "target": "actor",
                            "property": "health",
                            "value": 5,
                        }
                    ],
                    "priority": 90,
                },
                "low": {
                    "id": "low",
                    "matcher": {"action_types": ["hit"], "target_tags_any": ["target"]},
                    "effects": [
                        {
                            "kind": "set_property",
                            "target": "actor",
                            "property": "health",
                            "value": 1,
                        }
                    ],
                    "priority": 10,
                },
            },
        }
    )
    scenario = Scenario(
        id="s",
        title="Hit",
        actor="a",
        target="b",
        action=Action("hit"),
    )
    observation = RuleEngine().simulate(world, scenario)
    assert observation.matched_rule_ids == ["high", "low"]
    assert observation.suppressed_rule_ids == ["low"]
    assert world.entities["a"].properties["health"] == 10
    assert observation.effects[0]["after"] == 5


def test_property_condition_matching() -> None:
    world = World.from_dict(
        {
            "world_id": "properties",
            "title": "Properties",
            "entities": {
                "a": {"id": "a", "name": "A", "tags": ["actor"], "properties": {}},
                "b": {"id": "b", "name": "B", "tags": ["target"], "properties": {"health": 3}},
            },
            "rules": {
                "r_low_health": {
                    "id": "r_low_health",
                    "matcher": {
                        "action_types": ["hit"],
                        "target_tags_any": ["target"],
                        "target_properties": [{"key": "health", "op": "lt", "value": 5}],
                    },
                    "effects": [{"kind": "emit_event", "target": "target", "event": "hit"}],
                }
            },
        }
    )
    scenario = Scenario(id="s", title="Hit", actor="a", target="b", action=Action("hit"))
    observation = RuleEngine().simulate(world, scenario)
    assert observation.matched_rule_ids == ["r_low_health"]
    world.entities["b"].properties["health"] = 9
    assert RuleEngine().simulate(world, scenario).matched_rule_ids == []


def test_explicit_entity_effect_is_sandboxed() -> None:
    world = World.from_dict(
        {
            "world_id": "sandbox",
            "title": "Sandbox",
            "entities": {
                "a": {"id": "a", "name": "A", "tags": ["actor"], "properties": {}},
                "b": {"id": "b", "name": "B", "tags": ["target"], "properties": {"integrity": 10}},
            },
            "rules": {
                "r_direct": {
                    "id": "r_direct",
                    "matcher": {"action_types": ["hit"]},
                    "effects": [
                        {"kind": "set_property", "target": "b", "property": "integrity", "value": 0}
                    ],
                }
            },
        }
    )
    scenario = Scenario(id="s", title="Hit", actor="a", target="b", action=Action("hit"))
    observation = RuleEngine().simulate(world, scenario)
    assert observation.effects[0]["after"] == 0
    assert world.entities["b"].properties["integrity"] == 10


def test_unknown_actor_has_nonempty_fingerprint(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(id="s", title="Ghost", actor="missing", action=Action("touch"))
    observation = RuleEngine().simulate(world, scenario)
    assert observation.error
    assert observation.fingerprint


def test_modifiers_stack_but_a_lower_priority_set_does_not_override() -> None:
    world = World.from_dict(
        {
            "world_id": "stack",
            "title": "Stack",
            "entities": {
                "a": {"id": "a", "name": "A", "tags": ["actor"], "properties": {"health": 100}},
                "b": {"id": "b", "name": "B", "tags": ["target"], "properties": {}},
            },
            "rules": {
                "r_high": {
                    "id": "r_high",
                    "matcher": {"action_types": ["hit"], "target_tags_any": ["target"]},
                    "effects": [
                        {
                            "kind": "modify_property",
                            "target": "actor",
                            "property": "health",
                            "delta": -10,
                        }
                    ],
                    "priority": 90,
                },
                "r_stack": {
                    "id": "r_stack",
                    "matcher": {"action_types": ["hit"], "target_tags_any": ["target"]},
                    "effects": [
                        {
                            "kind": "modify_property",
                            "target": "actor",
                            "property": "health",
                            "delta": -5,
                        }
                    ],
                    "priority": 80,
                },
                "r_set_low": {
                    "id": "r_set_low",
                    "matcher": {"action_types": ["hit"], "target_tags_any": ["target"]},
                    "effects": [
                        {
                            "kind": "set_property",
                            "target": "actor",
                            "property": "health",
                            "value": 1,
                        }
                    ],
                    "priority": 10,
                },
            },
        }
    )
    scenario = Scenario(id="s", title="Hit", actor="a", target="b", action=Action("hit"))
    observation = RuleEngine().simulate(world, scenario)
    assert observation.suppressed_rule_ids == ["r_set_low"]
    assert observation.effects[0]["after"] == 90
    assert observation.effects[1]["after"] == 85
    assert world.entities["a"].properties["health"] == 100
