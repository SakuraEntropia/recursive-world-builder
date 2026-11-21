"""Causal Critic: turn a scenario observation into a structured finding.

Three distinctions matter most:

* ``explicit_violation`` — the scenario contradicts a declared constraint.
* ``undefined_interaction`` — canon is silent; this is a candidate gap.
* ``allowed_but_unrealistic`` — canon *does* allow the outcome, even if it
  differs from real-world intuition.  Fictional axioms win.  Never auto-patch.

Confidence values are subjective agent judgements.  They are deliberately
marked uncalibrated; nothing in this module is a statistical estimate.
"""

from __future__ import annotations

import logging

from .model import (
    GapFinding,
    GapType,
    Observation,
    Recommendation,
    Scenario,
    World,
    fingerprint_payload,
)

logger = logging.getLogger(__name__)

TAG_SYSTEMS: dict[str, list[str]] = {
    "energized": ["electricity", "materials", "health"],
    "electrical": ["electricity", "materials", "health"],
    "live": ["electricity", "materials", "health"],
    "water": ["hydrology", "materials", "health"],
    "liquid": ["hydrology", "materials"],
    "fluid": ["hydrology", "materials"],
    "vehicle": ["kinetics", "materials", "infrastructure"],
    "car": ["kinetics", "materials", "infrastructure"],
    "structural": ["materials", "infrastructure"],
    "infrastructure": ["materials", "infrastructure"],
    "fragile": ["materials", "kinetics"],
    "fire": ["combustion", "materials", "health"],
    "hot": ["thermodynamics", "materials", "health"],
    "temperature": ["thermodynamics", "materials"],
    "toxic": ["chemistry", "biology", "health"],
    "poison": ["chemistry", "biology", "health"],
    "radioactive": ["radiation", "biology", "health"],
    "sharp": ["materials", "health"],
    "biological": ["biology", "health"],
    "human": ["biology", "health"],
    "animal": ["biology", "health"],
    "institution": ["society", "institutions"],
    "law": ["society", "law"],
    "government": ["society", "institutions", "law"],
    "market": ["economy", "exchange"],
    "resource": ["economy", "resources"],
    "currency": ["economy", "exchange"],
    "character": ["character", "agency", "knowledge"],
    "mind": ["character", "psychology"],
}

ACTION_SYSTEMS: dict[str, list[str]] = {
    "touch": ["materials", "health"],
    "contact": ["materials", "health"],
    "immerse": ["hydrology", "health"],
    "expose": ["health", "biology"],
    "collide": ["kinetics", "materials"],
    "impact": ["kinetics", "materials"],
    "drop": ["gravity", "kinetics"],
    "fall": ["gravity", "kinetics"],
    "trade": ["economy", "exchange"],
    "petition": ["society", "institutions"],
    "persuade": ["character", "agency", "knowledge"],
    "speak": ["character", "communication"],
    "observe": ["character", "knowledge"],
}


