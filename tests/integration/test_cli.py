from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from recursive_world_builder.cli import main
from recursive_world_builder.storage import WorldStore

from ..conftest import PROJECT_ROOT


def test_cli_validate(electric_store: WorldStore) -> None:
    assert main(["validate", str(electric_store.root)]) == 0


def test_cli_init_from_markdown(markdown_source) -> None:
    target = markdown_source.parent / "new_world"
    shutil.copytree(markdown_source, target)
    assert main(["init", str(target)]) == 0
    store = WorldStore(target)
    world = store.load_world()
    assert world.entities["tala"].name == "Tala the Mason"
    assert "r_lift_stone" in world.rules
    assert world.source_documents[0]["path"] == "notes.md"


def test_module_entrypoint_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "recursive_world_builder", "--version"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "rwb 0.1.0" in result.stdout


def test_cli_explore_and_approve(electric_store: WorldStore) -> None:
    assert (
        main(
            [
                "explore",
                str(electric_store.root),
                "--rounds",
                "1",
                "--max-scenarios",
                "4",
                "--max-proposals",
                "1",
            ]
        )
        == 0
    )
    proposal = electric_store.load_proposals()[0]
    assert main(["approve", str(electric_store.root), proposal.id, "--yes"]) == 0
    world = electric_store.load_world()
    assert world.canon_version == 2
    assert electric_store.find_proposal(proposal.id).status == "applied"


def test_cli_propose_host_proposal(electric_store: WorldStore, tmp_path) -> None:
    payload = {
        "title": "A tiny host proposal",
        "problem": "Waving has no recorded event.",
        "root_cause_hypothesis": "No social gesture rule.",
        "rationale": "Add one general gesture event.",
        "expected_impacts": ["waving becomes observable"],
        "generality": {"scope": "any human", "special_case": False, "reusable": True},
        "test_plan": [
            {
                "id": "T-WAVE",
                "title": "Mira waves",
                "actor": "mira",
                "action": {"type": "wave"},
            }
        ],
        "rules": [
            {
                "id": "r_wave",
                "name": "Waving is visible",
                "description": "A human who waves emits an event.",
                "domain": "character",
                "matcher": {"action_types": ["wave"], "actor_tags_any": ["human"]},
                "effects": [{"kind": "emit_event", "target": "actor", "event": "waved"}],
                "status": "proposed",
            }
        ],
    }
    proposal_file = tmp_path / "proposal.json"
    proposal_file.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["propose", str(electric_store.root), "--file", str(proposal_file)]) == 0
    proposals = electric_store.load_proposals()
    assert len(proposals) == 1
    assert proposals[0].id == "P-0001"
    assert proposals[0].rules[0].id == "r_wave"
    assert proposals[0].rule_changes[0].action == "add"
