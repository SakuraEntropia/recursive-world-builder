"""Core data model for Recursive World Builder.

The model is deliberately boring: explicit dataclasses, JSON-compatible
dictionaries, and validation rules.  Reasoning about a fictional world belongs
to the host agent; this module only stores and checks the resulting structure.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Domain(StrEnum):
    PHYSICS = "physics"
    BIOLOGY = "biology"
    SOCIETY = "society"
    ECONOMY = "economy"
    CHARACTER = "character"
    GENERAL = "general"


class GapType(StrEnum):
    UNDEFINED_INTERACTION = "undefined_interaction"
    EXPLICIT_VIOLATION = "explicit_violation"
    ALLOWED_BUT_UNREALISTIC = "allowed_but_unrealistic"
    RULE_CONFLICT = "rule_conflict"
    MISSING_PRECONDITION = "missing_precondition"


class Recommendation(StrEnum):
    PROPOSE_GENERAL_RULE = "propose_general_rule"
    REVIEW_NOT_ERROR = "review_not_error"
    PRESERVE_CANON = "preserve_canon"
    FIX_SCENARIO = "fix_scenario"
    REVIEW_CONFLICT = "review_conflict"
    NO_ACTION = "no_action"


class RuleStatus(StrEnum):
    CANON = "canon"
    PROPOSED = "proposed"
    DEPRECATED = "deprecated"


class ProposalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    REGRESSION_FAILED = "regression_failed"


class ConflictSeverity(StrEnum):
    DIRECT = "direct"
    POTENTIAL = "potential"


class ValidationError(ValueError):
    """Raised when a world or proposal is structurally invalid."""

    def __init__(self, errors: list[str] | str):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        super().__init__("; ".join(errors))


def _tag_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce(value: str) -> Any:
    text = value.strip()
    lowered = text.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text.strip("\"'")


def _normalize_collection(
    value: Any, kind: str, *, id_hint: str | None = None
) -> dict[str, dict[str, Any]]:
    """Accept either a mapping or a list, return an id-keyed mapping.

    Duplicate IDs in list form are rejected instead of silently overwritten.
    """

    if value is None:
        return {}
    items: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(item, dict):
                raise ValidationError(f"{kind}.{key} must be an object")
            items.append((str(key), item))
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                raise ValidationError(f"Each {kind} entry must be an object")
            items.append((None, item))
    else:
        raise ValidationError(f"{kind} must be a list or object")

    result: dict[str, dict[str, Any]] = {}
    for key, item in items:
        item_id = str(item.get("id") or key or "").strip()
        if not item_id:
            raise ValidationError(f"Every {kind} entry needs an id")
        if item_id in result:
            raise ValidationError(f"Duplicate {kind} id: {item_id}")
        data = dict(item)
        data["id"] = item_id
        result[item_id] = data
    return result


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, [], {}, "")}


def _props(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("properties must be an object")
    return dict(value)


@dataclass(slots=True)
class PropertyCondition:
    key: str
    op: str = "eq"
    value: Any = True
    entity: str = "target"

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {"entity": self.entity, "key": self.key, "op": self.op, "value": self.value}
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PropertyCondition:
        if "key" not in data:
            raise ValidationError("Property condition needs a key")
        return cls(
            key=str(data["key"]),
            op=str(data.get("op", "eq")),
            value=data.get("value", True),
            entity=str(data.get("entity", "target")),
        )

    def evaluate(self, actual: Any) -> bool:
        op = self.op
        if op in {"eq", "=="}:
            return actual == self.value
        if op in {"ne", "!="}:
            return actual != self.value
        if op == "exists":
            return (actual is not None) == bool(self.value)
        if op == "truthy":
            return bool(actual) == bool(self.value)
        if op in {"gt", ">", "gte", ">=", "lt", "<", "lte", "<="}:
            if actual is None:
                return False
            try:
                left = float(actual)
                right = float(self.value)
            except (TypeError, ValueError):
                return False
            return {
                "gt": left > right,
                ">": left > right,
                "gte": left >= right,
                ">=": left >= right,
                "lt": left < right,
                "<": left < right,
                "lte": left <= right,
                "<=": left <= right,
            }[op]
        if op == "in":
            return actual in self.value if isinstance(self.value, (list, tuple, set)) else False
        if op == "contains":
            return self.value in actual if actual is not None else False
        raise ValidationError(f"Unknown property operator: {op}")

    def describe(self) -> str:
        return f"{self.entity}.{self.key} {self.op} {self.value!r}"


@dataclass(slots=True)
class RuleMatcher:
    action_types: list[str] = field(default_factory=list)
    actor_tags_any: list[str] = field(default_factory=list)
    actor_tags_none: list[str] = field(default_factory=list)
    target_tags_any: list[str] = field(default_factory=list)
    target_tags_none: list[str] = field(default_factory=list)
    location_tags_any: list[str] = field(default_factory=list)
    location_tags_none: list[str] = field(default_factory=list)
    actor_properties: list[PropertyCondition] = field(default_factory=list)
    target_properties: list[PropertyCondition] = field(default_factory=list)
    location_properties: list[PropertyCondition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "action_types": self.action_types,
                "actor_tags_any": self.actor_tags_any,
                "actor_tags_none": self.actor_tags_none,
                "target_tags_any": self.target_tags_any,
                "target_tags_none": self.target_tags_none,
                "location_tags_any": self.location_tags_any,
                "location_tags_none": self.location_tags_none,
                "actor_properties": [item.to_dict() for item in self.actor_properties],
                "target_properties": [item.to_dict() for item in self.target_properties],
                "location_properties": [item.to_dict() for item in self.location_properties],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RuleMatcher:
        data = data or {}
        conditions = []
        for raw in data.get("properties", []):
            condition = PropertyCondition.from_dict(raw)
            if condition.entity not in {"actor", "target", "location"}:
                raise ValidationError(
                    "Rule property condition entity must be actor/target/location"
                )
            conditions.append(condition)
        actor_props = [
            PropertyCondition.from_dict(item) for item in data.get("actor_properties", [])
        ]
        target_props = [
            PropertyCondition.from_dict(item) for item in data.get("target_properties", [])
        ]
        location_props = [
            PropertyCondition.from_dict(item) for item in data.get("location_properties", [])
        ]
        for condition in conditions:
            if condition.entity == "actor":
                actor_props.append(condition)
            elif condition.entity == "target":
                target_props.append(condition)
            else:
                location_props.append(condition)
        return cls(
            action_types=_tag_list(data.get("action_types") or data.get("actions")),
            actor_tags_any=_tag_list(data.get("actor_tags_any") or data.get("actor_tags")),
            actor_tags_none=_tag_list(data.get("actor_tags_none")),
            target_tags_any=_tag_list(data.get("target_tags_any") or data.get("target_tags")),
            target_tags_none=_tag_list(data.get("target_tags_none")),
            location_tags_any=_tag_list(data.get("location_tags_any")),
            location_tags_none=_tag_list(data.get("location_tags_none")),
            actor_properties=actor_props,
            target_properties=target_props,
            location_properties=location_props,
        )

    @property
    def specificity(self) -> int:
        return (
            len(self.actor_tags_any)
            + len(self.actor_tags_none)
            + len(self.target_tags_any)
            + len(self.target_tags_none)
            + len(self.location_tags_any)
            + len(self.location_tags_none)
            + len(self.actor_properties)
            + len(self.target_properties)
            + len(self.location_properties)
        )

    @staticmethod
    def _tag_overlap(one: list[str], other: list[str]) -> bool:
        # An empty "any" list is a wildcard.
        if not one or not other:
            return True
        return bool(set(one) & set(other))

    @staticmethod
    def _condition_bounds(condition: PropertyCondition) -> tuple[float, float] | None:
        try:
            value = float(condition.value)
        except (TypeError, ValueError):
            return None
        if condition.op in {"eq", "=="}:
            return (value, value)
        if condition.op in {"gt", ">"}:
            return (value, float("inf"))
        if condition.op in {"gte", ">="}:
            return (value, float("inf"))
        if condition.op in {"lt", "<"}:
            return (float("-inf"), value)
        if condition.op in {"lte", "<="}:
            return (float("-inf"), value)
        return None

    @classmethod
    def _conditions_overlap(
        cls, one: list[PropertyCondition], other: list[PropertyCondition]
    ) -> bool:
        for left in one:
            for right in other:
                if left.key != right.key:
                    continue
                if (
                    left.op in {"eq", "=="}
                    and right.op in {"eq", "=="}
                    and left.value != right.value
                ):
                    return False
                if left.op == "exists" and right.op == "exists":
                    if left.value != right.value:
                        return False
                    continue
                if (left.op == "exists" and left.value is False) or (
                    right.op == "exists" and right.value is False
                ):
                    # One matcher requires a property to be absent, the other
                    # constrains it. Be conservative and treat them as disjoint.
                    return False
                left_bounds = cls._condition_bounds(left)
                right_bounds = cls._condition_bounds(right)
                if (
                    left_bounds
                    and right_bounds
                    and (left_bounds[1] < right_bounds[0] or right_bounds[1] < left_bounds[0])
                ):
                    return False
        return True

    def overlaps(self, other: RuleMatcher) -> bool:
        if (
            self.action_types
            and other.action_types
            and not set(self.action_types) & set(other.action_types)
        ):
            return False
        if not self._tag_overlap(self.actor_tags_any, other.actor_tags_any):
            return False
        if not self._tag_overlap(self.target_tags_any, other.target_tags_any):
            return False
        if not self._tag_overlap(self.location_tags_any, other.location_tags_any):
            return False
        if not self._conditions_overlap(self.actor_properties, other.actor_properties):
            return False
        if not self._conditions_overlap(self.target_properties, other.target_properties):
            return False
        if not self._conditions_overlap(self.location_properties, other.location_properties):
            return False
        # A required tag that the other matcher explicitly excludes is a contradiction.
        if set(other.actor_tags_none) & set(self.actor_tags_any):
            return False
        if set(self.actor_tags_none) & set(other.actor_tags_any):
            return False
        if set(other.target_tags_none) & set(self.target_tags_any):
            return False
        if set(self.target_tags_none) & set(other.target_tags_any):
            return False
        if set(other.location_tags_none) & set(self.location_tags_any):
            return False
        return not (set(self.location_tags_none) & set(other.location_tags_any))

    def matches(
        self,
        action_type: str,
        actor: Entity | None,
        target: Entity | None,
        location: Location | None,
    ) -> bool:
        if self.action_types and action_type not in self.action_types:
            return False
        actor_tags = set(actor.tags if actor else [])
        target_tags = set(target.tags if target else [])
        location_tags = set(location.tags if location else [])
        if self.actor_tags_any and not actor_tags & set(self.actor_tags_any):
            return False
        if actor_tags & set(self.actor_tags_none):
            return False
        if self.target_tags_any and not target_tags & set(self.target_tags_any):
            return False
        if target_tags & set(self.target_tags_none):
            return False
        if self.location_tags_any and not location_tags & set(self.location_tags_any):
            return False
        if location_tags & set(self.location_tags_none):
            return False
        checks = (
            (self.actor_properties, actor),
            (self.target_properties, target),
            (self.location_properties, location),
        )
        for conditions, entity in checks:
            for condition in conditions:
                actual = entity.properties.get(condition.key) if entity else None
                if not condition.evaluate(actual):
                    return False
        return True


@dataclass(slots=True)
class Effect:
    kind: str
    target: str = "actor"
    property: str | None = None
    value: Any = None
    delta: float | None = None
    tag: str | None = None
    event: str | None = None
    message: str = ""

    VALID_KINDS = {
        "set_property",
        "modify_property",
        "add_tag",
        "remove_tag",
        "emit_event",
        "move_entity",
    }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.kind not in self.VALID_KINDS:
            errors.append(f"Unknown effect kind: {self.kind}")
        if self.kind in {"set_property", "modify_property"} and not self.property:
            errors.append(f"{self.kind} effect needs a property")
        if self.kind == "set_property" and self.value is None:
            errors.append("set_property effect needs a non-null value")
        if self.kind == "modify_property" and self.delta is None:
            errors.append("modify_property effect needs a delta")
        if self.kind in {"add_tag", "remove_tag"} and not self.tag:
            errors.append(f"{self.kind} effect needs a tag")
        if self.kind == "emit_event" and not (self.event or self.message):
            errors.append("emit_event effect needs an event or message")
        if self.kind == "move_entity" and not self.property:
            errors.append("move_entity effect needs a destination in property")
        return errors

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind, "target": self.target}
        if self.property:
            data["property"] = self.property
        if self.value is not None:
            data["value"] = self.value
        if self.delta is not None:
            data["delta"] = self.delta
        if self.tag:
            data["tag"] = self.tag
        if self.event:
            data["event"] = self.event
        if self.message:
            data["message"] = self.message
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Effect:
        return cls(
            kind=str(data.get("kind", "")),
            target=str(data.get("target", "actor")),
            property=str(data["property"]) if data.get("property") is not None else None,
            value=data.get("value"),
            delta=data.get("delta"),
            tag=str(data["tag"]) if data.get("tag") is not None else None,
            event=str(data["event"]) if data.get("event") is not None else None,
            message=str(data.get("message", "")),
        )

    def describe(self) -> str:
        if self.kind in {"set_property", "modify_property"}:
            operator = "=" if self.kind == "set_property" else "+="
            change = self.value if self.kind == "set_property" else self.delta
            return f"{self.kind} {self.target}.{self.property} {operator} {change!r}"
        if self.kind in {"add_tag", "remove_tag"}:
            return f"{self.kind} {self.target}:{self.tag}"
        if self.kind == "emit_event":
            return f"event {self.event or self.message} on {self.target}"
        return f"{self.kind} {self.target} -> {self.property}"


@dataclass(slots=True)
class Rule:
    id: str
    name: str
    description: str
    domain: str = Domain.GENERAL.value
    matcher: RuleMatcher = field(default_factory=RuleMatcher)
    effects: list[Effect] = field(default_factory=list)
    priority: int = 50
    status: str = RuleStatus.CANON.value
    version: int = 1
    depends_on: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    defies_real_world_expectation: bool = False
    rationale: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "domain": self.domain,
                "matcher": self.matcher.to_dict(),
                "effects": [effect.to_dict() for effect in self.effects],
                "priority": self.priority,
                "status": self.status,
                "version": self.version,
                "depends_on": self.depends_on,
                "conflicts_with": self.conflicts_with,
                "supersedes": self.supersedes,
                "tags": self.tags,
                "defies_real_world_expectation": self.defies_real_world_expectation,
                "rationale": self.rationale,
                "provenance": self.provenance,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        rule_id = str(data.get("id", "")).strip()
        if not rule_id:
            raise ValidationError("Rule needs an id")
        raw_effects = data.get("effects", [])
        if not isinstance(raw_effects, list):
            raise ValidationError(f"Rule {rule_id}: effects must be a list")
        return cls(
            id=rule_id,
            name=str(data.get("name") or rule_id),
            description=str(data.get("description", "")),
            domain=str(data.get("domain", Domain.GENERAL.value)),
            matcher=RuleMatcher.from_dict(data.get("matcher") or data.get("when")),
            effects=[Effect.from_dict(item) for item in raw_effects],
            priority=int(data.get("priority", 50)),
            status=str(data.get("status", RuleStatus.CANON.value)),
            version=int(data.get("version", 1)),
            depends_on=_tag_list(data.get("depends_on")),
            conflicts_with=_tag_list(data.get("conflicts_with")),
            supersedes=_tag_list(data.get("supersedes")),
            tags=_tag_list(data.get("tags")),
            defies_real_world_expectation=bool(data.get("defies_real_world_expectation", False)),
            rationale=str(data.get("rationale", "")),
            provenance=dict(data.get("provenance", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.matcher.action_types:
            errors.append(f"Rule {self.id}: matcher.action_types cannot be empty")
        for kind in (self.domain,):
            if kind not in {item.value for item in Domain}:
                errors.append(f"Rule {self.id}: unknown domain {kind!r}")
        if self.status not in {item.value for item in RuleStatus}:
            errors.append(f"Rule {self.id}: unknown status {self.status!r}")
        if not self.effects:
            errors.append(f"Rule {self.id}: at least one effect is required")
        for effect in self.effects:
            errors.extend(f"Rule {self.id}: {error}" for error in effect.validate())
        if self.priority < 0:
            errors.append(f"Rule {self.id}: priority must be >= 0")
        return errors

    def sort_key(self) -> tuple[int, int, str]:
        return (-self.priority, -self.matcher.specificity, self.id)

    @property
    def is_canon(self) -> bool:
        return self.status == RuleStatus.CANON.value


@dataclass(slots=True)
class Entity:
    id: str
    name: str
    type: str = "object"
    location_id: str = ""
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "name": self.name,
                "type": self.type,
                "location_id": self.location_id,
                "tags": self.tags,
                "properties": self.properties,
                "description": self.description,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], id_hint: str | None = None) -> Entity:
        entity_id = str(data.get("id") or id_hint or "").strip()
        if not entity_id:
            raise ValidationError("Entity needs an id")
        return cls(
            id=entity_id,
            name=str(data.get("name") or entity_id),
            type=str(data.get("type", "object")),
            location_id=str(data.get("location_id") or data.get("location") or ""),
            tags=_tag_list(data.get("tags")),
            properties=_props(data.get("properties")),
            description=str(data.get("description", "")),
        )


@dataclass(slots=True)
class Location:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "name": self.name,
                "tags": self.tags,
                "properties": self.properties,
                "description": self.description,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], id_hint: str | None = None) -> Location:
        location_id = str(data.get("id") or id_hint or "").strip()
        if not location_id:
            raise ValidationError("Location needs an id")
        return cls(
            id=location_id,
            name=str(data.get("name") or location_id),
            tags=_tag_list(data.get("tags")),
            properties=_props(data.get("properties")),
            description=str(data.get("description", "")),
        )


@dataclass(slots=True)
class Relationship:
    id: str
    source_id: str
    target_id: str
    kind: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "source_id": self.source_id,
                "target_id": self.target_id,
                "kind": self.kind,
                "properties": self.properties,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], id_hint: str | None = None) -> Relationship:
        rel_id = str(data.get("id") or id_hint or "").strip()
        if not rel_id:
            raise ValidationError("Relationship needs an id")
        source = str(data.get("source_id") or data.get("source") or "")
        target = str(data.get("target_id") or data.get("target") or "")
        if not source or not target:
            raise ValidationError(f"Relationship {rel_id}: source_id and target_id are required")
        return cls(
            id=rel_id,
            source_id=source,
            target_id=target,
            kind=str(data.get("kind", "related_to")),
            properties=_props(data.get("properties")),
        )


@dataclass(slots=True)
class Constraint:
    id: str
    description: str
    kind: str = "axiom"  # axiom | prohibition | invariant
    severity: str = "hard"  # hard | soft
    matcher: RuleMatcher | None = None
    message: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "description": self.description,
                "kind": self.kind,
                "severity": self.severity,
                "matcher": self.matcher.to_dict() if self.matcher else None,
                "message": self.message,
                "source": self.source,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], id_hint: str | None = None) -> Constraint:
        constraint_id = str(data.get("id") or id_hint or "").strip()
        if not constraint_id:
            raise ValidationError("Constraint needs an id")
        kind = str(data.get("kind", "axiom"))
        if kind not in {"axiom", "prohibition", "invariant"}:
            raise ValidationError(f"Constraint {constraint_id}: unknown kind {kind!r}")
        severity = str(data.get("severity", "hard"))
        if severity not in {"hard", "soft"}:
            raise ValidationError(f"Constraint {constraint_id}: severity must be hard or soft")
        matcher = RuleMatcher.from_dict(data.get("matcher")) if data.get("matcher") else None
        if kind == "prohibition" and (not matcher or not matcher.action_types):
            raise ValidationError(f"Constraint {constraint_id}: prohibition needs action matcher")
        return cls(
            id=constraint_id,
            description=str(data.get("description", "")),
            kind=kind,
            severity=severity,
            matcher=matcher,
            message=str(data.get("message", "")),
            source=str(data.get("source", "")),
        )


@dataclass(slots=True)
class CanonFact:
    id: str
    statement: str
    status: str = "canon"  # canon | retired
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "statement": self.statement,
                "status": self.status,
                "source": self.source,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], id_hint: str | None = None) -> CanonFact:
        fact_id = str(data.get("id") or id_hint or "").strip()
        if not fact_id:
            raise ValidationError("Canon fact needs an id")
        status = str(data.get("status", "canon"))
        if status not in {"canon", "retired"}:
            raise ValidationError(f"Canon fact {fact_id}: status must be canon or retired")
        return cls(
            id=fact_id,
            statement=str(data.get("statement", "")),
            status=status,
            source=str(data.get("source", "")),
        )


@dataclass(slots=True)
class Action:
    type: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "type": self.type,
                "tags": self.tags,
                "description": self.description,
                "parameters": self.parameters,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> Action:
        if isinstance(data, str):
            return cls(type=data)
        action_type = str(data.get("type") or data.get("action_type") or "").strip()
        if not action_type:
            raise ValidationError("Action needs a type")
        return cls(
            type=action_type,
            tags=_tag_list(data.get("tags")),
            description=str(data.get("description", "")),
            parameters=dict(data.get("parameters", {})),
        )


@dataclass(slots=True)
class Assumption:
    """Temporary setup applied only inside a counterfactual scenario."""

    entity_id: str
    add_tags: list[str] = field(default_factory=list)
    remove_tags: list[str] = field(default_factory=list)
    set_properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "entity_id": self.entity_id,
                "add_tags": self.add_tags,
                "remove_tags": self.remove_tags,
                "set_properties": self.set_properties,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assumption:
        entity_id = str(data.get("entity_id") or data.get("entity") or "").strip()
        if not entity_id:
            raise ValidationError("Assumption needs an entity_id")
        return cls(
            entity_id=entity_id,
            add_tags=_tag_list(data.get("add_tags")),
            remove_tags=_tag_list(data.get("remove_tags")),
            set_properties=_props(data.get("set_properties")),
        )


@dataclass(slots=True)
class Scenario:
    id: str
    title: str
    actor: str
    action: Action
    target: str | None = None
    description: str = ""
    focus: str = Domain.GENERAL.value
    tags: list[str] = field(default_factory=list)
    real_world_expectation: str = ""
    source: str = "generated"
    assumptions: list[Assumption] = field(default_factory=list)

    def key(self) -> str:
        assumption_key = "|".join(
            f"{item.entity_id}:"
            f"{','.join(sorted(item.add_tags))}:"
            f"{','.join(sorted(item.remove_tags))}:"
            f"{','.join(f'{key}={value}' for key, value in sorted(item.set_properties.items()))}"
            for item in self.assumptions
        )
        return f"{self.action.type}:{self.actor}:{self.target or '-'}:{assumption_key}"

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "title": self.title,
                "actor": self.actor,
                "target": self.target,
                "action": self.action.to_dict(),
                "description": self.description,
                "focus": self.focus,
                "tags": self.tags,
                "real_world_expectation": self.real_world_expectation,
                "source": self.source,
                "assumptions": [item.to_dict() for item in self.assumptions],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        scenario_id = str(data.get("id", "")).strip()
        if not scenario_id:
            raise ValidationError("Scenario needs an id")
        actor = str(data.get("actor", "")).strip()
        if not actor:
            raise ValidationError(f"Scenario {scenario_id}: actor is required")
        return cls(
            id=scenario_id,
            title=str(data.get("title") or scenario_id),
            actor=actor,
            action=Action.from_dict(data.get("action", {})),
            target=str(data["target"]) if data.get("target") else None,
            description=str(data.get("description", "")),
            focus=str(data.get("focus", Domain.GENERAL.value)),
            tags=_tag_list(data.get("tags")),
            real_world_expectation=str(data.get("real_world_expectation", "")),
            source=str(data.get("source", "external")),
            assumptions=[Assumption.from_dict(item) for item in data.get("assumptions", [])],
        )


@dataclass(slots=True)
class Observation:
    scenario_id: str
    actor_id: str
    target_id: str | None
    matched_rule_ids: list[str] = field(default_factory=list)
    suppressed_rule_ids: list[str] = field(default_factory=list)
    effects: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    constraint_violations: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    fingerprint: str = ""
    error: str = ""

    @property
    def undefined_behavior(self) -> bool:
        return not self.matched_rule_ids and not self.violations and not self.error

    def summary(self) -> str:
        if self.error:
            return f"scenario could not run: {self.error}"
        if self.violations:
            descriptions = "; ".join(item.get("description", "") for item in self.violations)
            return f"prohibited by world constraints: {descriptions}"
        if not self.matched_rule_ids:
            return "no canonical rule defines a consequence for this interaction"
        parts = []
        for effect in self.effects:
            if effect.get("kind") == "emit_event":
                parts.append(f"event {effect.get('event') or effect.get('message')}")
            elif effect.get("property"):
                parts.append(
                    f"{effect.get('target_id')}.{effect['property']} "
                    f"{effect.get('before')!r} -> {effect.get('after')!r}"
                )
            elif effect.get("tag"):
                parts.append(f"{effect.get('target_id')} tag {effect['tag']}")
        return "; ".join(parts) or "rules matched without visible state changes"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "matched_rule_ids": self.matched_rule_ids,
            "suppressed_rule_ids": self.suppressed_rule_ids,
            "effects": self.effects,
            "events": self.events,
            "violations": self.violations,
            "constraint_violations": self.constraint_violations,
            "notes": self.notes,
            "fingerprint": self.fingerprint,
            "error": self.error,
            "summary": self.summary(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Observation:
        return cls(
            scenario_id=str(data.get("scenario_id", "")),
            actor_id=str(data.get("actor_id", "")),
            target_id=data.get("target_id"),
            matched_rule_ids=list(data.get("matched_rule_ids", [])),
            suppressed_rule_ids=list(data.get("suppressed_rule_ids", [])),
            effects=list(data.get("effects", [])),
            events=list(data.get("events", [])),
            violations=list(data.get("violations", [])),
            constraint_violations=list(data.get("constraint_violations", [])),
            notes=list(data.get("notes", [])),
            fingerprint=str(data.get("fingerprint", "")),
            error=str(data.get("error", "")),
        )


@dataclass(slots=True)
class GapFinding:
    scenario_id: str
    scenario: str
    observation: str
    gap_type: str
    hypothesis: str
    confidence: float
    affected_systems: list[str]
    recommended_action: str
    matched_rule_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    dedupe_key: str = ""
    focus: str = Domain.GENERAL.value
    confidence_kind: str = "subjective_agent_judgment"
    calibrated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario": self.scenario,
            "observation": self.observation,
            "gap_type": self.gap_type,
            "hypothesis": self.hypothesis,
            "confidence": self.confidence,
            "confidence_kind": self.confidence_kind,
            "calibrated": self.calibrated,
            "affected_systems": self.affected_systems,
            "recommended_action": self.recommended_action,
            "matched_rule_ids": self.matched_rule_ids,
            "evidence": self.evidence,
            "dedupe_key": self.dedupe_key,
            "focus": self.focus,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GapFinding:
        return cls(
            scenario_id=str(data.get("scenario_id", "")),
            scenario=str(data.get("scenario", "")),
            observation=str(data.get("observation", "")),
            gap_type=str(data.get("gap_type", "")),
            hypothesis=str(data.get("hypothesis", "")),
            confidence=float(data.get("confidence", 0.0)),
            affected_systems=list(data.get("affected_systems", [])),
            recommended_action=str(data.get("recommended_action", "")),
            matched_rule_ids=list(data.get("matched_rule_ids", [])),
            evidence=list(data.get("evidence", [])),
            dedupe_key=str(data.get("dedupe_key", "")),
            focus=str(data.get("focus", Domain.GENERAL.value)),
            confidence_kind=str(data.get("confidence_kind", "subjective_agent_judgment")),
            calibrated=bool(data.get("calibrated", False)),
        )


@dataclass(slots=True)
class Conflict:
    id: str
    severity: str
    kind: str
    description: str
    rule_ids: list[str] = field(default_factory=list)
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "severity": self.severity,
                "kind": self.kind,
                "description": self.description,
                "rule_ids": self.rule_ids,
                "resolution": self.resolution,
            }
        )


@dataclass(slots=True)
class RuleChange:
    action: str  # add | modify
    rule_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "action": self.action,
                "rule_id": self.rule_id,
                "before": self.before,
                "after": self.after,
                "reason": self.reason,
            }
        )


@dataclass(slots=True)
class Proposal:
    id: str
    world_id: str
    world_version: int
    title: str
    problem: str
    root_cause_hypothesis: str
    rationale: str
    findings: list[GapFinding] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    rule_changes: list[RuleChange] = field(default_factory=list)
    expected_impacts: list[str] = field(default_factory=list)
    affected_systems: list[str] = field(default_factory=list)
    potential_conflicts: list[Conflict] = field(default_factory=list)
    test_plan: list[Scenario] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    generality: dict[str, Any] = field(default_factory=dict)
    status: str = ProposalStatus.PROPOSED.value
    confidence: float = 0.5
    confidence_kind: str = "subjective_agent_judgment"
    calibrated: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    decision: dict[str, Any] = field(default_factory=dict)
    applied_version: int | None = None
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "world_id": self.world_id,
            "world_version": self.world_version,
            "title": self.title,
            "problem": self.problem,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "rationale": self.rationale,
            "findings": [finding.to_dict() for finding in self.findings],
            "rules": [rule.to_dict() for rule in self.rules],
            "rule_changes": [change.to_dict() for change in self.rule_changes],
            "expected_impacts": self.expected_impacts,
            "affected_systems": self.affected_systems,
            "potential_conflicts": [conflict.to_dict() for conflict in self.potential_conflicts],
            "test_plan": [scenario.to_dict() for scenario in self.test_plan],
            "dependencies": self.dependencies,
            "generality": self.generality,
            "status": self.status,
            "confidence": self.confidence,
            "confidence_kind": self.confidence_kind,
            "calibrated": self.calibrated,
            "provenance": self.provenance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision": self.decision,
            "applied_version": self.applied_version,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        proposal_id = str(data.get("id", "")).strip()
        if not proposal_id:
            raise ValidationError("Proposal needs an id")
        return cls(
            id=proposal_id,
            world_id=str(data.get("world_id", "")),
            world_version=int(data.get("world_version", 0)),
            title=str(data.get("title") or proposal_id),
            problem=str(data.get("problem", "")),
            root_cause_hypothesis=str(data.get("root_cause_hypothesis", "")),
            rationale=str(data.get("rationale", "")),
            findings=[GapFinding.from_dict(item) for item in data.get("findings", [])],
            rules=[Rule.from_dict(item) for item in data.get("rules", [])],
            rule_changes=[
                RuleChange(
                    action=str(item.get("action", "add")),
                    rule_id=str(item.get("rule_id", "")),
                    before=item.get("before"),
                    after=item.get("after"),
                    reason=str(item.get("reason", "")),
                )
                for item in data.get("rule_changes", [])
            ],
            expected_impacts=list(data.get("expected_impacts", [])),
            affected_systems=list(data.get("affected_systems", [])),
            potential_conflicts=[
                Conflict(
                    id=str(item.get("id", "")),
                    severity=str(item.get("severity", ConflictSeverity.POTENTIAL.value)),
                    kind=str(item.get("kind", "")),
                    description=str(item.get("description", "")),
                    rule_ids=list(item.get("rule_ids", [])),
                    resolution=str(item.get("resolution", "")),
                )
                for item in data.get("potential_conflicts", [])
            ],
            test_plan=[Scenario.from_dict(item) for item in data.get("test_plan", [])],
            dependencies=_tag_list(data.get("dependencies")),
            generality=dict(data.get("generality", {})),
            status=str(data.get("status", ProposalStatus.PROPOSED.value)),
            confidence=float(data.get("confidence", 0.5)),
            confidence_kind=str(data.get("confidence_kind", "subjective_agent_judgment")),
            calibrated=bool(data.get("calibrated", False)),
            provenance=dict(data.get("provenance", {})),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            decision=dict(data.get("decision", {})),
            applied_version=data.get("applied_version"),
            last_error=str(data.get("last_error", "")),
        )


@dataclass(slots=True)
class RegressionCase:
    scenario: Scenario
    expected_fingerprint: str
    expected_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "expected_fingerprint": self.expected_fingerprint,
            "expected_summary": self.expected_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegressionCase:
        return cls(
            scenario=Scenario.from_dict(data.get("scenario", {})),
            expected_fingerprint=str(data.get("expected_fingerprint", "")),
            expected_summary=str(data.get("expected_summary", "")),
        )


@dataclass(slots=True)
class RegressionResult:
    case_id: str
    passed: bool
    expected_fingerprint: str
    actual_fingerprint: str
    expected_summary: str = ""
    actual_summary: str = ""
    diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "expected_fingerprint": self.expected_fingerprint,
            "actual_fingerprint": self.actual_fingerprint,
            "expected_summary": self.expected_summary,
            "actual_summary": self.actual_summary,
            "diff": self.diff,
        }


@dataclass(slots=True)
class World:
    world_id: str
    title: str
    description: str = ""
    schema_version: str = SCHEMA_VERSION
    canon_version: int = 1
    entities: dict[str, Entity] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    rules: dict[str, Rule] = field(default_factory=dict)
    constraints: dict[str, Constraint] = field(default_factory=dict)
    canon: list[CanonFact] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    regression_suite: list[Scenario] = field(default_factory=list)
    source_documents: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "world_id": self.world_id,
            "title": self.title,
            "description": self.description,
            "canon_version": self.canon_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "settings": self.settings,
            "entities": {key: value.to_dict() for key, value in self.entities.items()},
            "locations": {key: value.to_dict() for key, value in self.locations.items()},
            "relationships": {key: value.to_dict() for key, value in self.relationships.items()},
            "rules": {key: value.to_dict() for key, value in self.rules.items()},
            "constraints": {key: value.to_dict() for key, value in self.constraints.items()},
            "canon": [fact.to_dict() for fact in self.canon],
            "events": self.events,
            "regression_suite": [scenario.to_dict() for scenario in self.regression_suite],
            "source_documents": self.source_documents,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> World:
        if not isinstance(data, dict):
            raise ValidationError("World document must be an object")
        schema_version = str(data.get("schema_version", SCHEMA_VERSION))
        if schema_version.split(".", 1)[0] != SCHEMA_VERSION.split(".", 1)[0]:
            raise ValidationError(
                f"Unsupported schema_version {schema_version!r}; expected {SCHEMA_VERSION}.x"
            )
        world_id = str(data.get("world_id") or data.get("id") or "").strip()
        if not world_id:
            raise ValidationError("World needs a world_id")
        entity_data = _normalize_collection(data.get("entities"), "entities")
        location_data = _normalize_collection(data.get("locations"), "locations")
        relationship_data = _normalize_collection(data.get("relationships"), "relationships")
        rule_data = _normalize_collection(data.get("rules"), "rules")
        constraint_data = _normalize_collection(data.get("constraints"), "constraints")

        raw_canon = data.get("canon", [])
        if isinstance(raw_canon, dict):
            raw_canon = raw_canon.get("facts", [])
        canon: list[CanonFact] = []
        seen_facts: set[str] = set()
        for index, item in enumerate(raw_canon):
            fact = (
                CanonFact(id=f"CF-{index + 1:03d}", statement=str(item))
                if isinstance(item, str)
                else CanonFact.from_dict(item, f"CF-{index + 1:03d}")
            )
            if fact.id in seen_facts:
                raise ValidationError(f"Duplicate canon fact id: {fact.id}")
            seen_facts.add(fact.id)
            canon.append(fact)

        world = cls(
            world_id=world_id,
            title=str(data.get("title") or world_id),
            description=str(data.get("description", "")),
            schema_version=schema_version,
            canon_version=int(data.get("canon_version", 1)),
            entities={key: Entity.from_dict(item, key) for key, item in entity_data.items()},
            locations={key: Location.from_dict(item, key) for key, item in location_data.items()},
            relationships={
                key: Relationship.from_dict(item, key) for key, item in relationship_data.items()
            },
            rules={key: Rule.from_dict(item) for key, item in rule_data.items()},
            constraints={
                key: Constraint.from_dict(item, key) for key, item in constraint_data.items()
            },
            canon=canon,
            events=list(data.get("events", [])),
            regression_suite=[
                Scenario.from_dict(item) for item in data.get("regression_suite", [])
            ],
            source_documents=list(data.get("source_documents", [])),
            settings=dict(data.get("settings", {})),
            history=list(data.get("history", [])),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )
        world.assert_valid()
        return world

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version.split(".", 1)[0] != SCHEMA_VERSION.split(".", 1)[0]:
            errors.append(f"Unsupported schema_version: {self.schema_version}")
        if not self.world_id.strip():
            errors.append("world_id cannot be empty")
        if self.canon_version < 1:
            errors.append("canon_version must be >= 1")
        for entity in self.entities.values():
            if entity.location_id and entity.location_id not in self.locations:
                errors.append(f"Entity {entity.id}: unknown location {entity.location_id!r}")
        for relationship in self.relationships.values():
            if relationship.source_id not in self.entities:
                errors.append(
                    f"Relationship {relationship.id}: unknown source {relationship.source_id!r}"
                )
            if relationship.target_id not in self.entities:
                errors.append(
                    f"Relationship {relationship.id}: unknown target {relationship.target_id!r}"
                )
        for rule in self.rules.values():
            errors.extend(rule.validate())
            if rule.status not in {RuleStatus.CANON.value, RuleStatus.DEPRECATED.value}:
                errors.append(f"World rule {rule.id}: only canon/deprecated rules may be in canon")
            for dependency in rule.depends_on:
                if dependency not in self.rules:
                    errors.append(f"Rule {rule.id}: missing dependency {dependency!r}")
                elif self.rules[dependency].status != RuleStatus.CANON.value:
                    errors.append(f"Rule {rule.id}: dependency {dependency!r} is not canon")
        for constraint in self.constraints.values():
            if constraint.kind == "axiom" and not constraint.description:
                errors.append(f"Constraint {constraint.id}: axiom needs a description")
        if self.regression_suite and not self.entities:
            errors.append("Regression suite cannot reference an empty world")
        return errors

    def assert_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def clone(self) -> World:
        return World.from_dict(copy.deepcopy(self.to_dict()))

    def canon_rules(self) -> list[Rule]:
        return sorted(
            (rule for rule in self.rules.values() if rule.status == RuleStatus.CANON.value),
            key=Rule.sort_key,
        )

    def active_constraints(self) -> list[Constraint]:
        return sorted(self.constraints.values(), key=lambda item: item.id)

    def find_entity(self, entity_id: str | None) -> Entity | None:
        return self.entities.get(entity_id) if entity_id else None

    def entity_location(self, entity: Entity | None) -> Location | None:
        if not entity or not entity.location_id:
            return None
        return self.locations.get(entity.location_id)


@dataclass(slots=True)
class RunLimits:
    max_rounds: int = 5
    max_scenarios: int = 24
    max_new_rules: int = 8
    max_proposals: int = 10
    max_consecutive_empty_rounds: int = 2

    def validate(self) -> None:
        for name, value in (
            ("max_rounds", self.max_rounds),
            ("max_scenarios", self.max_scenarios),
            ("max_new_rules", self.max_new_rules),
            ("max_proposals", self.max_proposals),
            ("max_consecutive_empty_rounds", self.max_consecutive_empty_rounds),
        ):
            if int(value) < 1:
                raise ValidationError(f"{name} must be >= 1")

    def to_dict(self) -> dict[str, int]:
        return {
            "max_rounds": self.max_rounds,
            "max_scenarios": self.max_scenarios,
            "max_new_rules": self.max_new_rules,
            "max_proposals": self.max_proposals,
            "max_consecutive_empty_rounds": self.max_consecutive_empty_rounds,
        }


@dataclass(slots=True)
class RunRound:
    index: int
    scenario_ids: list[str] = field(default_factory=list)
    finding_keys: list[str] = field(default_factory=list)
    proposal_ids: list[str] = field(default_factory=list)
    new_findings: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "scenario_ids": self.scenario_ids,
            "finding_keys": self.finding_keys,
            "proposal_ids": self.proposal_ids,
            "new_findings": self.new_findings,
            "note": self.note,
        }


@dataclass(slots=True)
class RunResult:
    run_id: str
    world_id: str
    world_version: int
    focus: str
    rounds: list[RunRound] = field(default_factory=list)
    findings: list[GapFinding] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    stop_reason: str = ""
    stop_detail: str = ""
    scenarios_run: int = 0
    duplicates_skipped: int = 0
    architect_mode: str = "scripted"
    limits: RunLimits = field(default_factory=RunLimits)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "world_id": self.world_id,
            "world_version": self.world_version,
            "focus": self.focus,
            "rounds": [item.to_dict() for item in self.rounds],
            "findings": [item.to_dict() for item in self.findings],
            "proposals": [item.to_dict() for item in self.proposals],
            "stop_reason": self.stop_reason,
            "stop_detail": self.stop_detail,
            "scenarios_run": self.scenarios_run,
            "duplicates_skipped": self.duplicates_skipped,
            "architect_mode": self.architect_mode,
            "limits": self.limits.to_dict(),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(slots=True)
class ApprovalResult:
    proposal_id: str
    applied: bool
    world_version: int
    message: str
    conflicts: list[Conflict] = field(default_factory=list)
    regression_results: list[RegressionResult] = field(default_factory=list)
    post_tests: list[dict[str, Any]] = field(default_factory=list)
    report_path: str = ""
    rollback_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "applied": self.applied,
            "world_version": self.world_version,
            "message": self.message,
            "conflicts": [item.to_dict() for item in self.conflicts],
            "regression_results": [item.to_dict() for item in self.regression_results],
            "post_tests": self.post_tests,
            "report_path": self.report_path,
            "rollback_performed": self.rollback_performed,
        }


def fingerprint_payload(payload: Any) -> str:
    """Stable hash for regression fingerprints and dedupe keys."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def observation_fingerprint(observation: Observation) -> str:
    return fingerprint_payload(
        {
            "effects": observation.effects,
            "events": observation.events,
            "violations": observation.violations,
            "matched_rule_ids": observation.matched_rule_ids,
            "error": observation.error,
        }
    )
