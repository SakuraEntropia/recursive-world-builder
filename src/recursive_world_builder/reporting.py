"""Markdown reports.

Reports are deliberately explicit about epistemics: what was simulated
deterministically, what was inferred by an agent, and what still requires a
human decision.
"""

from __future__ import annotations

import json
from typing import Any

from .model import (
    ApprovalResult,
    Proposal,
    RegressionResult,
    RunResult,
    World,
)


def _bullets(items: list[str], fallback: str = "_none_") -> str:
    if not items:
        return fallback
    return "\n".join(f"- {item}" for item in items)


def _effect_line(effect: dict[str, Any]) -> str:
    if effect.get("kind") == "emit_event":
        return f"event `{effect.get('event')}` on `{effect.get('target_id')}`"
    if effect.get("tag"):
        action = effect.get("action", "add")
        return f"{action} tag `{effect.get('tag')}` on `{effect.get('target_id')}`"
    if effect.get("property"):
        return (
            f"`{effect.get('target_id')}.{effect.get('property')}` "
            f"{effect.get('before')!r} → {effect.get('after')!r}"
        )
    return str(effect)


def render_run_report(world: World, result: RunResult) -> str:
    lines = [
        "# Recursive World Builder — Exploration Report",
        "",
        f"- **World:** {world.title} (`{world.world_id}`)",
        f"- **Canon version:** {world.canon_version}",
        f"- **Run:** `{result.run_id}`",
        f"- **Focus:** {result.focus}",
        f"- **Architect mode:** {result.architect_mode}",
        f"- **Scenarios run:** {result.scenarios_run}",
        f"- **Duplicates skipped:** {result.duplicates_skipped}",
        f"- **Findings:** {len(result.findings)}",
        f"- **New proposals:** {len(result.proposals)}",
        f"- **Stop reason:** `{result.stop_reason}`",
        f"- **Stop detail:** {result.stop_detail}",
        "",
        "## Epistemic status",
        "",
        "The scenario outcomes below were produced by the deterministic rule engine.",
        "Gap hypotheses and confidence values are subjective agent judgements, **not**",
        "calibrated statistical probabilities. No proposal in this report has changed canon.",
        "",
        "## Budgets",
        "",
        "| Limit | Value |",
        "| --- | ---: |",
    ]
    for key, value in result.limits.to_dict().items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Rounds",
            "",
            "| Round | Scenarios | New findings | Proposals |",
            "| ---: | ---: | ---: | --- |",
        ]
    )
    for round_record in result.rounds:
        proposals = ", ".join(round_record.proposal_ids) or "—"
        lines.append(
            f"| {round_record.index} | {len(round_record.scenario_ids)} | "
            f"{round_record.new_findings} | {proposals} |"
        )
    if not result.rounds:
        lines.append("| — | 0 | 0 | — |")

    lines.extend(["", "## Findings", ""])
    if not result.findings:
        lines.append("_No causal gaps were detected within this run's budget._")
    for index, finding in enumerate(result.findings, start=1):
        lines.extend(
            [
                f"### {index}. {finding.scenario}",
                "",
                f"- **Gap type:** `{finding.gap_type}`",
                f"- **Observation:** {finding.observation}",
                f"- **Hypothesis:** {finding.hypothesis}",
                f"- **Confidence:** {finding.confidence:.2f} "
                f"({finding.confidence_kind}; calibrated: {finding.calibrated})",
                f"- **Affected systems:** {', '.join(finding.affected_systems)}",
                f"- **Recommended action:** `{finding.recommended_action}`",
                f"- **Matched rules:** {', '.join(finding.matched_rule_ids) or 'none'}",
                f"- **Dedupe key:** `{finding.dedupe_key}`",
                "",
            ]
        )

    lines.extend(["", "## Proposals (pending human approval)", ""])
    if not result.proposals:
        lines.append("_No proposals were generated in this run._")
    for proposal in result.proposals:
        lines.extend(
            [
                f"### `{proposal.id}` — {proposal.title}",
                "",
                f"- **Status:** `{proposal.status}`",
                f"- **Problem:** {proposal.problem}",
                f"- **Root-cause hypothesis:** {proposal.root_cause_hypothesis}",
                f"- **Affected systems:** {', '.join(proposal.affected_systems)}",
                f"- **Confidence:** {proposal.confidence:.2f} (subjective; uncalibrated)",
                f"- **Rules:** {', '.join(rule.id for rule in proposal.rules)}",
                f"- **Conflicts:** {len(proposal.potential_conflicts)}",
                f"- **Counterfactual tests:** {', '.join(item.id for item in proposal.test_plan)}",
                "",
                "**Expected impacts**",
                "",
                _bullets(proposal.expected_impacts),
                "",
            ]
        )
    lines.extend(
        [
            "",
            "## Approval boundary",
            "",
            "Nothing above is canon. Review a proposal and then run "
            "`rwb approve <world> <proposal-id>` to apply it explicitly.",
            "",
        ]
    )
    return "\n".join(lines)


