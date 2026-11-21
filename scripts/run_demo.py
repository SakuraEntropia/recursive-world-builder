#!/usr/bin/env python3
"""Reproducible offline demo for Recursive World Builder.

The committed example world is never modified.  This script copies it into
``demo-output/`` and runs:

    load -> explore -> finding -> proposal -> explicit approval
         -> regression gate -> counterfactual re-tests -> report

It uses the deterministic scripted architect, so no external LLM API is needed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recursive_world_builder.controller import RecursiveController  # noqa: E402
from recursive_world_builder.storage import WorldStore  # noqa: E402


def _safe_target() -> Path:
    return REPO_ROOT / "demo-output" / "electric_city"


def _print_finding(index: int, finding) -> None:
    print(f"\n  Finding {index}: {finding.gap_type}")
    print(f"    scenario:   {finding.scenario}")
    print(f"    observation:{finding.observation}")
    print(f"    hypothesis: {finding.hypothesis}")
    print(f"    systems:    {', '.join(finding.affected_systems)}")
    print(f"    confidence: {finding.confidence:.2f} (subjective; calibrated={finding.calibrated})")


def _print_proposal(proposal) -> None:
    print(f"\n  Proposal {proposal.id}: {proposal.title}")
    print(f"    problem:   {proposal.problem}")
    print(f"    root cause:{proposal.root_cause_hypothesis}")
    print(f"    rules:     {', '.join(rule.id for rule in proposal.rules)}")
    print(f"    conflicts: {len(proposal.potential_conflicts)}")
    print(f"    tests:     {', '.join(item.id for item in proposal.test_plan)}")
    print("    expected impacts:")
    for impact in proposal.expected_impacts:
        print(f"      - {impact}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approve",
        action="store_true",
        help="execute the explicit approval step without an interactive prompt (for CI/demo)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep an existing demo-output/electric_city instead of replacing it",
    )
    args = parser.parse_args()

    source = REPO_ROOT / "examples" / "electric_city"
    target = _safe_target()
    if target.exists() and not args.keep:
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copytree(source, target)
    # Never reuse runtime state from an earlier demo copy.
    for generated in (target / ".rwb", target / "reports"):
        if generated.exists():
            shutil.rmtree(generated)
    for generated_file in (target / "proposals.json", target / "regressions.json"):
        if generated_file.exists():
            generated_file.unlink()

    store = WorldStore(target)
    world = store.load_world()
    print("=" * 78)
    print("Recursive World Builder — offline electric_city demo")
    print("=" * 78)
    print(f"World: {world.title} ({world.world_id}), canon v{world.canon_version}")
    print(f"Entities: {len(world.entities)}, rules: {len(world.rules)}")
    print(f"Working copy: {target}")

    controller = RecursiveController(store, architect_mode="scripted")
    print("\n[1] Bounded exploration (focus=physics, max_proposals=1)")
    result = controller.explore(
        focus="physics",
        max_rounds=2,
        max_scenarios=8,
        max_proposals=1,
    )
    print(
        f"    ran {result.scenarios_run} scenarios; {len(result.findings)} findings; "
        f"{len(result.proposals)} proposal; stop={result.stop_reason}"
    )
    for index, finding in enumerate(result.findings, start=1):
        _print_finding(index, finding)
    if not result.proposals:
        print("\nNo proposal was generated; demo cannot continue.", file=sys.stderr)
        return 1
    proposal = result.proposals[0]
    _print_proposal(proposal)

    print("\n[2] Canon before approval")
    print(f"    canon_version={world.canon_version}; rules={len(world.rules)}")
    print("    (No proposal content is in canon yet.)")

    if not args.approve:
        if not sys.stdin.isatty():
            print(
                "\nRefusing to approve without confirmation. Re-run with --approve for automation.",
                file=sys.stderr,
            )
            return 2
        answer = input(f"\nApprove {proposal.id} and apply it to the demo copy? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Not approved. Canon remains unchanged.")
            return 0
    else:
        print("\n[3] Approval")
        print("    DEMO: --approve was passed, so the script performs the explicit approval")
        print("    step that a human would otherwise perform. The library API still requires")
        print("    a separate approve() call; exploration never applies proposals itself.")

    print("\n[4] Applying proposal and running the regression gate")
    approval = controller.approve(proposal.id)
    print(f"    applied={approval.applied}; world v{approval.world_version}")
    print(f"    {approval.message}")
    for regression in approval.regression_results:
        print(
            f"    regression {regression.case_id}: "
            f"{'PASS' if regression.passed else 'FAIL'} ({regression.actual_summary})"
        )
    if not approval.applied:
        print("Demo failed: proposal was not applied.", file=sys.stderr)
        return 1

    print("\n[5] Counterfactual re-tests")
    for item in approval.post_tests:
        scenario = item["scenario"]
        observation = item["observation"]
        print(f"    {scenario['id']}: {scenario['title']}")
        print(f"      -> {observation['summary']}")

    print("\n[6] Result")
    final = store.load_world()
    print(f"    canon v{final.canon_version}; rules: {len(world.rules)} -> {len(final.rules)}")
    print(f"    report: {approval.report_path}")
    print(f"    run report: {(store.run_dir / 'latest.json')}")
    print("\nDone. Source example remains at canon v1; only the working copy changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
