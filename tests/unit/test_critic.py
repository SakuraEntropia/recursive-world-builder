from __future__ import annotations

from recursive_world_builder.critic import CausalCritic
from recursive_world_builder.engine import RuleEngine
from recursive_world_builder.model import Action, Scenario
from recursive_world_builder.storage import WorldStore


def test_undefined_interaction_finding(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(
        id="critic-undefined",
        title="Mira touches the live line",
        actor="mira",
        target="power_line",
        action=Action("touch", tags=["contact"]),
        description="A direct contact probe.",
        focus="physics",
    )
    observation = RuleEngine().simulate(world, scenario)
    finding = CausalCritic().analyze(world, scenario, observation)
    assert finding is not None
    assert finding.gap_type == "undefined_interaction"
    assert finding.recommended_action == "propose_general_rule"
    assert finding.affected_systems[0] == "electricity"
    assert finding.confidence_kind == "subjective_agent_judgment"
    assert finding.calibrated is False
    assert 0.0 <= finding.confidence <= 1.0
    assert finding.dedupe_key == "undefined_interaction:electricity"


def test_explicit_violation(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(
        id="critic-violation",
        title="Mira enters the substation",
        actor="mira",
        target="substation",
        action=Action("enter", tags=["boundary"]),
        focus="society",
    )
    observation = RuleEngine().simulate(world, scenario)
    finding = CausalCritic().analyze(world, scenario, observation)
    assert finding is not None
    assert finding.gap_type == "explicit_violation"
    assert finding.recommended_action == "review_not_error"
    assert "C-SUBSTATION-1" in finding.evidence
    assert finding.affected_systems[0] == "society"
    assert "electricity" not in finding.affected_systems


def test_allowed_but_unrealistic_does_not_patch_canon(weird_store: WorldStore) -> None:
    world = weird_store.load_world()
    scenario = Scenario(
        id="critic-gravity",
        title="Drop a coin",
        actor="coin",
        target="ground",
        action=Action("drop"),
        real_world_expectation="Objects fall at 9.8 m/s².",
        tags=["reality_check"],
        focus="physics",
    )
    observation = RuleEngine().simulate(world, scenario)
    finding = CausalCritic().analyze(world, scenario, observation)
    assert finding is not None
    assert finding.gap_type == "allowed_but_unrealistic"
    assert finding.recommended_action == "preserve_canon"
    assert finding.calibrated is False
    assert "Real-world expectation" in finding.observation


def test_defined_normal_interaction_has_no_finding(electric_store: WorldStore) -> None:
    world = electric_store.load_world()
    scenario = Scenario(
        id="critic-walk",
        title="Walk",
        actor="mira",
        action=Action("walk"),
        focus="physics",
    )
    observation = RuleEngine().simulate(world, scenario)
    finding = CausalCritic().analyze(world, scenario, observation)
    assert finding is None
