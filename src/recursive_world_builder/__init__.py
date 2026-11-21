"""Recursive World Builder: self-play causal gap detection for fictional worlds."""
from .model import World, Entity, Location, Rule
from .storage import load_world, save_world, load_canon_notes
from .explorer import Scenario, generate_probes, counterfactuals
from .critic import Finding, analyse, find_contradictions
from .rules import Proposal, propose, apply, check_conflicts
from .controller import Controller, RunConfig, RunReport

__all__ = [
    "World", "Entity", "Location", "Rule",
    "load_world", "save_world", "load_canon_notes",
    "Scenario", "generate_probes", "counterfactuals",
    "Finding", "analyse", "find_contradictions",
    "Proposal", "propose", "apply", "check_conflicts",
    "Controller", "RunConfig", "RunReport",
]
__version__ = "0.1.0"