class CausalCritic:
    def analyze(
        self, world: World, scenario: Scenario, observation: Observation
    ) -> GapFinding | None:
        if observation.error:
            return None

        systems = self._affected_systems(world, scenario, observation)

        if observation.violations:
            descriptions = "; ".join(item.get("description", "") for item in observation.violations)
            violation_systems = [scenario.focus or "society", "constraints", "enforcement"]
            return GapFinding(
                scenario_id=scenario.id,
                scenario=scenario.title,
                observation=f"Action blocked by canon constraint(s): {descriptions}",
                gap_type=GapType.EXPLICIT_VIOLATION.value,
                hypothesis=(
                    "The scenario contradicts an existing constraint. This is an "
                    "enforcement observation, not evidence that canon should change."
                ),
                confidence=0.9,
                affected_systems=violation_systems,
                recommended_action=Recommendation.REVIEW_NOT_ERROR.value,
                matched_rule_ids=[],
                evidence=[item.get("constraint_id", "") for item in observation.violations],
                dedupe_key=self._dedupe_key(GapType.EXPLICIT_VIOLATION.value, violation_systems),
                focus=scenario.focus,
            )

        if observation.undefined_behavior:
            if not scenario.target:
                return None
            primary = self._primary_system(systems)
            hypothesis = self._hypothesis_for(primary, scenario)
            confidence = 0.92 if primary in {"electricity", "kinetics"} else 0.8
            return GapFinding(
                scenario_id=scenario.id,
                scenario=scenario.title,
                observation=observation.summary(),
                gap_type=GapType.UNDEFINED_INTERACTION.value,
                hypothesis=hypothesis,
                confidence=confidence,
                affected_systems=systems,
                recommended_action=Recommendation.PROPOSE_GENERAL_RULE.value,
                matched_rule_ids=[],
                evidence=[scenario.description, observation.summary()],
                dedupe_key=f"undefined_interaction:{primary}",
                focus=scenario.focus,
            )

        if observation.suppressed_rule_ids:
            return GapFinding(
                scenario_id=scenario.id,
                scenario=scenario.title,
                observation=(
                    "Multiple canon rules wrote the same state and the lower-priority "
                    f"rule(s) {', '.join(observation.suppressed_rule_ids)} were suppressed."
                ),
                gap_type=GapType.RULE_CONFLICT.value,
                hypothesis=(
                    "The canon contains overlapping rules with incompatible effects. "
                    "Resolve the conflict explicitly instead of adding another exception."
                ),
                confidence=0.85,
                affected_systems=systems,
                recommended_action=Recommendation.REVIEW_CONFLICT.value,
                matched_rule_ids=observation.matched_rule_ids,
                evidence=observation.notes,
                dedupe_key=f"rule_conflict:{','.join(observation.suppressed_rule_ids)}",
                focus=scenario.focus,
            )

        defies_reality = scenario.real_world_expectation and (
            "reality_check" in scenario.tags
            or any(
                world.rules[rule_id].defies_real_world_expectation
                for rule_id in observation.matched_rule_ids
                if rule_id in world.rules
            )
        )
        if defies_reality:
            return GapFinding(
                scenario_id=scenario.id,
                scenario=scenario.title,
                observation=(
                    f"{observation.summary()}. Real-world expectation: "
                    f"{scenario.real_world_expectation}"
                ),
                gap_type=GapType.ALLOWED_BUT_UNREALISTIC.value,
                hypothesis=(
                    "The outcome may be a deliberate fictional axiom. It is not a "
                    "contradiction unless it conflicts with another canon statement."
                ),
                confidence=0.55,
                affected_systems=systems,
                recommended_action=Recommendation.PRESERVE_CANON.value,
                matched_rule_ids=observation.matched_rule_ids,
                evidence=[scenario.real_world_expectation, observation.summary()],
                dedupe_key=self._dedupe_key(GapType.ALLOWED_BUT_UNREALISTIC.value, systems),
                focus=scenario.focus,
            )

        return None

    # ----------------------------------------------------------------- internals
    def _affected_systems(
        self, world: World, scenario: Scenario, observation: Observation
    ) -> list[str]:
        systems: list[str] = []
        target = world.entities.get(scenario.target or "")
        actor = world.entities.get(scenario.actor)
        # Target first: the thing being acted on usually names the relevant
        # mechanism more precisely than the actor does.
        referenced = [target, actor]
        location = world.entity_location(actor)
        if location:
            for tag in location.tags:
                systems.extend(TAG_SYSTEMS.get(tag, []))
        for entity in referenced:
            if entity:
                for tag in entity.tags:
                    systems.extend(TAG_SYSTEMS.get(tag, []))
        for tag in scenario.action.tags:
            systems.extend(ACTION_SYSTEMS.get(tag, []))
        systems.extend(ACTION_SYSTEMS.get(scenario.action.type, []))
        if not systems and scenario.focus:
            systems.append(scenario.focus)
        for rule_id in observation.matched_rule_ids:
            rule = world.rules.get(rule_id)
            if rule:
                systems.append(rule.domain)
        # Keep order stable and put the most explanatory system first.
        seen: set[str] = set()
        result = []
        for system in systems:
            if system and system not in seen:
                seen.add(system)
                result.append(system)
        if not result:
            return ["general"]
        primary = self._primary_system(result)
        return [primary] + [system for system in result if system != primary]

    def _primary_system(self, systems: list[str]) -> str:
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
            "materials",
            "health",
            "infrastructure",
        ]
        for candidate in priority:
            if candidate in systems:
                return candidate
        return systems[0] if systems else "general"

    def _dedupe_key(self, gap_type: str, systems: list[str]) -> str:
        primary = self._primary_system(systems)
        return f"{gap_type}:{primary}"

    def _hypothesis_for(self, primary: str, scenario: Scenario) -> str:
        if primary == "electricity":
            return (
                "The world lacks a general electrical conduction/interaction "
                "mechanism. This is a missing reusable rule, not merely a missing "
                "one-off consequence for this object."
            )
        if primary == "kinetics":
            return (
                "The world lacks a general impact/damage mechanism linking moving "
                "objects, structures, and downstream hazards."
            )
        if primary == "thermodynamics":
            return (
                "The world lacks a general heat-transfer or ignition mechanism; one "
                "rule may explain several related interactions."
            )
        if primary == "hydrology":
            return (
                "The world lacks a general fluid-conduction or immersion mechanism. "
                "Check whether this is a material rule rather than a water special case."
            )
        if primary == "society":
            return (
                "The world lacks a defined institutional response: enforcement, "
                "jurisdiction, or legitimacy is not yet mechanically represented."
            )
        if primary == "economy":
            return (
                "The world lacks exchange/ownership/scarcity rules that would make "
                "this transaction have consequences."
            )
        if primary == "character":
            return (
                "The world lacks a model of belief, intent, or refusal for this "
                "social action; character agency may be under-specified."
            )
        target = scenario.target or "the target"
        return (
            f"No general mechanism explains the interaction between the action and {target}. "
            "Consider the smallest reusable rule that also covers adjacent cases."
        )

    def dedupe_key(self, finding: GapFinding) -> str:
        if finding.dedupe_key:
            return finding.dedupe_key
        return fingerprint_payload(
            {
                "gap_type": finding.gap_type,
                "systems": finding.affected_systems,
                "focus": finding.focus,
            }
        )
