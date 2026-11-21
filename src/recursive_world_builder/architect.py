"""Rule Architect: turn findings into explicit, reviewable proposals.

A proposal never mutates canon.  It records the problem, the hypothesised root
cause, the exact rule diff, dependencies, expected impacts, conflicts, and a
counterfactual test plan.  A separate explicit approval applies it.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from .mechanisms import MechanismLibrary
from .model import (
    Conflict,
    ConflictSeverity,
    GapFinding,
    Proposal,
    ProposalStatus,
    Rule,
    RuleChange,
    RuleStatus,
    Scenario,
    ValidationError,
    World,
    utc_now,
)

logger = logging.getLogger(__name__)


class ProposalConflictError(RuntimeError):
    """Raised when applying a proposal would introduce a direct conflict."""

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts
        super().__init__(
            "Proposal has direct conflicts: "
            + "; ".join(conflict.description for conflict in conflicts)
        )


class StaleProposalError(RuntimeError):
    """Raised when the world changed after a proposal was drafted."""


class ProposalStateError(RuntimeError):
    """Raised when a proposal is not in a state that allows an operation."""


class RuleArchitect:
    def __init__(self, library: MechanismLibrary | None = None):
        self.library = library or MechanismLibrary()

    def build_proposal(
        self,
        world: World,
        finding: GapFinding,
        scenario: Scenario,
        proposal_id: str,
        *,
        existing_proposals: list[Proposal] | None = None,
    ) -> Proposal | None:
        if finding.recommended_action != "propose_general_rule":
            return None
        draft = self.library.draft(world, finding, scenario)
        if draft is None:
            logger.info("No scripted mechanism template for finding %s", finding.dedupe_key)
            return None
        existing_proposals = existing_proposals or []
        for proposal in existing_proposals:
            if proposal.provenance.get("mechanism_key") == draft.key and proposal.status in {
                ProposalStatus.PROPOSED.value,
                ProposalStatus.APPROVED.value,
                ProposalStatus.APPLIED.value,
            }:
                logger.info("Mechanism %s already has proposal %s", draft.key, proposal.id)
                return None

        deprecated = [
            rule.id
            for rule in draft.rules
            if world.rules.get(rule.id) is not None
            and world.rules[rule.id].status == RuleStatus.DEPRECATED.value
        ]
        if deprecated:
            logger.warning(
                "Mechanism %s would revive deprecated rule(s) %s; no proposal created",
                draft.key,
                ", ".join(deprecated),
            )
            return None

        rules: list[Rule] = []
        changes: list[RuleChange] = []
        amended_ids: set[str] = set()
        for rule in draft.rules:
            proposed = copy.deepcopy(rule)
            proposed.status = RuleStatus.PROPOSED.value
            proposed.provenance.update(
                {
                    "source": "scripted_mechanism_template",
                    "mechanism_key": draft.key,
                    "epistemic_status": "hypothesis_requiring_review",
                }
            )
            existing = world.rules.get(proposed.id)
            if existing is not None:
                if self._rule_equivalent(existing, proposed):
                    continue
                before = existing.to_dict()
                changes.append(
                    RuleChange(
                        action="modify",
                        rule_id=proposed.id,
                        before=before,
                        after=proposed.to_dict(),
                        reason=(
                            "Generalize the existing rule rather than adding a duplicate "
                            "with the same id."
                        ),
                    )
                )
                amended_ids.add(proposed.id)
            else:
                changes.append(
                    RuleChange(
                        action="add",
                        rule_id=proposed.id,
                        after=proposed.to_dict(),
                        reason="Add a reusable mechanism rule derived from the finding.",
                    )
                )
            rules.append(proposed)

        if not rules:
            logger.info("All proposed rules already exist unchanged; no proposal created")
            return None

        test_plan = [item for item in draft.test_plan if self._scenario_runnable(world, item)]
        if not test_plan:
            logger.warning("Mechanism %s produced no runnable counterfactual tests", draft.key)
            return None

        dependencies = sorted(
            {
                dependency
                for rule in rules
                for dependency in rule.depends_on
                if dependency not in {item.id for item in rules}
            }
        )
        conflicts = self.detect_conflicts(world, rules, amended_rule_ids=amended_ids)
        proposal = Proposal(
            id=proposal_id,
            world_id=world.world_id,
            world_version=world.canon_version,
            title=draft.title,
            problem=draft.problem,
            root_cause_hypothesis=draft.root_cause,
            rationale=draft.rationale,
            findings=[finding],
            rules=rules,
            rule_changes=changes,
            expected_impacts=draft.expected_impacts,
            affected_systems=sorted(set(draft.affected_systems)),
            potential_conflicts=conflicts,
            test_plan=test_plan,
            dependencies=dependencies,
            generality=draft.generality,
            status=ProposalStatus.PROPOSED.value,
            confidence=draft.confidence,
            confidence_kind="subjective_agent_judgment",
            calibrated=False,
            provenance={
                "mode": "scripted_mechanism_template",
                "mechanism_key": draft.key,
                "epistemic_status": "hypothesis_requiring_review",
                "notice": (
                    "Generated by a deterministic template, not by a calibrated model. "
                    "Review before approval."
                ),
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.validate_proposal(world, proposal)
        logger.info(
            "Built proposal %s (%s) with %d rule(s), %d conflict(s)",
            proposal.id,
            proposal.title,
            len(proposal.rules),
            len(proposal.potential_conflicts),
        )
        return proposal

    # ------------------------------------------------------------------ ingest
    def ingest_external_proposal(
        self,
        world: World,
        payload: dict[str, Any],
        proposal_id: str,
        *,
        existing_proposals: list[Proposal] | None = None,
    ) -> Proposal:
        """Accept a host-agent-authored proposal JSON document."""

        raw = dict(payload)
        raw.setdefault("id", proposal_id)
        raw["world_id"] = world.world_id
        raw["world_version"] = world.canon_version
        raw["status"] = ProposalStatus.PROPOSED.value
        raw.setdefault("confidence_kind", "subjective_agent_judgment")
        raw["calibrated"] = False
        raw.setdefault("created_at", utc_now())
        raw["updated_at"] = utc_now()
        raw.setdefault(
            "provenance",
            {
                "mode": "host_agent",
                "epistemic_status": "host_reasoning_requires_review",
            },
        )
        rules = [Rule.from_dict(item) for item in raw.get("rules", [])]
        if not rules:
            raise ValidationError("External proposal needs at least one rule")
        for rule in rules:
            rule.status = RuleStatus.PROPOSED.value
        raw["rules"] = [rule.to_dict() for rule in rules]
        if not raw.get("rule_changes"):
            changes: list[dict[str, Any]] = []
            for rule in rules:
                existing = world.rules.get(rule.id)
                if existing is None:
                    changes.append(
                        {
                            "action": "add",
                            "rule_id": rule.id,
                            "after": rule.to_dict(),
                            "reason": "Added by host-agent proposal.",
                        }
                    )
                elif not self._rule_equivalent(existing, rule):
                    changes.append(
                        {
                            "action": "modify",
                            "rule_id": rule.id,
                            "before": existing.to_dict(),
                            "after": rule.to_dict(),
                            "reason": "Modified by host-agent proposal.",
                        }
                    )
            raw["rule_changes"] = changes
        if not raw.get("generality"):
            raw["generality"] = {
                "scope": "not stated by author",
                "special_case": None,
                "reusable": None,
                "requires_review": True,
            }
        proposal = Proposal.from_dict(raw)
        amended = {change.rule_id for change in proposal.rule_changes if change.action == "modify"}
        proposal.potential_conflicts = self.detect_conflicts(
            world, proposal.rules, amended_rule_ids=amended
        )
        self.validate_proposal(world, proposal)
        for existing in existing_proposals or []:
            if existing.id == proposal.id:
                raise ValidationError(f"Proposal id already exists: {proposal.id}")
        return proposal

    # --------------------------------------------------------------- validation
    def validate_proposal(self, world: World, proposal: Proposal) -> None:
        errors: list[str] = []
        if proposal.world_id != world.world_id:
            errors.append(
                f"Proposal world_id {proposal.world_id!r} does not match {world.world_id!r}"
            )
        if proposal.world_version < 1:
            errors.append("Proposal world_version must be >= 1")
        for field_name in ("problem", "root_cause_hypothesis", "rationale", "title"):
            if not getattr(proposal, field_name).strip():
                errors.append(f"Proposal {proposal.id}: {field_name} cannot be empty")
        if not proposal.rules:
            errors.append(f"Proposal {proposal.id}: at least one proposed rule is required")
        if not proposal.rule_changes:
            errors.append(f"Proposal {proposal.id}: a rule diff is required")
        if not proposal.expected_impacts:
            errors.append(f"Proposal {proposal.id}: expected_impacts cannot be empty")
        if not proposal.test_plan:
            errors.append(f"Proposal {proposal.id}: test_plan cannot be empty")
        if not 0.0 <= proposal.confidence <= 1.0:
            errors.append("Proposal confidence must be between 0 and 1")
        if proposal.calibrated:
            errors.append(
                "Proposal confidence cannot be marked calibrated: this project does not "
                "produce calibrated statistical probabilities."
            )
        if proposal.confidence_kind != "subjective_agent_judgment":
            errors.append("confidence_kind must be subjective_agent_judgment")
        rule_ids = {rule.id for rule in proposal.rules}
        for rule in proposal.rules:
            errors.extend(rule.validate())
            if rule.status != RuleStatus.PROPOSED.value:
                errors.append(f"Rule {rule.id}: proposal rules must have status 'proposed'")
            existing = world.rules.get(rule.id)
            if existing is not None and existing.status == RuleStatus.DEPRECATED.value:
                errors.append(
                    f"Rule {rule.id}: deprecated rules cannot be revived automatically. "
                    "Add a new rule with a new id or ask the user for an explicit canon edit."
                )
        changed_ids = {change.rule_id for change in proposal.rule_changes}
        if changed_ids - rule_ids:
            errors.append(
                "rule_changes references rules that are not present in the proposal: "
                + ", ".join(sorted(changed_ids - rule_ids))
            )
        if rule_ids - changed_ids:
            errors.append(
                "Every proposed rule needs a recorded diff; missing: "
                + ", ".join(sorted(rule_ids - changed_ids))
            )
        if "special_case" not in proposal.generality:
            errors.append(
                "generality.special_case is required so reviewers can see whether this "
                "is a reusable mechanism or a deliberate exception."
            )
        for dependency in proposal.dependencies:
            if dependency not in world.rules and dependency not in rule_ids:
                errors.append(f"Proposal dependency {dependency!r} does not exist")
        for rule in proposal.rules:
            for dependency in rule.depends_on:
                if dependency not in world.rules and dependency not in rule_ids:
                    errors.append(f"Rule {rule.id}: unresolved dependency {dependency!r}")
        for scenario in proposal.test_plan:
            if scenario.actor not in world.entities:
                errors.append(f"Test scenario {scenario.id}: unknown actor {scenario.actor!r}")
            if scenario.target and scenario.target not in world.entities:
                errors.append(f"Test scenario {scenario.id}: unknown target {scenario.target!r}")
            for assumption in scenario.assumptions:
                if assumption.entity_id not in world.entities:
                    errors.append(
                        f"Test scenario {scenario.id}: unknown assumption entity "
                        f"{assumption.entity_id!r}"
                    )
        if proposal.status not in {item.value for item in ProposalStatus}:
            errors.append(f"Proposal {proposal.id}: unknown status {proposal.status!r}")
        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------- conflicts
    def detect_conflicts(
        self,
        world: World,
        proposed_rules: list[Rule],
        *,
        amended_rule_ids: set[str] | None = None,
    ) -> list[Conflict]:
        amended = amended_rule_ids or set()
        conflicts: list[Conflict] = []
        seen: set[tuple[str, str, str]] = set()

        def add(
            severity: str, kind: str, description: str, ids: list[str], resolution: str
        ) -> None:
            key = (severity, kind, ",".join(sorted(ids)))
            if key in seen:
                return
            seen.add(key)
            conflicts.append(
                Conflict(
                    id=f"C-{len(conflicts) + 1:03d}",
                    severity=severity,
                    kind=kind,
                    description=description,
                    rule_ids=ids,
                    resolution=resolution,
                )
            )

        for proposed in proposed_rules:
            for existing in world.canon_rules():
                if proposed.id == existing.id:
                    if proposed.id not in amended:
                        add(
                            ConflictSeverity.DIRECT.value,
                            "duplicate_rule_id",
                            f"Proposed rule {proposed.id} reuses an existing canon rule id "
                            "without being declared as a modification.",
                            [proposed.id],
                            "Use a new id or include an explicit modify diff.",
                        )
                    continue
                if proposed.id in existing.conflicts_with or existing.id in proposed.conflicts_with:
                    add(
                        ConflictSeverity.DIRECT.value,
                        "declared_conflict",
                        f"{proposed.id} and {existing.id} are explicitly marked as conflicting.",
                        [proposed.id, existing.id],
                        "Resolve the declared conflict before approval.",
                    )
                    continue
                if not proposed.matcher.overlaps(existing.matcher):
                    continue
                conflict = self._effect_conflict(proposed, existing)
                if conflict:
                    severity, description = conflict
                    add(
                        severity,
                        "incompatible_effects",
                        description,
                        [proposed.id, existing.id],
                        "Narrow the matchers, change priority semantics, or amend the "
                        "existing rule.",
                    )
                elif proposed.matcher.to_dict() == existing.matcher.to_dict():
                    add(
                        ConflictSeverity.POTENTIAL.value,
                        "redundant_matcher",
                        f"{proposed.id} matches exactly like existing rule {existing.id}. "
                        "Prefer modifying the existing rule unless the effects are "
                        "genuinely orthogonal.",
                        [proposed.id, existing.id],
                        "Merge into the existing rule or document why both are needed.",
                    )

            for constraint in world.active_constraints():
                if constraint.kind != "prohibition" or not constraint.matcher:
                    continue
                if constraint.matcher.overlaps(proposed.matcher):
                    add(
                        ConflictSeverity.POTENTIAL.value,
                        "prohibition_overlap",
                        f"Proposed rule {proposed.id} overlaps prohibition {constraint.id}. "
                        "The rule may be unreachable for covered actions.",
                        [proposed.id, constraint.id],
                        "Check whether the action is legal; if not, model the "
                        "enforcement path instead.",
                    )

        for index, left in enumerate(proposed_rules):
            for right in proposed_rules[index + 1 :]:
                if not left.matcher.overlaps(right.matcher):
                    continue
                conflict = self._effect_conflict(left, right)
                if conflict:
                    severity, description = conflict
                    add(
                        severity,
                        "internal_incompatible_effects",
                        f"{left.id} conflicts with {right.id} inside the same proposal: "
                        f"{description}",
                        [left.id, right.id],
                        "Restructure the proposal so each state write has one owner.",
                    )
        return conflicts

    def _effect_conflict(self, left: Rule, right: Rule) -> tuple[str, str] | None:
        left_writes = self._writes(left)
        right_writes = self._writes(right)
        for key, left_kind in left_writes.items():
            if key not in right_writes:
                continue
            right_kind = right_writes[key]
            if key[0] == "property":
                _, target, prop = key
                if left_kind[0] == "set" and right_kind[0] == "set":
                    if left_kind[1] != right_kind[1]:
                        return (
                            ConflictSeverity.DIRECT.value,
                            f"Both rules set {target}.{prop} to different values "
                            f"({left_kind[1]!r} vs {right_kind[1]!r}).",
                        )
                elif {left_kind[0], right_kind[0]} == {"set", "modify"}:
                    return (
                        ConflictSeverity.POTENTIAL.value,
                        f"Both rules write {target}.{prop} with set/modify semantics.",
                    )
            elif key[0] == "tag" and {left_kind[0], right_kind[0]} == {"add", "remove"}:
                _, target, tag = key
                return (
                    ConflictSeverity.DIRECT.value,
                    f"One rule adds tag {tag!r} to {target} while the other removes it.",
                )
        return None

    @staticmethod
    def _writes(rule: Rule) -> dict[tuple[str, ...], tuple[str, Any]]:
        writes: dict[tuple[str, ...], tuple[str, Any]] = {}
        for effect in rule.effects:
            if effect.kind == "set_property":
                writes[("property", effect.target, effect.property or "")] = (
                    "set",
                    effect.value,
                )
            elif effect.kind == "modify_property":
                writes[("property", effect.target, effect.property or "")] = (
                    "modify",
                    effect.delta,
                )
            elif effect.kind == "add_tag":
                writes[("tag", effect.target, effect.tag or "")] = ("add", effect.tag)
            elif effect.kind == "remove_tag":
                writes[("tag", effect.target, effect.tag or "")] = ("remove", effect.tag)
        return writes

    # -------------------------------------------------------------------- apply
    def apply_proposal(
        self,
        world: World,
        proposal: Proposal,
        *,
        accept_conflicts: bool = False,
    ) -> World:
        if proposal.status == ProposalStatus.APPLIED.value:
            raise ProposalStateError(f"Proposal {proposal.id} is already applied")
        if proposal.status != ProposalStatus.APPROVED.value:
            raise ProposalStateError(
                f"Proposal {proposal.id} must be explicitly approved before applying"
            )
        if proposal.world_version != world.canon_version:
            raise StaleProposalError(
                f"Proposal targets world version {proposal.world_version}, "
                f"but canon is now version {world.canon_version}"
            )
        amended = {change.rule_id for change in proposal.rule_changes if change.action == "modify"}
        conflicts = self.detect_conflicts(world, proposal.rules, amended_rule_ids=amended)
        direct = [item for item in conflicts if item.severity == ConflictSeverity.DIRECT.value]
        if direct and not accept_conflicts:
            raise ProposalConflictError(direct)
        self.validate_proposal(world, proposal)

        old_version = world.canon_version
        changes: list[dict[str, Any]] = []
        for proposed in proposal.rules:
            new_rule = Rule.from_dict(proposed.to_dict())
            new_rule.provenance.update(
                {
                    "proposal_id": proposal.id,
                    "applied_at": utc_now(),
                    "mechanism_key": proposal.provenance.get("mechanism_key", ""),
                }
            )
            existing = world.rules.get(new_rule.id)
            if existing is not None:
                before = existing.to_dict()
                new_rule.version = existing.version + 1
                new_rule.status = RuleStatus.CANON.value
                world.rules[new_rule.id] = new_rule
                changes.append(
                    {
                        "action": "modify",
                        "rule_id": new_rule.id,
                        "before": before,
                        "after": new_rule.to_dict(),
                    }
                )
            else:
                new_rule.version = 1
                new_rule.status = RuleStatus.CANON.value
                world.rules[new_rule.id] = new_rule
                changes.append(
                    {
                        "action": "add",
                        "rule_id": new_rule.id,
                        "after": new_rule.to_dict(),
                    }
                )
            for superseded in new_rule.supersedes:
                if superseded in world.rules:
                    world.rules[superseded].status = RuleStatus.DEPRECATED.value
                    changes.append(
                        {
                            "action": "deprecate",
                            "rule_id": superseded,
                            "reason": f"Superseded by {new_rule.id}",
                        }
                    )

        world.canon_version = old_version + 1
        world.updated_at = utc_now()
        history_entry = {
            "version": world.canon_version,
            "previous_version": old_version,
            "at": world.updated_at,
            "proposal_id": proposal.id,
            "title": proposal.title,
            "rationale": proposal.rationale,
            "changes": changes,
            "conflicts_accepted": [
                item.to_dict()
                for item in conflicts
                if item.severity == ConflictSeverity.DIRECT.value
            ]
            if accept_conflicts
            else [],
        }
        world.history.append(history_entry)
        world.events.append(
            {
                "id": f"EV-{len(world.events) + 1:05d}",
                "type": "rule_patch_applied",
                "at": world.updated_at,
                "version": world.canon_version,
                "proposal_id": proposal.id,
                "title": proposal.title,
                "changes": [change["rule_id"] for change in changes],
            }
        )
        world.assert_valid()

        proposal.status = ProposalStatus.APPLIED.value
        proposal.applied_version = world.canon_version
        proposal.updated_at = utc_now()
        proposal.decision.update(
            {
                "action": "approved",
                "at": proposal.updated_at,
                "accepted_conflicts": accept_conflicts,
                "resulting_version": world.canon_version,
            }
        )
        return world

    # ------------------------------------------------------------------ helpers
    def reject_proposal(self, proposal: Proposal, reason: str = "") -> Proposal:
        if proposal.status == ProposalStatus.APPLIED.value:
            raise ProposalStateError("Cannot reject a proposal that is already applied")
        proposal.status = ProposalStatus.REJECTED.value
        proposal.updated_at = utc_now()
        proposal.decision.update(
            {"action": "rejected", "reason": reason, "at": proposal.updated_at}
        )
        return proposal

    @staticmethod
    def _scenario_runnable(world: World, scenario: Scenario) -> bool:
        if scenario.actor not in world.entities:
            return False
        if scenario.target and scenario.target not in world.entities:
            return False
        return all(item.entity_id in world.entities for item in scenario.assumptions)

    @staticmethod
    def _rule_equivalent(left: Rule, right: Rule) -> bool:
        keys = (
            "matcher",
            "effects",
            "domain",
            "priority",
            "depends_on",
            "tags",
            "supersedes",
            "defies_real_world_expectation",
        )
        left_data = left.to_dict()
        right_data = right.to_dict()
        return all(left_data.get(key) == right_data.get(key) for key in keys)
