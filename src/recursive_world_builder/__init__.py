"""Recursive World Builder.

A lightweight Agent Skill runtime for self-play exploration, causal-gap
detection, and explicit, approval-gated world-rule expansion.

The Python package is deterministic state management.  The host agent performs
creative reasoning and supplies proposals; the package never treats an LLM
completion as a physical simulation or a formal proof.
"""

from __future__ import annotations

from .architect import (
    ProposalConflictError,
    ProposalStateError,
    RuleArchitect,
    StaleProposalError,
)
from .controller import RecursiveController
from .critic import CausalCritic
from .engine import RuleEngine
from .explorer import Explorer, ScenarioGenerator
from .ingest import ingest_directory, init_world
from .model import (
    ApprovalResult,
    Conflict,
    Constraint,
    Domain,
    Entity,
    GapFinding,
    GapType,
    Location,
    Observation,
    Proposal,
    ProposalStatus,
    Recommendation,
    RegressionCase,
    RegressionResult,
    Relationship,
    Rule,
    RuleChange,
    RuleMatcher,
    RuleStatus,
    RunLimits,
    RunResult,
    Scenario,
    ValidationError,
    World,
)
from .storage import StorageError, WorldStore

__version__ = "0.1.0"

__all__ = [
    "ApprovalResult",
    "CausalCritic",
    "Conflict",
    "Constraint",
    "Domain",
    "Entity",
    "Explorer",
    "GapFinding",
    "GapType",
    "Location",
    "Observation",
    "Proposal",
    "ProposalConflictError",
    "ProposalStateError",
    "ProposalStatus",
    "Recommendation",
    "RecursiveController",
    "RegressionCase",
    "RegressionResult",
    "Relationship",
    "Rule",
    "RuleArchitect",
    "RuleChange",
    "RuleEngine",
    "RuleMatcher",
    "RuleStatus",
    "RunLimits",
    "RunResult",
    "Scenario",
    "ScenarioGenerator",
    "StaleProposalError",
    "StorageError",
    "ValidationError",
    "World",
    "WorldStore",
    "__version__",
    "ingest_directory",
    "init_world",
]
