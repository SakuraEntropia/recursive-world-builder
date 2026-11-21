from __future__ import annotations

from recursive_world_builder.controller import RecursiveController
from recursive_world_builder.model import ProposalStatus, RunLimits
from recursive_world_builder.storage import WorldStore


def _explore_once(store: WorldStore) -> tuple[RecursiveController, object]:
    controller = RecursiveController(store, architect_mode="scripted")
    result = controller.explore(focus="physics", max_rounds=1, max_scenarios=4, max_proposals=1)
    return controller, result


def test_load_valid_world(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    assert world.world_id == "electric_city"
    assert world.canon_version == 1
    assert len(world.entities) == 9
    assert world.validate() == []


def test_detects_undefined_interaction(electric_store: WorldStore) -> None:
    _, result = _explore_once(electric_store)
    finding = next(item for item in result.findings if item.gap_type == "undefined_interaction")
    assert finding.scenario == "Mira Vale probes Bellweather High-Voltage Line"
    assert "electricity" in finding.affected_systems
    assert finding.calibrated is False


def test_generates_structured_rule_proposal(electric_store: WorldStore) -> None:
    controller, result = _explore_once(electric_store)
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.problem
    assert proposal.root_cause_hypothesis
    assert proposal.rationale
    assert proposal.expected_impacts
    assert proposal.test_plan
    assert proposal.rule_changes
    assert proposal.confidence_kind == "subjective_agent_judgment"
    assert proposal.calibrated is False
    assert all(rule.status == "proposed" for rule in proposal.rules)
    assert {rule.id for rule in proposal.rules} == {
        "r_electric_contact_shock",
        "r_electric_insulation_grounds",
        "r_electric_medium_conduction",
        "r_impact_infrastructure_damage",
    }
    # Generality: no rule names the demo's power_line entity directly.
    for rule in proposal.rules:
        assert "power_line" not in rule.matcher.target_tags_any
        assert rule.matcher.target_tags_any
    assert controller.store.load_world().canon_version == 1
    assert "r_electric_contact_shock" not in controller.store.load_world().rules


def test_rejected_proposal_leaves_canon_unchanged(electric_store: WorldStore) -> None:
    controller, result = _explore_once(electric_store)
    before = electric_store.load_world().to_dict()
    proposal = result.proposals[0]
    rejected = controller.reject(proposal.id, "not this time")
    assert rejected.status == ProposalStatus.REJECTED.value
    after = electric_store.load_world().to_dict()
    assert after == before
    assert after["canon_version"] == 1
    assert "r_electric_contact_shock" not in after["rules"]


def test_approved_proposal_updates_canon(electric_store: WorldStore) -> None:
    controller, result = _explore_once(electric_store)
    proposal = result.proposals[0]
    approval = controller.approve(proposal.id)
    assert approval.applied is True
    assert approval.rollback_performed is False
    assert approval.world_version == 2
    assert all(item.passed for item in approval.regression_results)

    world = electric_store.load_world()
    assert world.canon_version == 2
    assert world.rules["r_electric_contact_shock"].status == "canon"
    assert world.rules["r_electric_contact_shock"].provenance["proposal_id"] == proposal.id
    assert len(world.history) == 1
    assert world.history[0]["proposal_id"] == proposal.id
    assert world.events[-1]["type"] == "rule_patch_applied"
    assert world.events[-1]["proposal_id"] == proposal.id
    stored = electric_store.find_proposal(proposal.id)
    assert stored.status == ProposalStatus.APPLIED.value

    tests = {item["scenario"]["id"]: item["observation"] for item in approval.post_tests}
    direct = tests["T-electricity-01"]
    assert any(
        effect.get("property") == "health" and effect.get("after") == 40
        for effect in direct["effects"]
    )
    insulated = tests["T-electricity-02"]
    assert not any(effect.get("property") == "health" for effect in insulated["effects"])
    water = tests["T-electricity-03"]
    assert any(effect.get("tag") == "energized" for effect in water["effects"])
    collision = tests["T-electricity-05"]
    assert any(
        effect.get("property") == "integrity" and effect.get("after") == 75
        for effect in collision["effects"]
    )
    assert approval.report_path
    from pathlib import Path

    assert Path(approval.report_path).exists()


def test_controller_stops_within_budget(electric_store: WorldStore) -> None:
    controller = RecursiveController(
        electric_store,
        limits=RunLimits(
            max_rounds=1,
            max_scenarios=1,
            max_new_rules=8,
            max_proposals=1,
            max_consecutive_empty_rounds=1,
        ),
    )
    result = controller.explore(focus="physics")
    assert result.scenarios_run <= 1
    assert len(result.rounds) <= 1
    assert result.stop_reason in {
        "max_rounds",
        "max_scenarios",
        "max_proposals",
        "max_new_rules",
        "no_new_findings",
        "no_candidate_scenarios",
    }


def test_no_new_findings_stop_condition(weird_store: WorldStore) -> None:
    controller = RecursiveController(weird_store, architect_mode="host")
    result = controller.explore(focus="physics", max_rounds=3, max_scenarios=8)
    assert result.stop_reason in {"no_candidate_scenarios", "no_new_findings", "max_rounds"}
    assert len(result.findings) == 1
    assert result.proposals == []


def test_regression_suite_remains_green_after_patch(electric_store: WorldStore) -> None:
    controller, result = _explore_once(electric_store)
    approval = controller.approve(result.proposals[0].id)
    assert approval.regression_results
    assert all(item.passed for item in approval.regression_results)
    assert {item.case_id for item in approval.regression_results} == {
        "REG-WALK-1",
        "REG-COLLISION-1",
    }


def test_failed_regression_rolls_back_canon(electric_store: WorldStore) -> None:
    # First create a normal pending proposal so the regression baseline exists.
    controller, result = _explore_once(electric_store)
    proposal = result.proposals[0]
    controller.reject(proposal.id, "superseded by the regression test")

    world = electric_store.load_world()
    walk_rule = world.rules["r_walk_street"].to_dict()
    walk_rule["effects"] = list(walk_rule["effects"]) + [
        {"kind": "set_property", "target": "actor", "property": "health", "value": 1}
    ]
    payload = {
        "title": "Regression-breaking walk mutation",
        "problem": "test-only mutation",
        "root_cause_hypothesis": "test-only mutation",
        "rationale": "This proposal intentionally changes a regression probe.",
        "expected_impacts": ["should be blocked by the regression gate"],
        "test_plan": [
            {
                "id": "T-REG-WALK",
                "title": "Walk",
                "actor": "mira",
                "action": {"type": "walk"},
            }
        ],
        "rules": [walk_rule],
        "generality": {"special_case": False, "reusable": True},
    }
    architect = controller.architect
    proposals = electric_store.load_proposals()
    bad = architect.ingest_external_proposal(
        world,
        payload,
        proposal_id=electric_store.next_proposal_id(proposals),
        existing_proposals=proposals,
    )
    electric_store.upsert_proposal(bad)

    approval = controller.approve(bad.id)
    assert approval.applied is False
    assert approval.rollback_performed is True
    assert any(not item.passed for item in approval.regression_results)
    restored = electric_store.load_world()
    assert restored.canon_version == 1
    assert [effect.to_dict() for effect in restored.rules["r_walk_street"].effects] == [
        {
            "kind": "emit_event",
            "target": "actor",
            "event": "walked",
            "message": "the actor walks through the location",
        }
    ]
    assert electric_store.find_proposal(bad.id).status == "regression_failed"
