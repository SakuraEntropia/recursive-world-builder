"""World model: entities, locations, rules, canon, proposals.

Everything here is data. No physics engine, no simulation. Rules are
declarative constraints of the form: (subject tag, verb, object tag) => effect.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Entity:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    location: str | None = None


@dataclass
class Location:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    """A rule covers interactions matching (subject_tag, verb, object_tag).

    scope: list of tags that must all be present for the rule to apply.
    effect: free-form declarative consequence, e.g. {"harm": "lethal"}.
    """
    id: str
    scope: list[str]
    verb: str
    effect: dict[str, Any]
    rationale: str = ""
    status: str = "CANON"          # CANON | PROPOSED
    depends_on: list[str] = field(default_factory=list)
    source: str = ""

    def applies(self, subj_tags: set[str], verb: str, obj_tags: set[str]) -> bool:
        if self.verb != verb:
            return False
        have = subj_tags | obj_tags
        return all(tag in have for tag in self.scope)


@dataclass
class World:
    name: str
    entities: dict[str, Entity] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    rules: dict[str, Rule] = field(default_factory=dict)
    canon: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- queries ---------------------------------------------------------
    def find_by_tag(self, tag: str) -> list[Entity]:
        return [e for e in self.entities.values() if tag in e.tags]

    def rules_for(self, subj_tags: set[str], verb: str, obj_tags: set[str]) -> list[Rule]:
        return [r for r in self.rules.values() if r.applies(subj_tags, verb, obj_tags)]

    def add_rule(self, rule: Rule) -> None:
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> Rule | None:
        return self.rules.pop(rule_id, None)

    # -- serialisation ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "locations": {k: asdict(v) for k, v in self.locations.items()},
            "rules": {k: asdict(v) for k, v in self.rules.items()},
            "canon": list(self.canon),
            "constraints": list(self.constraints),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "World":
        w = cls(name=data.get("name", "untitled"))
        for k, v in data.get("entities", {}).items():
            w.entities[k] = Entity(**v)
        for k, v in data.get("locations", {}).items():
            w.locations[k] = Location(**v)
        for k, v in data.get("rules", {}).items():
            w.rules[k] = Rule(**v)
        w.canon = list(data.get("canon", []))
        w.constraints = list(data.get("constraints", []))
        w.metadata = dict(data.get("metadata", {}))
        return w

    def validate(self) -> list[str]:
        errors: list[str] = []
        for e in self.entities.values():
            if e.location and e.location not in self.locations:
                errors.append(f"entity {e.id} refers to unknown location {e.location}")
        for r in self.rules.values():
            for dep in r.depends_on:
                if dep not in self.rules:
                    errors.append(f"rule {r.id} depends on missing rule {dep}")
            if not r.scope:
                errors.append(f"rule {r.id} has empty scope")
        return errors
