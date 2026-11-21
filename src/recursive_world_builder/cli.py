"""Command line interface for Recursive World Builder.

The CLI is a thin, fully functional wrapper around the library.  It is not a
language-model client: natural-language requests are handled by the host agent,
which invokes these commands and supplies reasoning via ``--architect host`` or
``rwb propose``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .architect import ProposalConflictError, ProposalStateError, RuleArchitect, StaleProposalError
from .controller import RecursiveController
from .ingest import IngestError, init_world
from .model import ProposalStatus, RunLimits, ValidationError, World
from .reporting import (
    render_approval_result,
    render_proposals,
    render_world_summary,
)
from .storage import StorageError, WorldStore

logger = logging.getLogger(__name__)


def _store(path: str) -> WorldStore:
    return WorldStore(path)


def _load_world(path: str) -> World:
    store = _store(path)
    if not store.exists():
        raise StorageError(
            f"No world.json in {store.root}. Run 'rwb init {path}' or point at a world directory."
        )
    return store.load_world()


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).expanduser().resolve()
    store = WorldStore(target)
    if store.exists() and not args.force:
        world = store.load_world()
        print(f"World already initialized: {world.title} (canon v{world.canon_version})")
        print("Use --force to rebuild it from source material (destructive).")
        return 0
    if not target.exists():
        target.mkdir(parents=True)
    try:
        world = init_world(target, title=args.title, ignore_existing_world=args.force)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if store.exists() and not args.force:
        return 2
    store.create(world, overwrite=args.force)
    print(render_world_summary(world))
    print(f"\nInitialized structured world at {target}")
    if world.source_documents:
        print(f"Indexed {len(world.source_documents)} source document(s).")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    world = _load_world(args.directory)
    errors = world.validate()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"OK: {world.title} ({world.world_id}), canon v{world.canon_version}; "
        f"{len(world.entities)} entities, {len(world.rules)} rules."
    )
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    world = _load_world(args.directory)
    print(render_world_summary(world))
    return 0


def _cmd_explore(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    if not store.exists():
        print(f"error: no world at {store.root}", file=sys.stderr)
        return 2
    limits = RunLimits(
        max_rounds=args.rounds,
        max_scenarios=args.max_scenarios,
        max_new_rules=args.max_new_rules,
        max_proposals=args.max_proposals,
        max_consecutive_empty_rounds=args.max_empty_rounds,
    )
    controller = RecursiveController(store, limits=limits, architect_mode=args.architect)
    result = controller.explore(focus=args.focus)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(
            f"Run {result.run_id}: {len(result.findings)} finding(s), "
            f"{len(result.proposals)} proposal(s), stop={result.stop_reason}."
        )
        for proposal in result.proposals:
            print(f"  [{proposal.id}] {proposal.title} ({len(proposal.rules)} rules)")
        print(f"Reports written under {store.reports_dir} and {store.run_dir}")
    return 0


def _cmd_proposals(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    proposals = store.load_proposals()
    if args.status:
        proposals = [item for item in proposals if item.status == args.status]
    if args.json:
        print(
            json.dumps([proposal.to_dict() for proposal in proposals], indent=2, ensure_ascii=False)
        )
    else:
        print(render_proposals(proposals))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    proposal = store.find_proposal(args.proposal_id)
    print(json.dumps(proposal.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    controller = RecursiveController(store)
    proposal = store.find_proposal(args.proposal_id)
    if proposal.status == ProposalStatus.APPLIED.value:
        print(f"Proposal {proposal.id} is already applied.")
        return 0
    direct = [item for item in proposal.potential_conflicts if item.severity == "direct"]
    if direct and not args.accept_conflicts:
        print("Direct conflicts prevent approval:", file=sys.stderr)
        for conflict in direct:
            print(f"  {conflict.id}: {conflict.description}", file=sys.stderr)
        print("Resolve them, or pass --accept-conflicts explicitly.", file=sys.stderr)
        return 1
    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "Refusing to approve without confirmation. Re-run with --yes for automation.",
                file=sys.stderr,
            )
            return 2
        answer = input(f"Approve {proposal.id} '{proposal.title}' and modify canon? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Not approved.")
            return 0
    try:
        result = controller.approve(proposal.id, accept_conflicts=args.accept_conflicts)
    except (ProposalConflictError, ProposalStateError, StaleProposalError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_approval_result(result))
    return 0 if result.applied else 1


def _cmd_reject(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    controller = RecursiveController(store)
    if not args.yes:
        if not sys.stdin.isatty():
            print("Refusing to reject without confirmation. Re-run with --yes.", file=sys.stderr)
            return 2
        answer = input(f"Reject {args.proposal_id}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Not rejected.")
            return 0
    proposal = controller.reject(args.proposal_id, args.reason)
    print(f"Rejected {proposal.id}; canon unchanged.")
    return 0


def _cmd_propose(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    world = store.load_world()
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    proposals = store.load_proposals()
    architect = RuleArchitect()
    proposal = architect.ingest_external_proposal(
        world,
        payload,
        proposal_id=store.next_proposal_id(proposals),
        existing_proposals=proposals,
    )
    store.upsert_proposal(proposal)
    print(f"Added proposal {proposal.id}: {proposal.title}")
    print(
        f"Rules: {', '.join(rule.id for rule in proposal.rules)}; "
        f"conflicts: {len(proposal.potential_conflicts)}; tests: {len(proposal.test_plan)}"
    )
    print(f"Review with: rwb show {args.directory} {proposal.id}")
    return 0


def _cmd_regressions(args: argparse.Namespace) -> int:
    store = _store(args.directory)
    controller = RecursiveController(store)
    if args.update:
        cases = controller.update_regression_baseline()
        print(f"Updated {len(cases)} regression baseline case(s).")
        return 0
    cases, version = store.load_regressions()
    print(f"Regression cases: {len(cases)} (baseline world v{version})")
    for case in cases:
        print(f"  {case.scenario.id}: {case.expected_summary}")
    return 0


def _cmd_rollback(args: argparse.Namespace) -> int:
    if not args.yes:
        if not sys.stdin.isatty():
            print("Refusing to roll back without confirmation. Re-run with --yes.", file=sys.stderr)
            return 2
        answer = input("Restore canon from a snapshot? This overwrites current world.json. [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Not rolled back.")
            return 0
    controller = RecursiveController(_store(args.directory))
    world = controller.rollback(args.snapshot)
    print(f"Restored world {world.world_id} at canon v{world.canon_version}.")
    return 0


def _cmd_sources(args: argparse.Namespace) -> int:
    world = _load_world(args.directory)
    if not world.source_documents:
        print("No source documents indexed.")
        return 0
    for source in world.source_documents:
        print(
            f"{source.get('path')}: {source.get('title')} (sha256 {source.get('sha256', '')[:12]})"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rwb",
        description=(
            "Self-play exploration and recursive rule expansion for fictional worlds. "
            "The deterministic engine records state; the host agent supplies reasoning."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize a world from Markdown/JSON/YAML")
    init.add_argument("directory")
    init.add_argument("--title")
    init.add_argument("--force", action="store_true", help="overwrite an existing world")
    init.set_defaults(func=_cmd_init)

    validate = sub.add_parser("validate", help="validate world.json")
    validate.add_argument("directory")
    validate.set_defaults(func=_cmd_validate)

    summary = sub.add_parser("summary", help="print world and canon summary")
    summary.add_argument("directory")
    summary.set_defaults(func=_cmd_summary)

    explore = sub.add_parser("explore", help="run a bounded exploration loop")
    explore.add_argument("directory")
    explore.add_argument("--rounds", type=int, default=5)
    explore.add_argument(
        "--focus",
        default="all",
        choices=["all", "physics", "biology", "society", "economy", "character"],
    )
    explore.add_argument("--max-scenarios", type=int, default=24)
    explore.add_argument("--max-new-rules", type=int, default=8)
    explore.add_argument("--max-proposals", type=int, default=10)
    explore.add_argument("--max-empty-rounds", type=int, default=2)
    explore.add_argument("--architect", choices=["scripted", "host"], default="scripted")
    explore.add_argument("--json", action="store_true")
    explore.set_defaults(func=_cmd_explore)

    proposals = sub.add_parser("proposals", help="list proposals")
    proposals.add_argument("directory")
    proposals.add_argument("--status", choices=[item.value for item in ProposalStatus])
    proposals.add_argument("--json", action="store_true")
    proposals.set_defaults(func=_cmd_proposals)

    show = sub.add_parser("show", help="show a proposal as JSON")
    show.add_argument("directory")
    show.add_argument("proposal_id")
    show.set_defaults(func=_cmd_show)

    approve = sub.add_parser("approve", help="explicitly approve and apply a proposal")
    approve.add_argument("directory")
    approve.add_argument("proposal_id")
    approve.add_argument("--yes", action="store_true")
    approve.add_argument("--accept-conflicts", action="store_true")
    approve.set_defaults(func=_cmd_approve)

    reject = sub.add_parser("reject", help="reject a proposal without touching canon")
    reject.add_argument("directory")
    reject.add_argument("proposal_id")
    reject.add_argument("--reason", default="")
    reject.add_argument("--yes", action="store_true")
    reject.set_defaults(func=_cmd_reject)

    propose = sub.add_parser("propose", help="ingest a host-agent-authored proposal JSON")
    propose.add_argument("directory")
    propose.add_argument("--file", required=True)
    propose.set_defaults(func=_cmd_propose)

    regressions = sub.add_parser("regressions", help="inspect or update regression baselines")
    regressions.add_argument("directory")
    regressions.add_argument("--update", action="store_true")
    regressions.set_defaults(func=_cmd_regressions)

    rollback = sub.add_parser("rollback", help="restore the latest or a named snapshot")
    rollback.add_argument("directory")
    rollback.add_argument("--snapshot")
    rollback.add_argument("--yes", action="store_true")
    rollback.set_defaults(func=_cmd_rollback)

    sources = sub.add_parser("sources", help="list indexed source documents")
    sources.add_argument("directory")
    sources.set_defaults(func=_cmd_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return int(args.func(args))
    except (
        StorageError,
        IngestError,
        ValidationError,
        ProposalStateError,
        StaleProposalError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ProposalConflictError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for conflict in exc.conflicts:
            print(f"  {conflict.id}: {conflict.description}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
