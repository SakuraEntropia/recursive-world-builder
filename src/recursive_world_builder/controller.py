"""Recursive Controller.

The controller owns budgets, deduplication, approval, regression gates, and
rollback.  It is intentionally finite: every run has hard round/scenario/rule
caps, and repeated findings stop the loop instead of generating endless
variations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .architect import (
    ProposalConflictError,
    ProposalStateError,
    RuleArchitect,
    StaleProposalError,
)
from .critic import CausalCritic
from .explorer import Explorer
from .model import (
    ApprovalResult,
    GapFinding,
    Proposal,
    ProposalStatus,
    RegressionCase,
    RegressionResult,
    RunLimits,
    RunResult,
    RunRound,
    World,
    utc_now,
)
from .reporting import render_modification_report, render_run_report
from .storage import WorldStore

logger = logging.getLogger(__name__)


class RecursiveController:
    def __init__(
        self,
        store: WorldStore,
        *,
        limits: RunLimits | None = None,
        architect_mode: str = "scripted",
    ):
        self.store = store
        self.limits = limits or RunLimits()
        self.limits.validate()
        if architect_mode not in {"scripted", "host"}:
            raise ValueError("architect_mode must be 'scripted' or 'host'")
        self.architect_mode = architect_mode
        self.explorer = Explorer(
            external_path=store.root / "exploration_cases.json",
        )
        self.critic = CausalCritic()
        self.architect = RuleArchitect()

    # ------------------------------------------------------------------ explore
    def explore(
        self,
        *,
        focus: str = "all",
        max_rounds: int | None = None,
        max_scenarios: int | None = None,
        max_new_rules: int | None = None,
        max_proposals: int | None = None,
    ) -> RunResult:
        limits = self._effective_limits(
            max_rounds=max_rounds,
            max_scenarios=max_scenarios,
            max_new_rules=max_new_rules,
            max_proposals=max_proposals,
        )
        world = self.store.load_world()
        proposals = self.store.load_proposals()
        seen_findings: set[str] = set()
        seen_scenarios: set[str] = set()
        run_proposals: list[Proposal] = []
        findings: list[GapFinding] = []
        rounds: list[RunRound] = []
        scenarios_run = 0
        duplicates_skipped = 0
        new_rule_count = 0
        empty_streak = 0
        stop_reason = ""
        stop_detail = ""
        started_at = utc_now()
        run_id = self._run_id(focus)

        for round_index in range(1, limits.max_rounds + 1):
            remaining = limits.max_scenarios - scenarios_run
            if remaining <= 0:
                stop_reason = "max_scenarios"
                stop_detail = f"Scenario budget of {limits.max_scenarios} reached."
                break
            scenarios = self.explorer.plan(
                world,
                focus=focus,
                limit=remaining,
                exclude_keys=seen_scenarios,
            )
            if not scenarios:
                stop_reason = "no_candidate_scenarios"
                stop_detail = (
                    "No new scenario could be generated for this focus. This is a normal "
                    "finite stopping condition, not necessarily a complete world."
                )
                break

            round_record = RunRound(index=round_index)
            round_findings = 0
            for scenario in scenarios:
                if scenarios_run >= limits.max_scenarios:
                    break
                scenarios_run += 1
                seen_scenarios.add(scenario.key())
                round_record.scenario_ids.append(scenario.id)
                observation = self.explorer.observe(world, scenario)
                finding = self.critic.analyze(world, scenario, observation)
                if finding is None:
                    continue
                key = self.critic.dedupe_key(finding)
                if key in seen_findings:
                    duplicates_skipped += 1
                    continue
                seen_findings.add(key)
                findings.append(finding)
                round_record.finding_keys.append(key)
                round_findings += 1
                logger.info("Finding %s: %s", finding.gap_type, finding.scenario)

                if self.architect_mode != "scripted":
                    continue
                if len(run_proposals) >= limits.max_proposals:
                    stop_reason = "max_proposals"
                    stop_detail = f"Proposal budget of {limits.max_proposals} reached."
                    continue
                if new_rule_count >= limits.max_new_rules:
                    stop_reason = "max_new_rules"
                    stop_detail = f"New-rule budget of {limits.max_new_rules} reached."
                    continue
                proposal = self.architect.build_proposal(
                    world,
                    finding,
                    scenario,
                    proposal_id=self.store.next_proposal_id(proposals),
                    existing_proposals=proposals,
                )
                if proposal is None:
                    continue
                if new_rule_count + len(proposal.rules) > limits.max_new_rules:
                    stop_reason = "max_new_rules"
                    stop_detail = (
                        f"Proposal {proposal.id} needs {len(proposal.rules)} rules but only "
                        f"{limits.max_new_rules - new_rule_count} remain in this run."
                    )
                    continue
                proposals.append(proposal)
                run_proposals.append(proposal)
                new_rule_count += len(proposal.rules)
                round_record.proposal_ids.append(proposal.id)
                self.store.upsert_proposal(proposal)

            round_record.new_findings = round_findings
            rounds.append(round_record)
            if round_findings == 0:
                empty_streak += 1
            else:
                empty_streak = 0

            if stop_reason in {"max_proposals", "max_new_rules"}:
                break
            if new_rule_count >= limits.max_new_rules:
                stop_reason = "max_new_rules"
                stop_detail = f"New-rule budget of {limits.max_new_rules} reached."
                break
            if len(run_proposals) >= limits.max_proposals:
                stop_reason = "max_proposals"
                stop_detail = f"Proposal budget of {limits.max_proposals} reached."
                break
            if scenarios_run >= limits.max_scenarios:
                stop_reason = "max_scenarios"
                stop_detail = f"Scenario budget of {limits.max_scenarios} reached."
                break
            if empty_streak >= limits.max_consecutive_empty_rounds:
                stop_reason = "no_new_findings"
                stop_detail = (
                    f"No new findings for {empty_streak} consecutive round(s); "
                    "stopping to avoid repetitive expansion."
                )
                break
        else:
            stop_reason = "max_rounds"
            stop_detail = f"Round budget of {limits.max_rounds} reached."

        if not stop_reason:
            stop_reason = "max_rounds"
            stop_detail = f"Round budget of {limits.max_rounds} reached."

        result = RunResult(
            run_id=run_id,
            world_id=world.world_id,
            world_version=world.canon_version,
            focus=focus,
            rounds=rounds,
            findings=findings,
            proposals=run_proposals,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
            scenarios_run=scenarios_run,
            duplicates_skipped=duplicates_skipped,
            architect_mode=self.architect_mode,
            limits=limits,
            started_at=started_at,
            finished_at=utc_now(),
        )
        run_path = self.store.save_run(result)
        report_path = self.store.write_report(f"run-{run_id}.md", render_run_report(world, result))
        logger.info(
            "Exploration finished: %s findings, %s proposals, stop=%s; run=%s report=%s",
            len(findings),
            len(run_proposals),
            stop_reason,
            run_path,
            report_path,
        )
        return result

    def _effective_limits(self, **overrides: int | None) -> RunLimits:
        values = self.limits.to_dict()
        for key, value in overrides.items():
            if value is not None:
                values[key] = int(value)
        limits = RunLimits(**values)
        limits.validate()
        return limits

    # ------------------------------------------------------------------ approve
    def approve(
        self,
        proposal_id: str,
        *,
        accept_conflicts: bool = False,
        write_report: bool = True,
    ) -> ApprovalResult:
        world = self.store.load_world()
        proposals = self.store.load_proposals()
        proposal = next((item for item in proposals if item.id == proposal_id), None)
        if proposal is None:
            raise ProposalStateError(f"Unknown proposal: {proposal_id}")
        if proposal.status == ProposalStatus.APPLIED.value:
            raise ProposalStateError(f"Proposal {proposal_id} is already applied")
        if proposal.status == ProposalStatus.REJECTED.value:
            raise ProposalStateError(f"Proposal {proposal_id} was rejected")
        if proposal.world_id != world.world_id:
            raise ProposalStateError("Proposal belongs to a different world")
        if proposal.world_version != world.canon_version:
            raise StaleProposalError(
                f"Proposal targets v{proposal.world_version}, canon is v{world.canon_version}. "
                "Re-run exploration or explicitly rebase the proposal."
            )
        amended = {change.rule_id for change in proposal.rule_changes if change.action == "modify"}
        conflicts = self.architect.detect_conflicts(world, proposal.rules, amended_rule_ids=amended)
        proposal.potential_conflicts = conflicts
        direct = [item for item in conflicts if item.severity == "direct"]
        if direct and not accept_conflicts:
            self.store.upsert_proposal(proposal)
            raise ProposalConflictError(direct)

        snapshot_path = self.store.snapshot(world, f"pre-{proposal.id}")
        cases = self._ensure_regression_baseline(world)
        world_saved = False
        try:
            proposal.status = ProposalStatus.APPROVED.value
            applied_world = self.architect.apply_proposal(
                world, proposal, accept_conflicts=accept_conflicts
            )
            self.store.save_world(applied_world)
            world_saved = True
            regression_results = self._run_regressions(applied_world, cases)
            if any(not item.passed for item in regression_results):
                logger.error("Regression failure while applying %s; rolling back", proposal.id)
                restored = self.store.restore_snapshot(snapshot_path)
                proposal.status = ProposalStatus.REGRESSION_FAILED.value
                proposal.last_error = "Regression suite failed; canon was rolled back."
                proposal.updated_at = utc_now()
                proposal.decision.update(
                    {
                        "action": "rollback",
                        "reason": "regression_failure",
                        "at": proposal.updated_at,
                    }
                )
                self.store.upsert_proposal(proposal)
                return ApprovalResult(
                    proposal_id=proposal.id,
                    applied=False,
                    world_version=restored.canon_version,
                    message=(
                        "Regression suite failed. The world was rolled back and canon is "
                        f"unchanged. Restored version: {restored.canon_version}."
                    ),
                    conflicts=conflicts,
                    regression_results=regression_results,
                    rollback_performed=True,
                )

            post_tests = self._run_post_tests(applied_world, proposal)
            report_path = ""
            if write_report:
                try:
                    content = render_modification_report(
                        applied_world, proposal, regression_results, post_tests
                    )
                    report_path = str(
                        self.store.write_report(
                            f"rule-change-{proposal.id}-v{applied_world.canon_version}.md",
                            content,
                        )
                    )
                except OSError:
                    # A report failure must not invalidate an already gated canon change.
                    logger.exception("Could not write modification report for %s", proposal.id)
            self.store.upsert_proposal(proposal)
            logger.info("Approved %s; world v%s", proposal.id, applied_world.canon_version)
            return ApprovalResult(
                proposal_id=proposal.id,
                applied=True,
                world_version=applied_world.canon_version,
                message=(
                    f"Proposal applied. Canon is now v{applied_world.canon_version}; "
                    f"{len(proposal.rules)} rule(s) changed."
                ),
                conflicts=conflicts,
                regression_results=regression_results,
                post_tests=post_tests,
                report_path=report_path,
            )
        except Exception as exc:
            if world_saved:
                try:
                    self.store.restore_snapshot(snapshot_path)
                except Exception:  # pragma: no cover - recovery should not mask original error
                    logger.exception("Could not roll back snapshot after failure")
            proposal.status = ProposalStatus.PROPOSED.value
            proposal.last_error = str(exc)
            proposal.updated_at = utc_now()
            proposal.decision.update(
                {"action": "approval_failed", "reason": str(exc), "at": proposal.updated_at}
            )
            try:
                self.store.upsert_proposal(proposal)
            except Exception:  # pragma: no cover - best effort
                logger.exception("Could not persist failed proposal state")
            raise

    def reject(self, proposal_id: str, reason: str = "") -> Proposal:
        proposals = self.store.load_proposals()
        proposal = next((item for item in proposals if item.id == proposal_id), None)
        if proposal is None:
            raise ProposalStateError(f"Unknown proposal: {proposal_id}")
        if proposal.status == ProposalStatus.APPLIED.value:
            raise ProposalStateError("Cannot reject an applied proposal")
        self.architect.reject_proposal(proposal, reason)
        self.store.upsert_proposal(proposal)
        logger.info("Rejected %s: %s", proposal_id, reason or "no reason given")
        return proposal

    # --------------------------------------------------------------- regressions
    def _ensure_regression_baseline(self, world: World) -> list[RegressionCase]:
        cases, _ = self.store.load_regressions()
        if cases:
            return cases
        scenarios = list(world.regression_suite)
        if not scenarios:
            return []
        cases = []
        for scenario in scenarios:
            observation = self.explorer.observe(world, scenario)
            cases.append(
                RegressionCase(
                    scenario=scenario,
                    expected_fingerprint=observation.fingerprint,
                    expected_summary=observation.summary(),
                )
            )
        self.store.save_regressions(cases, world.canon_version)
        logger.info("Initialized %d regression cases at canon v%s", len(cases), world.canon_version)
        return cases

    def _run_regressions(self, world: World, cases: list[RegressionCase]) -> list[RegressionResult]:
        results: list[RegressionResult] = []
        for case in cases:
            observation = self.explorer.observe(world, case.scenario)
            passed = observation.fingerprint == case.expected_fingerprint
            results.append(
                RegressionResult(
                    case_id=case.scenario.id,
                    passed=passed,
                    expected_fingerprint=case.expected_fingerprint,
                    actual_fingerprint=observation.fingerprint,
                    expected_summary=case.expected_summary,
                    actual_summary=observation.summary(),
                    diff=(
                        ""
                        if passed
                        else f"expected: {case.expected_summary}; actual: {observation.summary()}"
                    ),
                )
            )
        return results

    def update_regression_baseline(self) -> list[RegressionCase]:
        """Re-baseline regressions after an *intentional* canon change."""

        world = self.store.load_world()
        cases, _ = self.store.load_regressions()
        scenarios = [case.scenario for case in cases] if cases else list(world.regression_suite)
        new_cases = []
        for scenario in scenarios:
            observation = self.explorer.observe(world, scenario)
            new_cases.append(
                RegressionCase(
                    scenario=scenario,
                    expected_fingerprint=observation.fingerprint,
                    expected_summary=observation.summary(),
                )
            )
        self.store.save_regressions(new_cases, world.canon_version)
        return new_cases

    def _run_post_tests(self, world: World, proposal: Proposal) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for scenario in proposal.test_plan:
            observation = self.explorer.observe(world, scenario)
            results.append(
                {
                    "scenario": scenario.to_dict(),
                    "observation": observation.to_dict(),
                }
            )
        return results

    # ------------------------------------------------------------------ rollback
    def rollback(self, snapshot: str | Path | None = None) -> World:
        return self.store.restore_snapshot(snapshot)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _run_id(focus: str) -> str:
        stamp = utc_now().replace("-", "").replace(":", "").replace("+00:00", "Z")
        safe_focus = "".join(ch if ch.isalnum() else "-" for ch in focus)
        return f"run-{stamp}-{safe_focus}"

    def proposals(self) -> list[Proposal]:
        return self.store.load_proposals()

    def pending_proposals(self) -> list[Proposal]:
        return [
            proposal
            for proposal in self.store.load_proposals()
            if proposal.status == ProposalStatus.PROPOSED.value
        ]
