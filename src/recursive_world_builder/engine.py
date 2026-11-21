"""Deterministic rule evaluation.

This is not a physics engine and it is not a theorem prover.  It applies
explicit, declarative rules to a single scenario, records every state change,
and reports when no rule covers the interaction.  Anything beyond that is
inference performed by the host agent and must stay labelled as such.
"""

from __future__ import annotations

import logging
from typing import Any

from .model import (
    Action,
    Assumption,
    Entity,
    Location,
    Observation,
    Rule,
    Scenario,
    World,
    observation_fingerprint,
)

logger = logging.getLogger(__name__)


class RuleEngine:
    """Apply canon rules to scenarios without mutating the source world."""

    def simulate(self, world: World, scenario: Scenario) -> Observation:
        # Work against a private clone so even an effect targeting an explicit
        # entity id can never mutate canon or a caller's in-memory world.
        sandbox = world.clone()
        world = sandbox
        actor = world.entities.get(scenario.actor)
        target = world.entities.get(scenario.target) if scenario.target else None
        if actor is None:
            observation = Observation(
                scenario_id=scenario.id,
                actor_id=scenario.actor,
                target_id=scenario.target,
                error=f"unknown actor {scenario.actor!r}",
            )
            observation.fingerprint = observation_fingerprint(observation)
            return observation
        if scenario.target and target is None:
            observation = Observation(
                scenario_id=scenario.id,
                actor_id=scenario.actor,
                target_id=scenario.target,
                error=f"unknown target {scenario.target!r}",
            )
            observation.fingerprint = observation_fingerprint(observation)
            return observation

        actor, target, extra_entities, location = self._apply_assumptions(
            world, scenario, actor, target
        )

        violations = self._check_constraints(world, scenario, actor, target, location)
        if violations:
            observation = Observation(
                scenario_id=scenario.id,
                actor_id=actor.id,
                target_id=target.id if target else None,
                violations=violations,
                notes=[
                    "Scenario conflicts with an existing world constraint. "
                    "Do not patch canon from this result without resolving the constraint first."
                ],
            )
            observation.fingerprint = observation_fingerprint(observation)
            return observation

        matched = [
            rule
            for rule in world.canon_rules()
            if rule.matcher.matches(scenario.action.type, actor, target, location)
        ]
        if not matched:
            observation = Observation(
                scenario_id=scenario.id,
                actor_id=actor.id,
                target_id=target.id if target else None,
                notes=["No canon rule matched this action."],
            )
            observation.fingerprint = observation_fingerprint(observation)
            return observation

        effects: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        suppressed: list[str] = []
        # A set_property takes ownership of a property. Modifiers may stack on
        # top of earlier modifiers, but never override a set or an earlier
        # higher-priority state owner. This keeps priority deterministic.
        write_claims: dict[tuple[str, str], list[tuple[str, str]]] = {}
        notes: list[str] = []

        for rule in matched:
            for effect in rule.effects:
                claim_key: tuple[str, str] | None = None
                if effect.kind in {"set_property", "modify_property"}:
                    claim_key = (effect.target, effect.property or "")
                    prior = write_claims.setdefault(claim_key, [])
                    if effect.kind == "set_property" and prior:
                        owner = prior[0][0]
                        suppressed.append(rule.id)
                        notes.append(
                            f"Effect from {rule.id} suppressed: {owner} already wrote "
                            f"{claim_key[1]!r} in this scenario."
                        )
                        continue
                    if effect.kind == "modify_property" and any(kind == "set" for _, kind in prior):
                        owner = next(owner for owner, kind in prior if kind == "set")
                        suppressed.append(rule.id)
                        notes.append(
                            f"Effect from {rule.id} suppressed: {owner} owns "
                            f"{claim_key[1]!r} with a set operation."
                        )
                        continue
                    prior.append((rule.id, "set" if effect.kind == "set_property" else "modify"))

                resolved = self._resolve_target(
                    world,
                    effect.target,
                    actor=actor,
                    target=target,
                    location=location,
                    extra_entities=extra_entities,
                )
                if resolved is None:
                    notes.append(
                        f"Effect {effect.describe()} skipped: target {effect.target!r} not found"
                    )
                    continue

                record = self._apply_effect(rule, effect, resolved, events)
                if record:
                    effects.append(record)

        observation = Observation(
            scenario_id=scenario.id,
            actor_id=actor.id,
            target_id=target.id if target else None,
            matched_rule_ids=[rule.id for rule in matched],
            suppressed_rule_ids=sorted(set(suppressed)),
            effects=effects,
            events=events,
            notes=notes,
        )
        observation.fingerprint = observation_fingerprint(observation)
        return observation

    def simulate_many(self, world: World, scenarios: list[Scenario]) -> list[Observation]:
        return [self.simulate(world, scenario) for scenario in scenarios]

    def run(self, world: World, scenario: Scenario) -> Observation:
        return self.simulate(world, scenario)

    # ----------------------------------------------------------------- internals
    def _apply_assumptions(
        self,
        world: World,
        scenario: Scenario,
        actor: Entity,
        target: Entity | None,
    ) -> tuple[Entity, Entity | None, dict[str, Entity], Location | None]:
        extra: dict[str, Entity] = {}
        actors = {actor.id: self._clone_entity(actor)}
        if target is not None:
            extra[target.id] = self._clone_entity(target)
        for assumption in scenario.assumptions:
            entity = actors.get(assumption.entity_id) or extra.get(assumption.entity_id)
            if entity is None:
                source = world.entities.get(assumption.entity_id)
                if source is None:
                    logger.warning(
                        "Scenario %s assumption references unknown entity %s",
                        scenario.id,
                        assumption.entity_id,
                    )
                    continue
                entity = self._clone_entity(source)
                extra[source.id] = entity
            self._mutate_entity(entity, assumption)
        actor_out = actors[actor.id]
        target_out = extra.get(target.id) if target is not None else None
        location = world.locations.get(actor_out.location_id or "")
        return actor_out, target_out, extra, location

    @staticmethod
    def _clone_entity(entity: Entity) -> Entity:
        return Entity(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            location_id=entity.location_id,
            tags=list(entity.tags),
            properties=dict(entity.properties),
            description=entity.description,
        )

    @staticmethod
    def _mutate_entity(entity: Entity, assumption: Assumption) -> None:
        for tag in assumption.add_tags:
            if tag not in entity.tags:
                entity.tags.append(tag)
        entity.tags = [tag for tag in entity.tags if tag not in set(assumption.remove_tags)]
        entity.properties.update(assumption.set_properties)

    def _check_constraints(
        self,
        world: World,
        scenario: Scenario,
        actor: Entity,
        target: Entity | None,
        location: Location | None,
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        for constraint in world.active_constraints():
            if constraint.kind not in {"prohibition", "invariant"}:
                continue
            if not constraint.matcher:
                continue
            if constraint.matcher.matches(scenario.action.type, actor, target, location):
                violations.append(
                    {
                        "constraint_id": constraint.id,
                        "kind": constraint.kind,
                        "severity": constraint.severity,
                        "description": constraint.message or constraint.description,
                    }
                )
        return violations

    def _resolve_target(
        self,
        world: World,
        target_name: str,
        *,
        actor: Entity,
        target: Entity | None,
        location: Location | None,
        extra_entities: dict[str, Entity],
    ) -> Entity | Location | None:
        if target_name == "actor":
            return actor
        if target_name == "target":
            return target
        if target_name == "location":
            return location
        if target_name in extra_entities:
            return extra_entities[target_name]
        if target_name in world.entities:
            return world.entities[target_name]
        if target_name in world.locations:
            return world.locations[target_name]
        return None

    def _apply_effect(
        self,
        rule: Rule,
        effect: Any,
        resolved: Entity | Location,
        events: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        record: dict[str, Any] = {
            "rule_id": rule.id,
            "kind": effect.kind,
            "target_id": resolved.id,
        }
        if effect.kind == "set_property":
            before = resolved.properties.get(effect.property)
            resolved.properties[effect.property] = effect.value
            record.update(
                {
                    "property": effect.property,
                    "before": before,
                    "after": effect.value,
                }
            )
            return record
        if effect.kind == "modify_property":
            before = resolved.properties.get(effect.property, 0)
            try:
                after = float(before) + float(effect.delta or 0)
            except (TypeError, ValueError):
                after = before
            if isinstance(before, int) and float(after).is_integer():
                after = int(after)
            resolved.properties[effect.property] = after
            record.update(
                {
                    "property": effect.property,
                    "before": before,
                    "after": after,
                    "delta": effect.delta,
                }
            )
            return record
        if effect.kind == "add_tag":
            if effect.tag not in resolved.tags:
                resolved.tags.append(effect.tag)
            record["tag"] = effect.tag
            record["action"] = "add"
            return record
        if effect.kind == "remove_tag":
            resolved.tags = [tag for tag in resolved.tags if tag != effect.tag]
            record["tag"] = effect.tag
            record["action"] = "remove"
            return record
        if effect.kind == "move_entity":
            if not isinstance(resolved, Entity):
                return None
            destination = effect.property or effect.value
            before = resolved.location_id
            resolved.location_id = str(destination or "")
            record.update(
                {
                    "property": "location_id",
                    "before": before,
                    "after": resolved.location_id,
                }
            )
            return record
        if effect.kind == "emit_event":
            event = {
                "rule_id": rule.id,
                "event": effect.event or "unspecified_event",
                "message": effect.message,
                "target_id": resolved.id,
            }
            events.append(event)
            record.update(event)
            return record
        return None

    def explain(self, world: World, scenario: Scenario) -> str:
        observation = self.simulate(world, scenario)
        lines = [
            f"Scenario: {scenario.title}",
            f"Action: {scenario.actor} {scenario.action.type} {scenario.target or ''}".strip(),
            f"Matched: {', '.join(observation.matched_rule_ids) or 'none'}",
            f"Result: {observation.summary()}",
        ]
        if observation.notes:
            lines.append("Notes: " + " | ".join(observation.notes))
        return "\n".join(lines)


def dry_run(world: World, action: Action, actor: str, target: str | None = None) -> Observation:
    """Convenience helper for tests and ad-hoc probes."""

    scenario = Scenario(
        id="ad-hoc",
        title="Ad-hoc probe",
        actor=actor,
        target=target,
        action=action,
    )
    return RuleEngine().simulate(world, scenario)
