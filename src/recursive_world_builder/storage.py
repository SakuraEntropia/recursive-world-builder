"""Persistence, snapshots, and proposal storage.

Runtime state lives under ``.rwb/`` and is intentionally excluded from version
control.  Canon is a plain JSON file so it is reviewable in a diff.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .model import (
    Proposal,
    ProposalStatus,
    RegressionCase,
    RunResult,
    ValidationError,
    World,
    utc_now,
)

logger = logging.getLogger(__name__)

WORLD_FILE = "world.json"
YAML_WORLD_FILES = ("world.yaml", "world.yml")
PROPOSALS_FILE = "proposals.json"
REGRESSIONS_FILE = "regressions.json"
STATE_DIR = ".rwb"
REPORTS_DIR = "reports"


class StorageError(RuntimeError):
    """Raised for filesystem or serialization failures."""


def _import_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise StorageError(
            "YAML support is optional. Install it with: pip install 'recursive-world-builder[yaml]'"
        ) from exc
    return yaml


def read_structured_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageError(f"Cannot read {path}: {exc}") from exc
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            return json.loads(text)
        if suffix in {".yaml", ".yml"}:
            yaml = _import_yaml()
            return yaml.safe_load(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise StorageError(f"Cannot parse {path}: {exc}") from exc
    raise StorageError(f"Unsupported structured file type: {path.suffix} ({path})")


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


class WorldStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.state_dir = self.root / STATE_DIR
        self.snapshot_dir = self.state_dir / "snapshots"
        self.run_dir = self.state_dir / "runs"
        self.reports_dir = self.root / REPORTS_DIR

    # ------------------------------------------------------------------ paths
    @property
    def canonical_world_path(self) -> Path:
        return self.root / WORLD_FILE

    @property
    def world_path(self) -> Path:
        if self.canonical_world_path.exists():
            return self.canonical_world_path
        for name in YAML_WORLD_FILES:
            candidate = self.root / name
            if candidate.exists():
                return candidate
        return self.canonical_world_path

    @property
    def proposals_path(self) -> Path:
        return self.root / PROPOSALS_FILE

    @property
    def regressions_path(self) -> Path:
        return self.root / REGRESSIONS_FILE

    def exists(self) -> bool:
        return self.world_path.exists()

    # ------------------------------------------------------------------ world
    def load_world(self) -> World:
        if not self.world_path.exists():
            raise StorageError(
                f"No world found at {self.root} (looked for world.json, world.yaml, world.yml)"
            )
        data = read_structured_file(self.world_path)
        try:
            return World.from_dict(data)
        except ValidationError as exc:
            raise StorageError(f"Invalid world: {exc}") from exc

    def save_world(self, world: World, *, touch: bool = True) -> None:
        world.assert_valid()
        if touch:
            world.updated_at = utc_now()
        write_json_atomic(self.canonical_world_path, world.to_dict())
        logger.info("Saved world %s v%s", world.world_id, world.canon_version)

    def create(self, world: World, *, overwrite: bool = False) -> None:
        if self.world_path.exists() and not overwrite:
            raise StorageError(f"World already exists at {self.world_path}")
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        world.created_at = world.created_at or utc_now()
        world.updated_at = utc_now()
        self.save_world(world)
        if overwrite or not self.proposals_path.exists():
            write_json_atomic(self.proposals_path, {"version": 1, "proposals": []})
        if overwrite and self.regressions_path.exists():
            self.regressions_path.unlink()
        logger.info("Initialized world at %s", self.root)

    # -------------------------------------------------------------- proposals
    def load_proposals(self) -> list[Proposal]:
        if not self.proposals_path.exists():
            return []
        try:
            payload = read_structured_file(self.proposals_path)
        except StorageError:
            raise
        raw = payload.get("proposals", []) if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise StorageError("proposals.json must contain a list under 'proposals'")
        return [Proposal.from_dict(item) for item in raw]

    def save_proposals(self, proposals: list[Proposal]) -> None:
        payload = {
            "version": 1,
            "updated_at": utc_now(),
            "proposals": [proposal.to_dict() for proposal in proposals],
        }
        write_json_atomic(self.proposals_path, payload)

    def next_proposal_id(self, proposals: list[Proposal] | None = None) -> str:
        proposals = proposals if proposals is not None else self.load_proposals()
        numbers = []
        for proposal in proposals:
            prefix, _, suffix = proposal.id.partition("-")
            if prefix == "P" and suffix.isdigit():
                numbers.append(int(suffix))
        return f"P-{max(numbers, default=0) + 1:04d}"

    def find_proposal(self, proposal_id: str) -> Proposal:
        for proposal in self.load_proposals():
            if proposal.id == proposal_id:
                return proposal
        raise StorageError(f"Unknown proposal: {proposal_id}")

    def upsert_proposal(self, proposal: Proposal) -> None:
        proposals = self.load_proposals()
        for index, current in enumerate(proposals):
            if current.id == proposal.id:
                proposals[index] = proposal
                break
        else:
            proposals.append(proposal)
        self.save_proposals(proposals)

    # ------------------------------------------------------------ regressions
    def load_regressions(self) -> tuple[list[RegressionCase], int]:
        if not self.regressions_path.exists():
            return [], 0
        payload = read_structured_file(self.regressions_path)
        if not isinstance(payload, dict):
            raise StorageError("regressions.json must be an object")
        cases = [RegressionCase.from_dict(item) for item in payload.get("cases", [])]
        return cases, int(payload.get("baseline_world_version", 0))

    def save_regressions(self, cases: list[RegressionCase], world_version: int) -> None:
        payload = {
            "version": 1,
            "baseline_world_version": world_version,
            "updated_at": utc_now(),
            "cases": [case.to_dict() for case in cases],
        }
        write_json_atomic(self.regressions_path, payload)

    # ---------------------------------------------------------------- runs
    def save_run(self, result: RunResult) -> Path:
        payload = result.to_dict()
        run_id = result.run_id
        path = self.run_dir / f"{run_id}.json"
        write_json_atomic(path, payload)
        latest_path = self.run_dir / "latest.json"
        write_json_atomic(latest_path, {"run_id": run_id, "file": path.name})
        return path

    def latest_run(self) -> dict[str, Any] | None:
        latest_path = self.run_dir / "latest.json"
        if not latest_path.exists():
            return None
        pointer = read_structured_file(latest_path)
        target = self.run_dir / str(pointer.get("file", ""))
        if not target.exists():
            return None
        return read_structured_file(target)

    # ------------------------------------------------------------- snapshots
    def snapshot(self, world: World, label: str = "pre-apply") -> Path:
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)[:40]
        filename = f"v{world.canon_version}-{safe_label}-{utc_now().replace(':', '')}.json"
        path = self.snapshot_dir / filename
        payload = {
            "label": label,
            "created_at": utc_now(),
            "world": world.to_dict(),
        }
        write_json_atomic(path, payload)
        write_json_atomic(self.snapshot_dir / "latest.json", {"file": filename})
        return path

    def list_snapshots(self) -> list[Path]:
        if not self.snapshot_dir.exists():
            return []
        return sorted(
            (path for path in self.snapshot_dir.glob("*.json") if path.name != "latest.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    def restore_snapshot(self, path: str | Path | None = None) -> World:
        target: Path
        if path is None:
            snapshots = self.list_snapshots()
            if not snapshots:
                raise StorageError("No snapshots are available")
            target = snapshots[0]
        else:
            target = Path(path)
            if not target.is_absolute():
                target = self.snapshot_dir / target
        if not target.exists():
            raise StorageError(f"Snapshot not found: {target}")
        payload = read_structured_file(target)
        raw_world = payload.get("world") if isinstance(payload, dict) else None
        if not isinstance(raw_world, dict):
            raise StorageError(f"Snapshot is malformed: {target}")
        world = World.from_dict(raw_world)
        self.save_world(world)
        logger.info("Restored snapshot %s", target)
        return world

    # ---------------------------------------------------------------- reports
    def write_report(self, filename: str, content: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / filename
        path.write_text(content, encoding="utf-8")
        return path


def mark_proposal_status(proposal: Proposal, status: ProposalStatus, **decision: Any) -> None:
    proposal.status = status.value
    proposal.updated_at = utc_now()
    proposal.decision.update(decision)
    proposal.decision["at"] = proposal.updated_at
