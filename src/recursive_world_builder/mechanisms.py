"""Scripted mechanism templates.

These templates exist for the offline demo and for deterministic tests.  They
are not a substitute for the host agent's reasoning.  Each template proposes a
small *cluster* of reusable rules rather than a one-off ``if object X then Y``
patch, and every proposal produced from one is labelled
``scripted_mechanism_template``.

Host agents should normally run exploration in ``--architect host`` mode and
write their own proposal JSON, especially for settings whose physics or society
deliberately diverges from reality.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .model import (
    Action,
    Assumption,
    Effect,
    Entity,
    GapFinding,
    Rule,
    RuleMatcher,
    RuleStatus,
    Scenario,
    World,
)

BIOLOGICAL = ["biological", "human", "animal", "creature", "alive"]
VEHICLE = ["vehicle", "car", "cart", "train", "ship"]
INFRASTRUCTURE = ["infrastructure", "structural", "pole", "tower", "bridge", "building"]
LIQUID = ["water", "liquid", "fluid", "river", "ocean", "pool"]
ENERGIZED = ["energized", "live", "charged", "powered_hazard"]
HEAT = ["fire", "hot", "heat", "flame"]
TOXIN = ["toxic", "poison", "venom", "contaminated"]
SOCIAL = ["institution", "law", "government", "guild", "court", "norm"]
MARKET = ["market", "resource", "currency", "shop", "commodity"]


@dataclass(slots=True)
class MechanismDraft:
    key: str
    title: str
    problem: str
    root_cause: str
    rationale: str
    rules: list[Rule]
    expected_impacts: list[str]
    affected_systems: list[str]
    test_plan: list[Scenario]
    generality: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.75
    evidence: list[str] = field(default_factory=list)


def _first(
    world: World,
    tags: list[str],
    *,
    exclude: set[str] | None = None,
    types: set[str] | None = None,
) -> Entity | None:
    excluded = exclude or set()
    for entity in sorted(world.entities.values(), key=lambda item: item.id):
        if entity.id in excluded:
            continue
        if types and entity.type not in types:
            continue
        if set(entity.tags) & set(tags):
            return entity
    return None


def _rule(
    rule_id: str,
    name: str,
    description: str,
    *,
    domain: str,
    action_types: list[str],
    effects: list[Effect],
    actor_tags_any: list[str] | None = None,
    actor_tags_none: list[str] | None = None,
    target_tags_any: list[str] | None = None,
    target_tags_none: list[str] | None = None,
    priority: int = 50,
    depends_on: list[str] | None = None,
    rationale: str = "",
    tags: list[str] | None = None,
    defies_reality: bool = False,
) -> Rule:
    return Rule(
        id=rule_id,
        name=name,
        description=description,
        domain=domain,
        matcher=RuleMatcher(
            action_types=action_types,
            actor_tags_any=actor_tags_any or [],
            actor_tags_none=actor_tags_none or [],
            target_tags_any=target_tags_any or [],
            target_tags_none=target_tags_none or [],
        ),
        effects=effects,
        priority=priority,
        status=RuleStatus.PROPOSED.value,
        depends_on=depends_on or [],
        tags=tags or [],
        defies_real_world_expectation=defies_reality,
        rationale=rationale,
        provenance={"source": "scripted_mechanism_template"},
    )


def _scenario(
    mechanism: str,
    index: int,
    title: str,
    actor: Entity | None,
    target: Entity | None,
    action_type: str,
    *,
    focus: str,
    description: str,
    action_tags: list[str] | None = None,
    assumptions: list[Assumption] | None = None,
) -> Scenario | None:
    if actor is None:
        return None
    return Scenario(
        id=f"T-{mechanism}-{index:02d}",
        title=title,
        actor=actor.id,
        target=target.id if target else None,
        action=Action(
            action_type,
            tags=action_tags or ["counterfactual", "proposal-test"],
            description=description,
        ),
        description=description,
        focus=focus,
        tags=["counterfactual", "proposal-test", mechanism],
        source="rule-architect",
        assumptions=assumptions or [],
    )


class MechanismLibrary:
    """Deterministic proposal templates keyed by inferred system."""

    def __init__(self) -> None:
        self._builders: dict[
            str, Callable[[World, GapFinding, Scenario], MechanismDraft | None]
        ] = {
            "electricity": self._electricity,
            "kinetics": self._kinetics,
            "thermodynamics": self._thermodynamics,
            "chemistry": self._chemistry,
            "hydrology": self._hydrology,
            "society": self._society,
            "economy": self._economy,
            "character": self._character,
            "biology": self._biology,
        }

    def draft(self, world: World, finding: GapFinding, scenario: Scenario) -> MechanismDraft | None:
        primary = self.primary_system(finding)
        builder = self._builders.get(primary)
        if builder is None:
            return None
        return builder(world, finding, scenario)

    @staticmethod
    def primary_system(finding: GapFinding) -> str:
        priority = [
            "electricity",
            "kinetics",
            "thermodynamics",
            "radiation",
            "chemistry",
            "hydrology",
            "society",
            "economy",
            "character",
            "biology",
        ]
        for candidate in priority:
            if candidate in finding.affected_systems:
                return candidate
        return finding.affected_systems[0] if finding.affected_systems else "general"

    # ------------------------------------------------------------- electricity
    def _electricity(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        energy = world.entities.get(scenario.target or "")
        if not energy or not set(energy.tags) & set(ENERGIZED):
            energy = _first(world, ENERGIZED)
        actor = world.entities.get(scenario.actor)
        if actor is None or not set(actor.tags) & set(BIOLOGICAL):
            actor = _first(world, BIOLOGICAL)
        if energy is None or actor is None:
            return None
        water = _first(world, LIQUID, exclude={energy.id})
        vehicle = _first(world, VEHICLE)
        structure = _first(world, INFRASTRUCTURE)

        rules = [
            _rule(
                "r_electric_contact_shock",
                "Conductive contact causes electrical injury",
                "A biological actor that contacts an energized entity without electrical "
                "insulation suffers injury. The tag 'energized' denotes a hazardous "
                "electrical state, independent of any specific object.",
                domain="physics",
                action_types=["touch", "contact", "grab", "immerse", "expose", "strike"],
                actor_tags_any=BIOLOGICAL,
                actor_tags_none=["electrically_insulated"],
                target_tags_any=ENERGIZED,
                effects=[
                    Effect(
                        "modify_property",
                        target="actor",
                        property="health",
                        delta=-60,
                        message="electrical injury",
                    ),
                    Effect("add_tag", target="actor", tag="electrically_shocked"),
                    Effect(
                        "emit_event",
                        target="actor",
                        event="electric_shock",
                        message="current passes through the actor",
                    ),
                ],
                priority=70,
                rationale="Generalizes across wires, rails, machinery, and charged creatures.",
                tags=["electricity", "injury", "general-mechanism"],
            ),
            _rule(
                "r_electric_insulation_grounds",
                "Insulation interrupts the shock path",
                "An actor tagged as electrically insulated can contact an energized "
                "entity without taking the default shock injury.",
                domain="physics",
                action_types=["touch", "contact", "grab", "immerse", "expose", "strike"],
                actor_tags_any=["electrically_insulated"],
                target_tags_any=ENERGIZED,
                effects=[
                    Effect(
                        "emit_event",
                        target="actor",
                        event="insulation_grounds_current",
                        message="insulating material interrupts the current path",
                    )
                ],
                priority=80,
                depends_on=["r_electric_contact_shock"],
                rationale="A positive rule makes the insulation exception testable and visible.",
                tags=["electricity", "materials", "general-mechanism"],
            ),
            _rule(
                "r_electric_medium_conduction",
                "Energized objects energize conductive media",
                "When an energized entity contacts a conductive medium such as water or "
                "metal, the medium becomes energized. This models a class of conduction, "
                "not a specific pool.",
                domain="physics",
                action_types=["contact", "touch", "fall", "drop", "immerse"],
                actor_tags_any=ENERGIZED,
                target_tags_any=LIQUID + ["conductive"],
                effects=[
                    Effect("add_tag", target="target", tag="energized"),
                    Effect(
                        "emit_event",
                        target="target",
                        event="medium_energized",
                        message="conductive medium becomes part of the live circuit",
                    ),
                ],
                priority=60,
                depends_on=["r_electric_contact_shock"],
                rationale=(
                    "Explains water, wet ground, metal debris, and similar media with one rule."
                ),
                tags=["electricity", "materials", "conduction", "general-mechanism"],
            ),
        ]
        test_plan = [
            item
            for item in [
                _scenario(
                    "electricity",
                    1,
                    f"{actor.name} touches {energy.name}",
                    actor,
                    energy,
                    "touch",
                    focus="physics",
                    description="Baseline contact should now produce a shock.",
                ),
                _scenario(
                    "electricity",
                    2,
                    f"{actor.name} touches {energy.name} while insulated",
                    actor,
                    energy,
                    "touch",
                    focus="physics",
                    description="Insulation should suppress the shock without a special case.",
                    assumptions=[Assumption(actor.id, add_tags=["electrically_insulated"])],
                ),
                _scenario(
                    "electricity",
                    3,
                    f"{energy.name} energizes a conductive medium",
                    energy,
                    water,
                    "contact",
                    focus="physics",
                    description="Conduction should propagate through a medium.",
                    action_tags=["contact", "composition"],
                )
                if water
                else None,
                _scenario(
                    "electricity",
                    4,
                    f"{actor.name} enters energized water",
                    actor,
                    water,
                    "immerse",
                    focus="physics",
                    description="The shock rule should compose with the medium-conduction rule.",
                    assumptions=[Assumption(water.id, add_tags=["energized"])] if water else [],
                )
                if water
                else None,
                _scenario(
                    "electricity",
                    5,
                    f"A vehicle strikes {structure.name if structure else 'infrastructure'}",
                    vehicle,
                    structure,
                    "collide",
                    focus="physics",
                    description="Impact damages infrastructure and can create downstream hazards.",
                )
                if vehicle and structure
                else None,
            ]
            if item is not None
        ]

        rules.append(
            _rule(
                "r_impact_infrastructure_damage",
                "Vehicle impact damages infrastructure",
                "A moving vehicle that collides with structural infrastructure reduces its "
                "integrity and marks it damaged. This is the upstream rule that can create "
                "downed-line and blocked-road situations.",
                domain="physics",
                action_types=["collide", "impact"],
                actor_tags_any=VEHICLE,
                target_tags_any=INFRASTRUCTURE,
                effects=[
                    Effect(
                        "modify_property",
                        target="target",
                        property="integrity",
                        delta=-25,
                    ),
                    Effect("add_tag", target="target", tag="damaged"),
                    Effect(
                        "emit_event",
                        target="target",
                        event="infrastructure_impact",
                        message="structure takes kinetic damage",
                    ),
                ],
                priority=50,
                rationale="Downstream hazards should build on a general impact rule.",
                tags=["kinetics", "infrastructure", "general-mechanism"],
            )
        )

        return MechanismDraft(
            key="electricity-conduction-cluster",
            title="Generalized electrical conduction and infrastructure interaction",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale=(
                "One electrical-conduction cluster covers direct contact, insulation, "
                "conductive media, and damaged infrastructure. It deliberately avoids "
                "object-specific outcomes such as 'touching this wire is fatal'."
            ),
            rules=rules,
            expected_impacts=[
                "Biological contact with any energized entity has a defined injury result.",
                "Electrical insulation is represented as a reusable material property.",
                "Water, wet ground, and metal debris can become energized through one rule.",
                "Infrastructure impact becomes a source of downstream hazards rather "
                "than a dead end.",
            ],
            affected_systems=[
                "electricity",
                "materials",
                "health",
                "infrastructure",
            ],
            test_plan=test_plan,
            generality={
                "scope": (
                    "Any biological actor, energized entity, conductive medium, vehicle, "
                    "or structural target."
                ),
                "special_case": False,
                "reusable": True,
                "assumptions": [
                    "the tag 'energized' denotes a hazardous electrical state",
                    "insulation is represented by an actor tag rather than a numeric "
                    "material model",
                ],
            },
            confidence=round(min(finding.confidence, 0.82), 2),
            evidence=finding.evidence,
        )

    # ----------------------------------------------------------------- kinetics
    def _kinetics(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        vehicle = world.entities.get(scenario.actor) or _first(world, VEHICLE)
        target = world.entities.get(scenario.target or "") or _first(world, INFRASTRUCTURE)
        if vehicle is None or target is None:
            return None
        rule = _rule(
            "r_kinetic_impact_damage",
            "Kinetic impacts transfer damage",
            "A moving object that collides with a structural or fragile target reduces "
            "the target's integrity in proportion to the collision event, not the target's name.",
            domain="physics",
            action_types=["collide", "impact", "strike"],
            actor_tags_any=VEHICLE + ["projectile"],
            target_tags_any=INFRASTRUCTURE + ["fragile", "breakable"],
            effects=[
                Effect("modify_property", target="target", property="integrity", delta=-25),
                Effect("add_tag", target="target", tag="damaged"),
                Effect(
                    "emit_event",
                    target="target",
                    event="kinetic_impact",
                    message="impact transfers energy to the target",
                ),
            ],
            priority=50,
            rationale="A single impact rule can feed damage, collapse, and hazard subsystems.",
            tags=["kinetics", "materials", "general-mechanism"],
        )
        test_plan = [
            item
            for item in [
                _scenario(
                    "kinetics",
                    1,
                    f"{vehicle.name} collides with {target.name}",
                    vehicle,
                    target,
                    "collide",
                    focus="physics",
                    description="Impact should transfer damage.",
                )
            ]
            if item is not None
        ]
        return MechanismDraft(
            key="kinetic-impact-cluster",
            title="Generalized kinetic impact and structural damage",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale="Use one impact rule for vehicles, projectiles, and collapsing structures.",
            rules=[rule],
            expected_impacts=[
                "Collisions alter integrity and mark targets damaged.",
                "Damaged structures can feed later hazard scenarios without new exceptions.",
            ],
            affected_systems=["kinetics", "materials", "infrastructure"],
            test_plan=test_plan,
            generality={
                "scope": (
                    "Any moving actor with a vehicle/projectile tag hitting a "
                    "structural or fragile target."
                ),
                "special_case": False,
                "reusable": True,
            },
            confidence=round(min(finding.confidence, 0.8), 2),
            evidence=finding.evidence,
        )

    # ----------------------------------------------------------- thermodynamics
    def _thermodynamics(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        heat = world.entities.get(scenario.target or "") or _first(world, HEAT + ["temperature"])
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if heat is None or actor is None:
            return None
        rules = [
            _rule(
                "r_thermal_transfer_injury",
                "Heat transfers to biological tissue",
                "Biological actors exposed to a hot or burning entity receive thermal injury "
                "unless tagged heat resistant.",
                domain="physics",
                action_types=["touch", "contact", "expose", "enter"],
                actor_tags_any=BIOLOGICAL,
                actor_tags_none=["heat_resistant", "fireproof"],
                target_tags_any=HEAT,
                effects=[
                    Effect("modify_property", target="actor", property="health", delta=-25),
                    Effect("add_tag", target="actor", tag="burned"),
                    Effect(
                        "emit_event",
                        target="actor",
                        event="thermal_injury",
                        message="heat transfers into tissue",
                    ),
                ],
                priority=60,
                tags=["thermodynamics", "health", "general-mechanism"],
                rationale="Temperature is a shared medium; fire is one source, not the rule.",
            ),
            _rule(
                "r_combustion_spread",
                "Flammable targets ignite from fire",
                "A flammable target in contact with fire gains the burning tag and emits an "
                "ignition event.",
                domain="physics",
                action_types=["contact", "touch", "ignite"],
                actor_tags_any=HEAT,
                target_tags_any=["flammable", "fuel", "wood", "cloth"],
                effects=[
                    Effect("add_tag", target="target", tag="burning"),
                    Effect(
                        "emit_event",
                        target="target",
                        event="ignition",
                        message="flammable material catches fire",
                    ),
                ],
                priority=55,
                depends_on=["r_thermal_transfer_injury"],
                tags=["thermodynamics", "combustion", "general-mechanism"],
            ),
        ]
        test_plan = [
            item
            for item in [
                _scenario(
                    "thermodynamics",
                    1,
                    f"{actor.name} touches {heat.name}",
                    actor,
                    heat,
                    "touch",
                    focus="physics",
                    description="Thermal injury should follow a general transfer rule.",
                ),
                _scenario(
                    "thermodynamics",
                    2,
                    f"Heat-resistant {actor.name} touches {heat.name}",
                    actor,
                    heat,
                    "touch",
                    focus="physics",
                    description="Material resistance should be represented by a tag.",
                    assumptions=[Assumption(actor.id, add_tags=["heat_resistant"])],
                ),
            ]
            if item is not None
        ]
        return MechanismDraft(
            key="thermal-transfer-cluster",
            title="Generalized heat transfer and ignition",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale="Separate heat transfer from ignition so both can compose with materials.",
            rules=rules,
            expected_impacts=[
                "Heat exposure injures unprotected biological actors.",
                "Flammable materials ignite and can propagate fire.",
            ],
            affected_systems=["thermodynamics", "materials", "health"],
            test_plan=test_plan,
            generality={
                "scope": "Any hot source, biological target, and flammable material.",
                "special_case": False,
                "reusable": True,
            },
            confidence=round(min(finding.confidence, 0.8), 2),
            evidence=finding.evidence,
        )

    # ----------------------------------------------------------------- chemistry
    def _chemistry(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        toxin = world.entities.get(scenario.target or "") or _first(world, TOXIN)
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if toxin is None or actor is None:
            return None
        rule = _rule(
            "r_toxin_exposure_injury",
            "Toxic exposure causes dose-dependent injury",
            "Biological actors exposed to a toxic entity suffer injury unless they have "
            "a resistance tag. Dosage is represented by exposure events, not a chemistry engine.",
            domain="biology",
            action_types=["touch", "contact", "expose", "ingest", "inhale"],
            actor_tags_any=BIOLOGICAL,
            actor_tags_none=["toxin_resistant"],
            target_tags_any=TOXIN,
            effects=[
                Effect("modify_property", target="actor", property="health", delta=-20),
                Effect("add_tag", target="actor", tag="poisoned"),
                Effect(
                    "emit_event",
                    target="actor",
                    event="toxin_exposure",
                    message="toxin enters the actor's body",
                ),
            ],
            priority=60,
            tags=["chemistry", "biology", "general-mechanism"],
        )
        return MechanismDraft(
            key="toxin-exposure-cluster",
            title="Generalized toxic exposure",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale="Exposure and resistance are separate reusable concepts.",
            rules=[rule],
            expected_impacts=[
                "Unprotected biological actors are injured by toxic material.",
                "Resistance tags can suppress the default outcome.",
            ],
            affected_systems=["chemistry", "biology", "health"],
            test_plan=[
                item
                for item in [
                    _scenario(
                        "chemistry",
                        1,
                        f"{actor.name} is exposed to {toxin.name}",
                        actor,
                        toxin,
                        "expose",
                        focus="biology",
                        description="Toxic exposure should have a physiological consequence.",
                    )
                ]
                if item is not None
            ],
            generality={
                "scope": "Any toxic source and any biological actor without resistance.",
                "special_case": False,
                "reusable": True,
            },
            confidence=round(min(finding.confidence, 0.78), 2),
            evidence=finding.evidence,
        )

    # ----------------------------------------------------------------- hydrology
    def _hydrology(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        water = world.entities.get(scenario.target or "") or _first(world, LIQUID)
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if water is None or actor is None:
            return None
        rule = _rule(
            "r_immersion_drowning_risk",
            "Immersion creates drowning and wetness state",
            "A biological actor that immerses in a deep liquid gains a submerged state and "
            "loses health unless tagged aquatic or breathing apparatus. Shallow water is a "
            "location property, not a special rule.",
            domain="physics",
            action_types=["immerse", "enter", "fall"],
            actor_tags_any=BIOLOGICAL,
            actor_tags_none=["aquatic", "water_breathing", "sealed_suit"],
            target_tags_any=LIQUID,
            effects=[
                Effect("add_tag", target="actor", tag="submerged"),
                Effect("modify_property", target="actor", property="health", delta=-10),
                Effect(
                    "emit_event",
                    target="actor",
                    event="immersion",
                    message="actor enters a liquid medium",
                ),
            ],
            priority=55,
            tags=["hydrology", "biology", "general-mechanism"],
        )
        return MechanismDraft(
            key="immersion-cluster",
            title="Generalized immersion and drowning risk",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale="Separate the medium from the actor's breathing capability.",
            rules=[rule],
            expected_impacts=[
                "Immersion has a physiological and state consequence.",
                "Aquatic or sealed actors are handled by tags, not by another rule.",
            ],
            affected_systems=["hydrology", "materials", "health"],
            test_plan=[
                item
                for item in [
                    _scenario(
                        "hydrology",
                        1,
                        f"{actor.name} enters {water.name}",
                        actor,
                        water,
                        "immerse",
                        focus="physics",
                        description="Immersion should update state and risk.",
                    )
                ]
                if item is not None
            ],
            generality={
                "scope": "Any liquid medium and biological actor without an aquatic tag.",
                "special_case": False,
                "reusable": True,
            },
            confidence=round(min(finding.confidence, 0.75), 2),
            evidence=finding.evidence,
        )

    # ------------------------------------------------------------------ society
    def _society(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        institution = world.entities.get(scenario.target or "") or _first(world, SOCIAL)
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if institution is None or actor is None:
            return None
        rules = [
            _rule(
                "r_institution_acknowledges_request",
                "Institutions acknowledge petitions",
                "A petition to an institution creates a pending-review state and an official "
                "acknowledgement event. This is a minimal procedural model, not a "
                "full politics engine.",
                domain="society",
                action_types=["petition", "request", "appeal", "report"],
                actor_tags_any=BIOLOGICAL + ["citizen", "member"],
                target_tags_any=SOCIAL,
                effects=[
                    Effect("add_tag", target="target", tag="petition_received"),
                    Effect(
                        "emit_event",
                        target="target",
                        event="petition_acknowledged",
                        message="institution records the request",
                    ),
                ],
                priority=50,
                tags=["society", "institutions", "general-mechanism"],
            ),
            _rule(
                "r_sanction_for_violation",
                "Recognized violations trigger sanctions",
                "An enforcement actor can impose a sanction on a target tagged as a rule "
                "breaker. Legitimacy, severity, and appeal are represented as properties for "
                "the host agent to reason about, not simulated automatically.",
                domain="society",
                action_types=["sanction", "arrest", "fine", "sentence"],
                actor_tags_any=["enforcer", "institution", "official"],
                target_tags_any=["rule_breaker", "suspect", "convicted"],
                effects=[
                    Effect("add_tag", target="target", tag="sanctioned"),
                    Effect(
                        "emit_event",
                        target="target",
                        event="sanction_applied",
                        message="an institution applies a sanction",
                    ),
                ],
                priority=55,
                tags=["society", "law", "general-mechanism"],
            ),
        ]
        test_plan = [
            item
            for item in [
                _scenario(
                    "society",
                    1,
                    f"{actor.name} petitions {institution.name}",
                    actor,
                    institution,
                    "petition",
                    focus="society",
                    description="Institutional response should be explicit.",
                )
            ]
            if item is not None
        ]
        return MechanismDraft(
            key="institutional-response-cluster",
            title="Minimal institutional acknowledgement and sanction",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale=(
                "Models procedure and enforcement as separate, inspectable rules. It avoids "
                "claiming to simulate legitimacy or culture."
            ),
            rules=rules,
            expected_impacts=[
                "Petitions produce a recorded institutional state.",
                "Sanctions are possible only for targets already marked as rule breakers.",
            ],
            affected_systems=["society", "law", "institutions"],
            test_plan=test_plan,
            generality={
                "scope": (
                    "Any institution, citizen, and enforcement actor using the documented tags."
                ),
                "special_case": False,
                "reusable": True,
                "limits": (
                    "Legitimacy, faction politics, and cultural meaning remain "
                    "host-agent judgements."
                ),
            },
            confidence=round(min(finding.confidence, 0.7), 2),
            evidence=finding.evidence,
        )

    # ------------------------------------------------------------------ economy
    def _economy(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        resource = world.entities.get(scenario.target or "") or _first(world, MARKET)
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if resource is None or actor is None:
            return None
        rule = _rule(
            "r_trade_exchange",
            "Trade transfers a resource claim",
            "A trade action creates an exchange event and marks the resource as transacted. "
            "Price formation and scarcity equilibrium are outside the deterministic engine.",
            domain="economy",
            action_types=["trade", "buy", "sell", "barter"],
            actor_tags_any=BIOLOGICAL + ["merchant", "buyer", "seller"],
            target_tags_any=MARKET,
            effects=[
                Effect("add_tag", target="target", tag="transacted"),
                Effect(
                    "emit_event",
                    target="target",
                    event="exchange_completed",
                    message="ownership or use claim changes hands",
                ),
            ],
            priority=50,
            tags=["economy", "exchange", "general-mechanism"],
        )
        return MechanismDraft(
            key="exchange-cluster",
            title="Minimal exchange and ownership event",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale=(
                "A transaction event is enough to expose downstream rules about price, "
                "scarcity, and ownership without pretending to simulate a market."
            ),
            rules=[rule],
            expected_impacts=[
                "Trade produces an explicit exchange event and ownership-relevant state.",
                "Scarcity and price remain host-agent concerns, clearly outside "
                "deterministic simulation.",
            ],
            affected_systems=["economy", "exchange", "resources"],
            test_plan=[
                item
                for item in [
                    _scenario(
                        "economy",
                        1,
                        f"{actor.name} attempts to trade for {resource.name}",
                        actor,
                        resource,
                        "trade",
                        focus="economy",
                        description="Exchange should have a defined event.",
                    )
                ]
                if item is not None
            ],
            generality={
                "scope": "Any actor and resource tagged for exchange.",
                "special_case": False,
                "reusable": True,
                "limits": "No market clearing, price discovery, or currency simulation.",
            },
            confidence=round(min(finding.confidence, 0.68), 2),
            evidence=finding.evidence,
        )

    # ---------------------------------------------------------------- character
    def _character(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        actor = world.entities.get(scenario.actor)
        target = world.entities.get(scenario.target or "")
        if actor is None or target is None or actor.id == target.id:
            return None
        rule = _rule(
            "r_persuasion_exchange",
            "Persuasion produces a stance event",
            "A persuasion attempt creates a stance event on the target. The deterministic "
            "engine does not decide whether the target is convinced; belief change requires "
            "host reasoning or an explicit belief rule.",
            domain="character",
            action_types=["persuade", "argue", "negotiate", "threaten"],
            actor_tags_any=BIOLOGICAL,
            target_tags_any=BIOLOGICAL,
            effects=[
                Effect(
                    "emit_event",
                    target="target",
                    event="persuasion_attempted",
                    message="target registers a persuasion attempt",
                ),
                Effect("add_tag", target="target", tag="stance_contested"),
            ],
            priority=40,
            tags=["character", "agency", "general-mechanism"],
        )
        return MechanismDraft(
            key="persuasion-event-cluster",
            title="Minimal persuasion and stance event",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale=(
                "Records that persuasion occurred without pretending to model another mind. "
                "Belief content stays with the host agent."
            ),
            rules=[rule],
            expected_impacts=[
                "Persuasion attempts become visible events instead of undefined no-ops.",
                "Actual belief revision is explicitly out of scope.",
            ],
            affected_systems=["character", "agency", "knowledge"],
            test_plan=[
                item
                for item in [
                    _scenario(
                        "character",
                        1,
                        f"{actor.name} attempts to persuade {target.name}",
                        actor,
                        target,
                        "persuade",
                        focus="character",
                        description="A persuasion attempt should produce an observable event.",
                    )
                ]
                if item is not None
            ],
            generality={
                "scope": "Any two characters with agency.",
                "special_case": False,
                "reusable": True,
                "limits": "Does not determine belief change or emotional outcome.",
            },
            confidence=round(min(finding.confidence, 0.62), 2),
            evidence=finding.evidence,
        )

    # ------------------------------------------------------------------ biology
    def _biology(
        self, world: World, finding: GapFinding, scenario: Scenario
    ) -> MechanismDraft | None:
        hazard = world.entities.get(scenario.target or "") or _first(world, TOXIN + HEAT)
        actor = world.entities.get(scenario.actor) or _first(world, BIOLOGICAL)
        if hazard is None or actor is None:
            return None
        rule = _rule(
            "r_hazard_exposure_injury",
            "Hazard exposure injures biological actors",
            "A biological actor exposed to a tagged hazard takes injury unless a matching "
            "resistance tag is present. More specific rules should override or depend on this one.",
            domain="biology",
            action_types=["expose", "touch", "contact", "ingest", "inhale"],
            actor_tags_any=BIOLOGICAL,
            actor_tags_none=["hazard_resistant"],
            target_tags_any=TOXIN + HEAT + ["hazard"],
            effects=[
                Effect("modify_property", target="actor", property="health", delta=-15),
                Effect("add_tag", target="actor", tag="exposed"),
                Effect(
                    "emit_event",
                    target="actor",
                    event="hazard_exposure",
                    message="hazard affects the actor",
                ),
            ],
            priority=45,
            tags=["biology", "health", "general-mechanism"],
        )
        return MechanismDraft(
            key="hazard-exposure-cluster",
            title="Minimal biological hazard exposure",
            problem=finding.observation,
            root_cause=finding.hypothesis,
            rationale="One exposure rule can be specialized by more specific mechanisms.",
            rules=[rule],
            expected_impacts=["Exposure has a defined physiological result."],
            affected_systems=["biology", "health"],
            test_plan=[
                item
                for item in [
                    _scenario(
                        "biology",
                        1,
                        f"{actor.name} is exposed to {hazard.name}",
                        actor,
                        hazard,
                        "expose",
                        focus="biology",
                        description="General hazard exposure should have a consequence.",
                    )
                ]
                if item is not None
            ],
            generality={
                "scope": "Any biological actor and tagged hazard.",
                "special_case": False,
                "reusable": True,
            },
            confidence=round(min(finding.confidence, 0.72), 2),
            evidence=finding.evidence,
        )
