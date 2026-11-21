"""Recursive controller: bounded loop, dedupe, approval, rollback."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .model import World
from .explorer import generate_probes, counterfactuals
from .critic import analyse, find_contradictions
from .rules import propose, apply, Proposal


@dataclass
class RunConfig:
    rounds: int = 3
    max_scenarios: int = 40
    max_proposals: int = 5
    auto_approve: bool = False


@dataclass
class RunReport:
    rounds_run: int = 0
    scenarios: int = 0
    findings: list = field(default_factory=list)
    proposals: list = field(default_factory=list)
    applied: list = field(default_factory=list)
    stopped_because: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Controller:
    def __init__(self, world: World, config: RunConfig | None = None):
        self.world = world
        self.config = config or RunConfig()
        self.findings: list = []
        self.proposals: list[Proposal] = []
        self.applied: list[str] = []
        self._seen: set[str] = set()
        self._snapshot: dict = {}

    # -- lifecycle -------------------------------------------------------
    def snapshot(self) -> None:
        self._snapshot = self.world.to_dict()

    def rollback(self) -> None:
        if self._snapshot:
            restored = World.from_dict(self._snapshot)
            self.world.__dict__.update(restored.__dict__)

    # -- loop ------------------------------------------------------------
    def run(self, probes=None) -> RunReport:
        cfg = self.config
        report = RunReport()
        self.snapshot()
        scenarios = probes if probes is not None else generate_probes(self.world, cfg.max_scenarios)

        for rnd in range(cfg.rounds):
            report.rounds_run = rnd + 1
            produced = 0
            for sc in scenarios:
                if report.scenarios >= cfg.max_scenarios:
                    report.stopped_because = "max_scenarios"
                    break
                report.scenarios += 1

                for f in find_contradictions(self.world, sc):
                    key = (f.scenario, f.gap_type)
                    if key in self._seen:
                        continue
                    self._seen.add(key)
                    self.findings.append(f)
                    report.findings.append(f.to_dict())

                f = analyse(self.world, sc)
                if f is None:
                    continue
                key = (f.scenario, f.gap_type)
                if key in self._seen:
                    continue
                self._seen.add(key)
                self.findings.append(f)
                report.findings.append(f.to_dict())

                if len(self.proposals) >= cfg.max_proposals:
                    continue
                p = propose(self.world, f)
                self.proposals.append(p)
                report.proposals.append(p.to_dict())
                produced += 1

            if report.stopped_because:
                break
            if produced == 0:
                report.stopped_because = "no_new_findings"
                break
        else:
            report.stopped_because = "max_rounds"

        if cfg.auto_approve:
            for p in self.proposals:
                self.approve(p.id)
        return report

    # -- human in the loop -------------------------------------------------
    def approve(self, proposal_id: str) -> None:
        p = self.get(proposal_id)
        p.status = "APPROVED"
        apply(self.world, p)
        self.applied.append(p.id)

    def reject(self, proposal_id: str) -> None:
        p = self.get(proposal_id)
        p.status = "REJECTED"

    def get(self, proposal_id: str) -> Proposal:
        for p in self.proposals:
            if p.id == proposal_id:
                return p
        raise KeyError(proposal_id)

    def follow_ups(self, proposal_id: str):
        p = self.get(proposal_id)
        return counterfactuals(self.world, p.proposed_rule["scope"])
