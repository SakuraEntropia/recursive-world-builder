"""Rule architect: propose general mechanisms, not special cases."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict

from .critic import Finding
from .model import World, Rule


@dataclass
class Proposal:
    id: str
    title: str
    problem: str
    root_cause: str
    proposed_rule: dict
    expected_impact: list[str]
    conflicts: list[str]
    tests: list[str]
    status: str = "PROPOSED"      # PROPOSED | APPROVED | REJECTED
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _new_id() -> str:
    return "P-" + uuid.uuid4().hex[:6]


def _scope_from(finding: Finding) -> list[str]:
    """Pull candidate tags out of the hypothesis text."""
    tags: list[str] = []
    for token in ("electric", "power", "water", "liquid", "metal", "insulator",
                  "human", "vehicle", "weather", "building", "animal"):
        if token in finding.hypothesis or token in finding.scenario:
            tags.append(token)
    return tags or ["general"]


def propose(world: World, finding: Finding) -> Proposal:
    """Turn a finding into a general, reusable rule proposal."""
    scope = _scope_from(finding)
    rule = Rule(
        id="R-" + uuid.uuid4().hex[:6],
        scope=scope,
        verb="touch",
        effect={"consequence": "defined_by_approval", "harm": "unknown"},
        rationale=finding.hypothesis,
        status="PROPOSED",
        depends_on=[],
    )
    conflicts = check_conflicts(world, rule)
    return Proposal(
        id=_new_id(),
        title=f"general rule for {', '.join(scope)}",
        problem=finding.observation,
        root_cause=finding.hypothesis,
        proposed_rule=asdict(rule),
        expected_impact=finding.affected_systems,
        conflicts=conflicts,
        tests=[
            f"{scope[0] if scope else 'entity'} in contact with water",
            "insulated contact",
            "vehicle strikes the fixture",
            "contact during weather",
        ],
        rationale="prefer one mechanism covering many cases over per-case patches",
    )


def check_conflicts(world: World, rule: Rule) -> list[str]:
    """Same verb and overlapping scope, with a different effect -> conflict."""
    out: list[str] = []
    for r in world.rules.values():
        if r.verb != rule.verb:
            continue
        if set(r.scope) & set(rule.scope):
            if r.effect != rule.effect:
                out.append(f"overlaps {r.id} (scope {r.scope}) with different effect")
    return out


def apply(world: World, proposal: Proposal) -> Rule:
    """Promote an approved proposal into canon."""
    if proposal.status != "APPROVED":
        raise PermissionError("proposal is not approved")
    rule = Rule(**proposal.proposed_rule)
    rule.status = "CANON"
    rule.source = proposal.id
    world.add_rule(rule)
    return rule
