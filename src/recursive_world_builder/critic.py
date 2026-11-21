"""Causal critic: turn observed scenarios into structured findings.

Three outcomes matter, and they are not the same:
  contradiction   - a rule applies and the world says the outcome is impossible
  undefined       - nothing in the rule set covers this interaction
  counter_intuitive - covered, but the consequence looks odd to a human reader

The third is NOT automatically a defect. Fictional physics may be strange on
purpose. It is reported separately and never auto-patched.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .explorer import Scenario
from .model import World


@dataclass
class Finding:
    scenario: str
    observation: str
    gap_type: str            # undefined_interaction | contradiction | counter_intuitive
    hypothesis: str
    confidence: float        # subjective, not calibrated
    affected_systems: list[str]
    recommended_action: str

    def to_dict(self) -> dict:
        return asdict(self)


TAG_SYSTEMS = {
    "electric": "electricity", "power": "electricity", "wired": "electricity",
    "water": "materials", "liquid": "materials", "metal": "materials",
    "insulator": "materials", "human": "health", "animal": "health",
    "vehicle": "physics", "weather": "physics", "building": "physics",
}


def systems_of(world: World, scenario: Scenario) -> list[str]:
    tags: set[str] = set()
    for eid in scenario.subjects + scenario.objects:
        e = world.entities.get(eid)
        if e:
            tags |= set(e.tags)
    systems = sorted({TAG_SYSTEMS[t] for t in tags if t in TAG_SYSTEMS})
    return systems or ["general"]


def analyse(world: World, scenario: Scenario) -> Finding | None:
    """Return a finding if the scenario is uncovered, else None."""
    subj_tags = set()
    obj_tags = set()
    for eid in scenario.subjects:
        e = world.entities.get(eid)
        if e:
            subj_tags |= set(e.tags)
    for eid in scenario.objects:
        e = world.entities.get(eid)
        if e:
            obj_tags |= set(e.tags)

    rules = world.rules_for(subj_tags, scenario.verb, obj_tags)
    if rules:
        return None

    systems = systems_of(world, scenario)
    shared = sorted((subj_tags & obj_tags) | (subj_tags | obj_tags))
    return Finding(
        scenario=f"{scenario.verb} {scenario.subjects} -> {scenario.objects}",
        observation="no rule in the world model resolves this interaction",
        gap_type="undefined_interaction",
        hypothesis=f"missing mechanism covering tags {shared}",
        confidence=0.6,
        affected_systems=systems,
        recommended_action="propose_general_rule",
    )


def find_contradictions(world: World, scenario: Scenario) -> list[Finding]:
    """A contradiction is a rule that applies but whose effect is marked impossible."""
    subj_tags: set[str] = set()
    obj_tags: set[str] = set()
    for eid in scenario.subjects:
        e = world.entities.get(eid)
        if e:
            subj_tags |= set(e.tags)
    for eid in scenario.objects:
        e = world.entities.get(eid)
        if e:
            obj_tags |= set(e.tags)

    out: list[Finding] = []
    for r in world.rules_for(subj_tags, scenario.verb, obj_tags):
        if r.effect.get("impossible") is True:
            out.append(Finding(
                scenario=f"{scenario.verb} {scenario.subjects} -> {scenario.objects}",
                observation=f"rule {r.id} applies but marks the outcome impossible",
                gap_type="contradiction",
                hypothesis="rule set is internally inconsistent",
                confidence=0.9,
                affected_systems=systems_of(world, scenario),
                recommended_action="resolve_conflict",
            ))
    return out
