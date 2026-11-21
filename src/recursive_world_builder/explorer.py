"""Scenario generation.

Two modes:
  * deterministic probes: tag pairs that the world says can meet
  * supplied probes: cases handed in by the host agent (LLM mode)

A scenario is a dict: verbs over entities, with an intent.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, asdict
from typing import Iterable

from .model import World


@dataclass
class Scenario:
    id: str
    verb: str
    subjects: list[str]
    objects: list[str]
    intent: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


INTERACTION_VERBS = ["touch", "enter", "strike", "carry", "observe"]


def _sig(s: Scenario) -> str:
    return f"{s.verb}:{'|'.join(sorted(s.subjects))}->{'|'.join(sorted(s.objects))}"


def generate_probes(world: World, limit: int = 40) -> list[Scenario]:
    """Pair up entities that share a location, and try contact verbs.

    Deliberately dumb: the point is coverage, not realism. The critic and the
    rule architect do the thinking.
    """
    by_loc: dict[str, list] = {}
    for e in world.entities.values():
        if e.location:
            by_loc.setdefault(e.location, []).append(e)

    out: list[Scenario] = []
    seen: set[str] = set()
    for loc, ents in sorted(by_loc.items()):
        for a, b in itertools.permutations(ents, 2):
            for verb in ("touch", "enter", "strike"):
                sc = Scenario(id=f"{verb}-{a.id}-{b.id}", verb=verb,
                              subjects=[a.id], objects=[b.id], intent=f"contact in {loc}")
                sig = _sig(sc)
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(sc)
                if len(out) >= limit:
                    return out
    return out


def counterfactuals(world: World, rule_scope: Iterable[str], limit: int = 6) -> list[Scenario]:
    """Build follow-up scenarios that stress a proposed scope.

    For each pair of entities carrying two tags from the scope, propose contact.
    """
    tags = set(rule_scope)
    out: list[Scenario] = []
    seen: set[str] = set()
    ents = list(world.entities.values())
    for a, b in itertools.permutations(ents, 2):
        shared = (set(a.tags) | set(b.tags)) & tags
        if len(shared) >= 2:
            sc = Scenario(id=f"cf-{a.id}-{b.id}", verb="touch",
                          subjects=[a.id], objects=[b.id],
                          intent=f"counterfactual on scope {sorted(shared)}")
            sig = _sig(sc)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(sc)
            if len(out) >= limit:
                break
    return out
