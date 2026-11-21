import json
from pathlib import Path

import pytest

from recursive_world_builder import (
    World, Rule, load_world, save_world,
    Controller, RunConfig, propose, analyse, check_conflicts,
)
from recursive_world_builder.explorer import Scenario, generate_probes

ROOT = Path(__file__).resolve().parents[1] / "examples" / "electric_city"


def touch_line():
    return Scenario(id="t", verb="touch", subjects=["person_1"], objects=["line_1"])


def test_load_valid_world():
    w = load_world(ROOT)
    assert w.name == "Electric City"
    assert "person_1" in w.entities
    assert w.validate() == []


def test_detects_undefined_interaction():
    w = load_world(ROOT)
    f = analyse(w, touch_line())
    assert f is not None
    assert f.gap_type == "undefined_interaction"
    assert "electricity" in f.affected_systems


def test_proposal_is_structured():
    w = load_world(ROOT)
    f = analyse(w, touch_line())
    p = propose(w, f)
    assert p.status == "PROPOSED"
    assert p.proposed_rule["verb"] == "touch"
    assert p.proposed_rule["scope"]
    assert p.tests and p.rationale


def test_detects_direct_conflict():
    w = load_world(ROOT)
    w.add_rule(Rule(id="R-a", scope=["electric", "human"], verb="touch",
                    effect={"harm": "lethal"}, status="CANON"))
    candidate = Rule(id="R-b", scope=["electric", "human"], verb="touch",
                     effect={"harm": "none"}, status="PROPOSED")
    conflicts = check_conflicts(w, candidate)
    assert conflicts and "R-a" in conflicts[0]


def test_reject_leaves_canon_unchanged():
    w = load_world(ROOT)
    before = set(w.rules)
    ctl = Controller(w, RunConfig(rounds=1, max_scenarios=10))
    rep = ctl.run(probes=[touch_line()])
    assert rep.proposals
    ctl.reject(rep.proposals[0]["id"])
    assert set(w.rules) == before


def test_approve_updates_canon():
    w = load_world(ROOT)
    before = set(w.rules)
    ctl = Controller(w, RunConfig(rounds=1, max_scenarios=10))
    rep = ctl.run(probes=[touch_line()])
    pid = rep.proposals[0]["id"]
    ctl.approve(pid)
    assert len(w.rules) == len(before) + 1
    assert any(r.source == pid for r in w.rules.values())


def test_recursion_stops():
    w = load_world(ROOT)
    ctl = Controller(w, RunConfig(rounds=5, max_scenarios=6, max_proposals=2))
    rep = ctl.run(probes=generate_probes(w, 20))
    assert rep.stopped_because in {"max_scenarios", "no_new_findings", "max_rounds"}
    assert rep.rounds_run <= 5


def test_rollback_restores_rules():
    w = load_world(ROOT)
    before = set(w.rules)
    ctl = Controller(w, RunConfig(rounds=1, max_scenarios=5, auto_approve=False))
    ctl.snapshot()
    ctl.run(probes=[touch_line()])
    ctl.approve(ctl.proposals[0].id)
    assert set(w.rules) != before
    ctl.rollback()
    assert set(w.rules) == before


def test_save_roundtrip(tmp_path):
    w = load_world(ROOT)
    save_world(w, tmp_path)
    again = load_world(tmp_path)
    assert again.to_dict() == w.to_dict()
