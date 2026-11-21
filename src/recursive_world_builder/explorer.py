"""Explorer: generate scenarios and run them against the world.

The built-in generator is a deterministic *probe planner*, not a creative
agent.  It looks for semantic tags that tend to expose causal gaps (hazards,
liquids, vehicles, institutions, markets) and composes simple actions.  A host
agent can add richer, in-character scenarios through ``exploration_cases.json``
or by calling the Python API directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .engine import RuleEngine
from .model import (
    Action,
    Assumption,
    Domain,
    Entity,
    Observation,
    Scenario,
    ValidationError,
    World,
)

logger = logging.getLogger(__name__)

HAZARD_TAGS = {
    "energized",
    "electrical",
    "live",
    "radioactive",
    "toxic",
    "poison",
    "fire",
    "hot",
    "sharp",
    "cursed",
    "hazard",
}
LIQUID_TAGS = {"water", "liquid", "fluid", "river", "ocean", "pool"}
VEHICLE_TAGS = {"vehicle", "cart", "car", "ship", "train"}
INFRASTRUCTURE_TAGS = {"infrastructure", "structural", "pole", "bridge", "building", "tower"}
BIOLOGICAL_TAGS = {"biological", "human", "animal", "creature", "character", "alive"}
MARKET_TAGS = {"market", "resource", "currency", "shop", "trade_good", "commodity"}
SOCIAL_TAGS = {"institution", "law", "government", "guild", "court", "norm"}
FRAGILE_TAGS = {"fragile", "breakable", "crate", "glass"}

FOCUS_ORDER = [
    Domain.PHYSICS.value,
    Domain.BIOLOGY.value,
    Domain.SOCIETY.value,
    Domain.ECONOMY.value,
    Domain.CHARACTER.value,
]


def _tagged(entity: Entity, tags: set[str]) -> bool:
    return bool(set(entity.tags) & tags)


def _characters(world: World) -> list[Entity]:
    return sorted(
        (
            entity
            for entity in world.entities.values()
            if _tagged(entity, BIOLOGICAL_TAGS) or entity.type in {"character", "creature"}
        ),
        key=lambda item: item.id,
    )


class ScenarioGenerator:
    def __init__(self, engine: RuleEngine | None = None):
        self.engine = engine or RuleEngine()

    def generate(
        self,
        world: World,
        *,
        focus: str = "all",
        limit: int = 10,
        exclude_keys: set[str] | None = None,
    ) -> list[Scenario]:
        exclude = exclude_keys or set()
        candidates: list[Scenario] = []
        for domain in self._domains(focus):
            candidates.extend(self._candidates_for(world, domain))
        # Stable sort by focus only: within a focus, preserve the probe planner's
        # deliberate ordering (direct contact before composition and collision).
        candidates.sort(
            key=lambda item: FOCUS_ORDER.index(item.focus) if item.focus in FOCUS_ORDER else 99
        )
        selected: list[Scenario] = []
        for scenario in candidates:
            if scenario.key() in exclude:
                continue
            if scenario.key() in {item.key() for item in selected}:
                continue
            selected.append(scenario)
            if len(selected) >= limit:
                break
        return selected

    @staticmethod
    def _domains(focus: str) -> list[str]:
        if focus == "all":
            return list(FOCUS_ORDER)
        if focus not in FOCUS_ORDER:
            raise ValidationError(
                f"Unknown focus {focus!r}; choose all or one of {', '.join(FOCUS_ORDER)}"
            )
        return [focus]

    def _candidates_for(self, world: World, domain: str) -> list[Scenario]:
        if domain == Domain.PHYSICS.value:
            return self._physics(world)
        if domain == Domain.BIOLOGY.value:
            return self._biology(world)
        if domain == Domain.SOCIETY.value:
            return self._society(world)
        if domain == Domain.ECONOMY.value:
            return self._economy(world)
        return self._character(world)

    # ------------------------------------------------------------------ physics
    def _physics(self, world: World) -> list[Scenario]:
        scenarios: list[Scenario] = []
        characters = _characters(world)
        for hazard in sorted(world.entities.values(), key=lambda item: item.id):
            if not _tagged(hazard, HAZARD_TAGS):
                continue
            for character in characters:
                if character.id == hazard.id:
                    continue
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-physics-contact-{character.id}-{hazard.id}",
                        f"{character.name} probes {hazard.name}",
                        character,
                        hazard,
                        Action("touch", tags=["contact", "probe"]),
                        domain=Domain.PHYSICS.value,
                        description=(
                            f"{character.name} deliberately makes contact with {hazard.name}, "
                            "testing whether the world defines a consequence."
                        ),
                    )
                )
            # Hazardous thing interacts with a liquid (e.g. a live wire falling
            # into water).  This is a composition probe, not a special case.
            for liquid in sorted(world.entities.values(), key=lambda item: item.id):
                if liquid.id == hazard.id or not _tagged(liquid, LIQUID_TAGS):
                    continue
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-physics-fluid-{hazard.id}-{liquid.id}",
                        f"{hazard.name} contacts {liquid.name}",
                        hazard,
                        liquid,
                        Action("contact", tags=["contact", "composition", "fluid"]),
                        domain=Domain.PHYSICS.value,
                        description=(
                            f"{hazard.name} is brought into contact with {liquid.name}. "
                            "The probe looks for an unstated medium interaction."
                        ),
                    )
                )
        for vehicle in sorted(world.entities.values(), key=lambda item: item.id):
            if not _tagged(vehicle, VEHICLE_TAGS):
                continue
            for structure in sorted(world.entities.values(), key=lambda item: item.id):
                if structure.id == vehicle.id:
                    continue
                if not _tagged(structure, INFRASTRUCTURE_TAGS | FRAGILE_TAGS):
                    continue
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-physics-collide-{vehicle.id}-{structure.id}",
                        f"{vehicle.name} collides with {structure.name}",
                        vehicle,
                        structure,
                        Action("collide", tags=["impact", "kinetic"]),
                        domain=Domain.PHYSICS.value,
                        description=(
                            f"{vehicle.name} strikes {structure.name}, testing damage and "
                            "downstream consequences."
                        ),
                    )
                )
        return scenarios

    # ------------------------------------------------------------------ biology
    def _biology(self, world: World) -> list[Scenario]:
        scenarios: list[Scenario] = []
        characters = _characters(world)
        for hazard in sorted(world.entities.values(), key=lambda item: item.id):
            if not _tagged(hazard, HAZARD_TAGS):
                continue
            for character in characters:
                if character.id == hazard.id:
                    continue
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-biology-expose-{character.id}-{hazard.id}",
                        f"{character.name} is exposed to {hazard.name}",
                        character,
                        hazard,
                        Action("expose", tags=["contact", "biological"]),
                        domain=Domain.BIOLOGY.value,
                        description=(
                            f"Test whether {hazard.name} has a physiological consequence for "
                            f"{character.name}."
                        ),
                    )
                )
        return scenarios

    # ------------------------------------------------------------------ society
    def _society(self, world: World) -> list[Scenario]:
        scenarios: list[Scenario] = []
        characters = _characters(world)
        for constraint in world.active_constraints():
            if constraint.kind != "prohibition" or not constraint.matcher:
                continue
            for character in characters:
                target = self._find_matching_entity(world, constraint.matcher.target_tags_any)
                if target is None:
                    continue
                action_type = (constraint.matcher.action_types or ["interact"])[0]
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-society-{constraint.id}-{character.id}",
                        f"{character.name} tests prohibition {constraint.id}",
                        character,
                        target,
                        Action(action_type, tags=["institutional", "boundary"]),
                        domain=Domain.SOCIETY.value,
                        description=(
                            f"Deliberately trigger {constraint.id} to separate a legal/social "
                            "prohibition from an undefined causal consequence."
                        ),
                    )
                )
        for institution in sorted(world.entities.values(), key=lambda item: item.id):
            if not _tagged(institution, SOCIAL_TAGS):
                continue
            for character in characters:
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-society-petition-{character.id}-{institution.id}",
                        f"{character.name} petitions {institution.name}",
                        character,
                        institution,
                        Action("petition", tags=["social", "institutional"]),
                        domain=Domain.SOCIETY.value,
                        description=(
                            f"Test whether {institution.name} has a defined response to a "
                            "request from an ordinary character."
                        ),
                    )
                )
        return scenarios

    # ------------------------------------------------------------------ economy
    def _economy(self, world: World) -> list[Scenario]:
        scenarios: list[Scenario] = []
        characters = _characters(world)
        for resource in sorted(world.entities.values(), key=lambda item: item.id):
            if not _tagged(resource, MARKET_TAGS):
                continue
            for character in characters:
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-economy-trade-{character.id}-{resource.id}",
                        f"{character.name} attempts to trade for {resource.name}",
                        character,
                        resource,
                        Action("trade", tags=["economic", "exchange"]),
                        domain=Domain.ECONOMY.value,
                        description=(
                            f"Test the exchange rules and ownership consequences around "
                            f"{resource.name}."
                        ),
                    )
                )
        return scenarios

    # ---------------------------------------------------------------- character
    def _character(self, world: World) -> list[Scenario]:
        scenarios: list[Scenario] = []
        characters = _characters(world)
        for character in characters:
            for other in characters:
                if character.id >= other.id:
                    continue
                scenarios.append(
                    self._scenario(
                        world,
                        f"auto-character-persuade-{character.id}-{other.id}",
                        f"{character.name} tries to persuade {other.name}",
                        character,
                        other,
                        Action("persuade", tags=["social", "agency"]),
                        domain=Domain.CHARACTER.value,
                        description=(
                            "Probe whether persuasion, belief, and refusal have defined "
                            "causal consequences."
                        ),
                    )
                )
        return scenarios

    @staticmethod
    def _find_matching_entity(world: World, tags: list[str]) -> Entity | None:
        if not tags:
            return None
        for entity in sorted(world.entities.values(), key=lambda item: item.id):
            if set(entity.tags) & set(tags):
                return entity
        return None

    def _scenario(
        self,
        world: World,
        scenario_id: str,
        title: str,
        actor: Entity,
        target: Entity,
        action: Action,
        *,
        domain: str,
        description: str,
        assumptions: list[Assumption] | None = None,
    ) -> Scenario:
        return Scenario(
            id=scenario_id,
            title=title,
            actor=actor.id,
            target=target.id,
            action=action,
            description=description,
            focus=domain,
            tags=[domain, "auto-generated"],
            source="generated",
            assumptions=assumptions or [],
        )


class Explorer:
    """Plans and executes exploration probes."""

    def __init__(
        self,
        engine: RuleEngine | None = None,
        generator: ScenarioGenerator | None = None,
        external_path: str | Path | None = None,
    ):
        self.engine = engine or RuleEngine()
        self.generator = generator or ScenarioGenerator(self.engine)
        self.external_path = Path(external_path) if external_path else None
        self.external_scenarios: list[Scenario] = []
        if self.external_path and self.external_path.exists():
            self.external_scenarios = self.load_external(self.external_path)

    def load_external(self, path: str | Path) -> list[Scenario]:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"Cannot read external scenarios from {path}: {exc}") from exc
        raw = payload.get("scenarios", []) if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise ValidationError(f"{path}: scenarios must be a list")
        scenarios = []
        for item in raw:
            scenario = Scenario.from_dict(item)
            scenario.source = scenario.source or "external"
            scenarios.append(scenario)
        logger.info("Loaded %d external scenarios from %s", len(scenarios), path)
        return scenarios

    def plan(
        self,
        world: World,
        *,
        focus: str = "all",
        limit: int = 10,
        exclude_keys: set[str] | None = None,
    ) -> list[Scenario]:
        exclude = set(exclude_keys or set())
        generated = self.generator.generate(
            world, focus=focus, limit=max(limit * 3, limit), exclude_keys=exclude
        )
        external = [
            scenario
            for scenario in self.external_scenarios
            if scenario.focus == focus or focus == "all"
        ]
        combined: list[Scenario] = []
        seen: set[str] = set()
        for scenario in external + generated:
            key = scenario.key()
            if key in exclude or key in seen:
                continue
            seen.add(key)
            combined.append(scenario)
            if len(combined) >= limit:
                break
        return combined

    def observe(self, world: World, scenario: Scenario) -> Observation:
        return self.engine.simulate(world, scenario)

    def discover(
        self,
        world: World,
        *,
        focus: str = "all",
        limit: int = 10,
        exclude_keys: set[str] | None = None,
    ) -> list[tuple[Scenario, Observation]]:
        scenarios = self.plan(world, focus=focus, limit=limit, exclude_keys=exclude_keys)
        return [(scenario, self.observe(world, scenario)) for scenario in scenarios]


def scenarios_from_dicts(items: list[dict[str, Any]]) -> list[Scenario]:
    return [Scenario.from_dict(item) for item in items]
