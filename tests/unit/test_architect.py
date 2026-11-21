from __future__ import annotations

import json
from pathlib import Path

import pytest

from recursive_world_builder.architect import (
    ProposalConflictError,
    ProposalStateError,
    RuleArchitect,
)
from recursive_world_builder.model import (
    Action,
    PropertyCondition,
    Proposal,
    ProposalStatus,
    Rule,
    Scenario,
    ValidationError,
    World,
)


def _conflict_world(path: Path) -> World:
    return World.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _new_shock_rule() -> Rule:
    return Rule.from_dict(
        {
            "id": "r_new_shock",
            "name": "Live wires shock",
            "description": "Contact with an energized wire causes injury.",
            "domain": "physics",
            "matcher": {
                "action_types": ["touch"],
                "actor_tags_any": ["human"],
                "target_tags_any": ["energized"],
            },
            "effects": [
                {"kind": "set_property", "target": "actor", "property": "health", "value": 0},
                {"kind": "emit_event", "target": "actor", "event": "shock"},
            ],
            "status": "proposed",
        }
    )


def test_detects_direct_rule_conflict(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    conflicts = RuleArchitect().detect_conflicts(world, [_new_shock_rule()])
    assert any(item.severity == "direct" for item in conflicts)
    assert any("different values" in item.description for item in conflicts)


def test_apply_blocks_direct_conflict_without_override(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    proposal = Proposal(
        id="P-9999",
        world_id=world.world_id,
        world_version=world.canon_version,
        title="Shock",
        problem="missing shock",
        root_cause_hypothesis="no electrical rule",
        rationale="test",
        rules=[_new_shock_rule()],
        expected_impacts=["injury"],
        test_plan=[
            Scenario(
                id="t",
                title="Touch",
                actor="mira",
                target="wire",
                action=Action("touch"),
            )
        ],
        status=ProposalStatus.APPROVED.value,
        confidence=0.5,
    )
    with pytest.raises(ProposalConflictError):
        RuleArchitect().apply_proposal(world, proposal)
    assert world.canon_version == 1
    assert "r_new_shock" not in world.rules


def test_apply_requires_explicit_approval(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    proposal = Proposal(
        id="P-9998",
        world_id=world.world_id,
        world_version=world.canon_version,
        title="Shock",
        problem="missing shock",
        root_cause_hypothesis="no electrical rule",
        rationale="test",
        rules=[_new_shock_rule()],
        expected_impacts=["injury"],
        test_plan=[],
        status=ProposalStatus.PROPOSED.value,
    )
    with pytest.raises(ProposalStateError, match="approved"):
        RuleArchitect().apply_proposal(world, proposal)


def test_existing_rule_is_modified_not_duplicated(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    existing = world.rules["r_existing_safety"].to_dict()
    existing["effects"] = [
        {"kind": "set_property", "target": "actor", "property": "health", "value": 0},
        {"kind": "emit_event", "target": "actor", "event": "electric_shock"},
    ]
    payload = {
        "title": "Revise the safety axiom",
        "problem": "Existing rule makes live wires harmless.",
        "root_cause_hypothesis": "The rule is too broad.",
        "rationale": "Amend the existing rule rather than add a duplicate.",
        "expected_impacts": ["contact becomes dangerous"],
        "test_plan": [
            {
                "id": "T-MOD",
                "title": "Touch wire",
                "actor": "mira",
                "target": "wire",
                "action": {"type": "touch"},
            }
        ],
        "rules": [existing],
    }
    architect = RuleArchitect()
    proposal = architect.ingest_external_proposal(world, payload, proposal_id="P-0001")
    assert proposal.rule_changes[0].action == "modify"
    assert proposal.rule_changes[0].before["effects"][0]["value"] == 100
    assert proposal.potential_conflicts == []
    proposal.status = "approved"
    updated = architect.apply_proposal(world, proposal)
    assert updated.canon_version == 2
    assert updated.rules["r_existing_safety"].version == 2
    assert updated.rules["r_existing_safety"].effects[0].value == 0
    assert updated.history[0]["changes"][0]["action"] == "modify"


def test_deprecated_rule_cannot_be_revived_automatically(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    world.rules["r_existing_safety"].status = "deprecated"
    payload = {
        "title": "Revive old safety rule",
        "problem": "test",
        "root_cause_hypothesis": "test",
        "rationale": "test",
        "expected_impacts": ["test"],
        "test_plan": [
            {
                "id": "T-REVIVE",
                "title": "Touch",
                "actor": "mira",
                "target": "wire",
                "action": {"type": "touch"},
            }
        ],
        "rules": [world.rules["r_existing_safety"].to_dict()],
    }
    with pytest.raises(ValidationError, match="deprecated"):
        RuleArchitect().ingest_external_proposal(world, payload, proposal_id="P-0002")


def test_property_conditions_prevent_false_conflict(conflict_world_path: Path) -> None:
    world = _conflict_world(conflict_world_path)
    world.rules["r_existing_safety"].matcher.target_properties = [
        PropertyCondition(key="voltage", op="gt", value=5000)
    ]
    proposed = _new_shock_rule()
    proposed.matcher.target_properties = [PropertyCondition(key="voltage", op="lt", value=10)]
    conflicts = RuleArchitect().detect_conflicts(world, [proposed])
    assert not any(item.severity == "direct" for item in conflicts)