def render_modification_report(
    world: World,
    proposal: Proposal,
    regression_results: list[RegressionResult],
    post_tests: list[dict[str, Any]],
) -> str:
    lines = [
        "# World Rule Modification Report",
        "",
        f"- **World:** {world.title} (`{world.world_id}`)",
        f"- **Proposal:** `{proposal.id}` — {proposal.title}",
        f"- **Applied canon version:** {world.canon_version}",
        f"- **Previous version:** {proposal.world_version}",
        f"- **Proposal confidence:** {proposal.confidence:.2f} "
        f"({proposal.confidence_kind}; calibrated: {proposal.calibrated})",
        f"- **Provenance:** `{proposal.provenance.get('mode', 'unknown')}`",
        "",
        "## Decision",
        "",
        "The proposal was explicitly approved and applied. Rejected proposals never",
        "modify canon. Confidence remains a subjective hypothesis, not a statistical result.",
        "",
        "## Problem",
        "",
        proposal.problem,
        "",
        "## Root-cause hypothesis",
        "",
        proposal.root_cause_hypothesis,
        "",
        "## Rationale",
        "",
        proposal.rationale,
        "",
        "## Rule diff",
        "",
        "| Action | Rule | Summary |",
        "| --- | --- | --- |",
    ]
    for change in proposal.rule_changes:
        lines.append(f"| {change.action} | `{change.rule_id}` | {change.reason or '—'} |")
    lines.append("")
    modifications = [change for change in proposal.rule_changes if change.action == "modify"]
    if modifications:
        lines.extend(["### Before / after", ""])
        for change in modifications:
            before = change.before or {}
            after = change.after or {}
            lines.extend(
                [
                    f"**`{change.rule_id}`**",
                    "",
                    "Before:",
                    "",
                    "```json",
                    json.dumps(
                        {
                            "matcher": before.get("matcher"),
                            "effects": before.get("effects"),
                            "version": before.get("version"),
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    "```",
                    "",
                    "After:",
                    "",
                    "```json",
                    json.dumps(
                        {
                            "matcher": after.get("matcher"),
                            "effects": after.get("effects"),
                            "status": "proposed (becomes canon on approval)",
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    "```",
                    "",
                ]
            )
    for rule in proposal.rules:
        lines.extend(
            [
                f"### `{rule.id}` — {rule.name}",
                "",
                f"- **Domain:** `{rule.domain}`",
                f"- **Priority:** {rule.priority}",
                f"- **Depends on:** {', '.join(rule.depends_on) or 'none'}",
                f"- **Tags:** {', '.join(rule.tags) or 'none'}",
                f"- **Matches actions:** {', '.join(rule.matcher.action_types)}",
                f"- **Target tags:** {', '.join(rule.matcher.target_tags_any) or 'any'}",
                f"- **Description:** {rule.description}",
                "",
                "**Effects**",
                "",
                _bullets([effect.describe() for effect in rule.effects]),
                "",
            ]
        )

    lines.extend(["## Conflicts", ""])
    if proposal.potential_conflicts:
        lines.extend(
            [
                "| ID | Severity | Kind | Description | Resolution |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for conflict in proposal.potential_conflicts:
            lines.append(
                f"| {conflict.id} | {conflict.severity} | {conflict.kind} | "
                f"{conflict.description} | {conflict.resolution or '—'} |"
            )
    else:
        lines.append("_No conflicts detected at approval time._")

    lines.extend(
        [
            "",
            "## Regression gate",
            "",
            "| Case | Result | Expected | Actual |",
            "| --- | --- | --- | --- |",
        ]
    )
    if regression_results:
        for result in regression_results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(
                f"| `{result.case_id}` | {status} | {result.expected_summary or '—'} | "
                f"{result.actual_summary or '—'} |"
            )
    else:
        lines.append("| — | skipped | no regression cases | — |")

    lines.extend(["", "## Counterfactual re-tests", ""])
    if not post_tests:
        lines.append("_The proposal had no runnable test plan._")
    for item in post_tests:
        scenario = item.get("scenario", {})
        observation = item.get("observation", {})
        lines.extend(
            [
                f"### `{scenario.get('id')}` — {scenario.get('title')}",
                "",
                f"- **Action:** `{scenario.get('action', {}).get('type')}`",
                "- **Matched rules:** "
                f"{', '.join(observation.get('matched_rule_ids', [])) or 'none'}",
                f"- **Result:** {observation.get('summary', '')}",
                f"- **Fingerprint:** `{observation.get('fingerprint', '')}`",
                "",
            ]
        )
        effects = observation.get("effects", [])
        if effects:
            lines.append("**Effects**")
            lines.append("")
            lines.append(_bullets([_effect_line(effect) for effect in effects]))
            lines.append("")
        if observation.get("notes"):
            lines.append("**Notes**")
            lines.append("")
            lines.append(_bullets(observation["notes"]))
            lines.append("")

    lines.extend(
        [
            "",
            "## Remaining uncertainty",
            "",
            "- The deterministic engine applies only the rules in canon.",
            "- It does not simulate continuous physics, fluid dynamics, markets, or minds.",
            "- The new mechanism is a hypothesis that may still conflict with future canon.",
            "- Regression passing means existing deterministic probes are unchanged, not that",
            "  the world is artistically or narratively complete.",
            "",
        ]
    )
    return "\n".join(lines)


def render_proposals(proposals: list[Proposal]) -> str:
    if not proposals:
        return "No proposals.\n"
    lines = ["Proposals", "=========", ""]
    for proposal in proposals:
        lines.extend(
            [
                f"[{proposal.id}] {proposal.status.upper()} — {proposal.title}",
                f"  world: {proposal.world_id} v{proposal.world_version}",
                f"  affected: {', '.join(proposal.affected_systems)}",
                f"  rules: {', '.join(rule.id for rule in proposal.rules)}",
                f"  conflicts: {len(proposal.potential_conflicts)}",
                f"  tests: {len(proposal.test_plan)}",
                "",
            ]
        )
    return "\n".join(lines)


def render_world_summary(world: World) -> str:
    lines = [
        f"{world.title} ({world.world_id}) — canon v{world.canon_version}",
        f"entities: {len(world.entities)}  locations: {len(world.locations)}  "
        f"rules: {len(world.rules)}  constraints: {len(world.constraints)}  "
        f"canon facts: {len(world.canon)}",
        "",
        "Canon rules:",
    ]
    for rule in world.canon_rules():
        lines.append(f"  [{rule.domain}] {rule.id}: {rule.name} (v{rule.version})")
    if not world.rules:
        lines.append("  (none)")
    return "\n".join(lines)


def render_approval_result(result: ApprovalResult) -> str:
    lines = [
        f"Proposal {result.proposal_id}: {'APPLIED' if result.applied else 'NOT APPLIED'}",
        f"World version: {result.world_version}",
        result.message,
    ]
    if result.rollback_performed:
        lines.append("ROLLBACK PERFORMED")
    if result.regression_results:
        lines.append(
            "Regression: "
            + ", ".join(
                f"{item.case_id}={'PASS' if item.passed else 'FAIL'}"
                for item in result.regression_results
            )
        )
    if result.report_path:
        lines.append(f"Report: {result.report_path}")
    return "\n".join(lines)
