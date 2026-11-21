"""Markdown / JSON / YAML ingestion.

Unstructured prose is never silently converted into rules.  The deterministic
ingester understands a small documented Markdown shape, embeds arbitrary world
fragments in fenced JSON/YAML, and preserves every source document (path,
digest, outline, excerpt) so the host agent can consult the original prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .model import (
    SCHEMA_VERSION,
    ValidationError,
    World,
    utc_now,
)
from .storage import StorageError, read_structured_file

FENCE_RE = re.compile(r"```(json|yaml|yml)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")
KEY_VALUE_RE = re.compile(r"^([A-Za-z_][\w.-]*)\s*:\s*(.+)$")

ENTITY_SECTIONS = {"entities", "characters", "objects", "creatures", "factions"}
LOCATION_SECTIONS = {"locations", "places", "sites"}
RELATIONSHIP_SECTIONS = {"relationships", "relations"}
COLLECTION_KEYS = {
    "entities",
    "locations",
    "rules",
    "relationships",
    "constraints",
    "canon",
    "regression_suite",
}
IGNORED_FILES = {
    "proposals.json",
    "regressions.json",
    "exploration_cases.json",
    "package.json",
}
IGNORED_DIRS = {".git", ".rwb", "__pycache__", ".pytest_cache", "node_modules", "reports"}


class IngestError(StorageError):
    """Raised when source material cannot be converted safely."""


def slugify(value: str) -> str:
    text = re.sub(r"[^\w\s-]", "", value.strip().lower(), flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "item"


def _scalar(value: str) -> Any:
    text = value.strip()
    lowered = text.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text.strip("\"'")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _properties(value: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for chunk in _split_csv(value):
        if "=" in chunk:
            key, raw = chunk.split("=", 1)
            result[key.strip()] = _scalar(raw)
        elif ":" in chunk:
            key, raw = chunk.split(":", 1)
            result[key.strip()] = _scalar(raw)
    return result


def _heading_identity(raw: str) -> tuple[str, str]:
    text = raw.strip()
    for separator in (" — ", " – ", " - ", ": "):
        if separator in text:
            left, right = text.split(separator, 1)
            identifier = slugify(left)
            return identifier, right.strip() or left.strip()
    identifier = slugify(text)
    return identifier, text


def _outline(text: str) -> list[str]:
    return [
        match.group(2).strip()
        for match in (HEADING_RE.match(line) for line in text.splitlines())
        if match
    ]


def _fenced_fragments(text: str, path: Path) -> list[dict[str, Any]]:
    fragments: list[dict[str, Any]] = []
    for language, body in FENCE_RE.findall(text):
        language = language.lower()
        try:
            if language == "json":
                payload = json.loads(body)
            else:
                try:
                    import yaml  # type: ignore
                except ImportError as exc:  # pragma: no cover - optional
                    raise IngestError(
                        f"{path}: YAML fence requires PyYAML; install the yaml extra"
                    ) from exc
                payload = yaml.safe_load(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise IngestError(f"{path}: invalid {language} fence: {exc}") from exc
        if isinstance(payload, dict) and (
            COLLECTION_KEYS & set(payload) or "world_id" in payload or "entities" in payload
        ):
            fragments.append(payload)
    return fragments


def _parse_markdown_body(text: str, path: Path) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    locations: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    canon: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []

    current_section = ""
    current: dict[str, Any] | None = None
    current_kind = ""
    canon_index = 0
    constraint_index = 0

    for raw_line in text.splitlines():
        heading = HEADING_RE.match(raw_line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 2:
                current_section = title.lower().strip()
                current = None
                current_kind = ""
                continue
            if level == 3 and current_section in (
                ENTITY_SECTIONS | LOCATION_SECTIONS | RELATIONSHIP_SECTIONS
            ):
                identifier, name = _heading_identity(title)
                if current_section in ENTITY_SECTIONS:
                    current = {
                        "id": identifier,
                        "name": name,
                        "type": "character" if current_section == "characters" else "object",
                    }
                    entities[identifier] = current
                    current_kind = "entity"
                elif current_section in LOCATION_SECTIONS:
                    current = {"id": identifier, "name": name}
                    locations[identifier] = current
                    current_kind = "location"
                else:
                    current = {"id": identifier, "source_id": "", "target_id": "", "kind": name}
                    relationships[identifier] = current
                    current_kind = "relationship"
                continue
            current = None
            current_kind = ""
            continue

        bullet = BULLET_RE.match(raw_line)
        if not bullet:
            continue
        content = bullet.group(1).strip()
        if current_section in {"canon", "canon facts", "established canon"}:
            canon_index += 1
            canon.append({"id": f"CF-{canon_index:03d}", "statement": content, "source": path.name})
            continue
        if current_section in {"constraints", "world constraints"}:
            constraint_index += 1
            constraints.append(
                {
                    "id": f"C-SRC-{constraint_index:03d}",
                    "description": content,
                    "kind": "axiom",
                    "severity": "hard",
                    "source": path.name,
                }
            )
            continue
        if not current or current_kind not in {"entity", "location", "relationship"}:
            continue
        match = KEY_VALUE_RE.match(content)
        if not match:
            if not current.get("description"):
                current["description"] = content
            continue
        key = match.group(1).lower()
        value = match.group(2).strip()
        if key in {"tags", "tag"}:
            current["tags"] = _split_csv(value)
        elif key in {"properties", "property", "stats"}:
            current.setdefault("properties", {}).update(_properties(value))
        elif key == "type":
            current["type"] = value
        elif key in {"location", "location_id"}:
            current["location_id"] = value.strip()
        elif key == "name":
            current["name"] = value
        elif key in {"description", "summary"}:
            current["description"] = value
        elif current_kind == "relationship" and key in {"source", "source_id"}:
            current["source_id"] = value
        elif current_kind == "relationship" and key in {"target", "target_id"}:
            current["target_id"] = value
        else:
            current.setdefault("properties", {})[key] = _scalar(value)

    return {
        "entities": entities,
        "locations": locations,
        "relationships": relationships,
        "canon": canon,
        "constraints": constraints,
    }


def _merge_collection(target: dict[str, Any], incoming: Any, kind: str, path: Path) -> None:
    if incoming is None:
        return
    if isinstance(incoming, dict):
        items = incoming.items()
    elif isinstance(incoming, list):
        items = ((str(item.get("id", "")), item) for item in incoming)
    else:
        raise IngestError(f"{path}: {kind} must be a list or object")
    for key, item in items:
        if not isinstance(item, dict):
            raise IngestError(f"{path}: {kind}.{key} must be an object")
        item_id = str(item.get("id") or key)
        if not item_id:
            raise IngestError(f"{path}: {kind} entry is missing an id")
        if item_id in target:
            if target[item_id] != item:
                raise IngestError(f"{path}: duplicate {kind} id {item_id!r} with different content")
            continue
        target[item_id] = dict(item)


def _merge_fragment(builder: dict[str, Any], fragment: dict[str, Any], path: Path) -> None:
    if "world_id" in fragment and not builder.get("world_id"):
        builder["world_id"] = str(fragment["world_id"])
    if "title" in fragment and not builder.get("title"):
        builder["title"] = str(fragment["title"])
    if "description" in fragment and not builder.get("description"):
        builder["description"] = str(fragment["description"])
    if "settings" in fragment:
        builder.setdefault("settings", {}).update(fragment["settings"])
    for kind in ("entities", "locations", "relationships", "constraints"):
        _merge_collection(builder.setdefault(kind, {}), fragment.get(kind), kind, path)

    incoming_rules = fragment.get("rules")
    if incoming_rules:
        rules = builder.setdefault("rules", {})
        if isinstance(incoming_rules, dict):
            rules.update(incoming_rules)
        elif isinstance(incoming_rules, list):
            for rule in incoming_rules:
                rule_id = str(rule.get("id", ""))
                if not rule_id:
                    raise IngestError(f"{path}: rule missing id")
                if rule_id in rules:
                    raise IngestError(f"{path}: duplicate rule id {rule_id!r}")
                rules[rule_id] = rule
        else:
            raise IngestError(f"{path}: rules must be a list or object")

    incoming_canon = fragment.get("canon")
    if incoming_canon:
        canon = builder.setdefault("canon", [])
        raw = (
            incoming_canon.get("facts", []) if isinstance(incoming_canon, dict) else incoming_canon
        )
        for item in raw:
            if isinstance(item, str):
                canon.append({"id": f"CF-{len(canon) + 1:03d}", "statement": item})
            elif isinstance(item, dict):
                if "id" not in item:
                    item = dict(item)
                    item["id"] = f"CF-{len(canon) + 1:03d}"
                canon.append(item)
    if fragment.get("regression_suite"):
        builder.setdefault("regression_suite", []).extend(fragment["regression_suite"])


def parse_markdown(path: Path, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace("_", " ").title()
    fragment = _parse_markdown_body(text, path)
    for fenced in _fenced_fragments(text, path):
        _merge_fragment(fragment, fenced, path)
    source_document = {
        "path": path.name,
        "title": title,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "headings": _outline(text),
        "excerpt": re.sub(r"\s+", " ", text).strip()[:400],
        "ingested_at": utc_now(),
    }
    fragment["title"] = fragment.get("title") or title
    return fragment, source_document


def ingest_directory(
    root: str | Path,
    title: str | None = None,
    *,
    ignore_existing_world: bool = False,
) -> World:
    """Build a world from Markdown/JSON/YAML material in ``root``."""

    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise IngestError(f"Not a directory: {directory}")

    world_file = directory / "world.json"
    if world_file.exists() and not ignore_existing_world:
        return read_world_file(world_file)

    builder: dict[str, Any] = {
        "world_id": slugify(title or directory.name),
        "title": title or directory.name.replace("_", " ").title(),
        "description": "",
        "schema_version": SCHEMA_VERSION,
        "entities": {},
        "locations": {},
        "relationships": {},
        "rules": {},
        "constraints": {},
        "canon": [],
        "source_documents": [],
        "settings": {"ingestion": "markdown-json-yaml"},
    }
    sources = 0
    identity_from_source = title is not None
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if any(
            part in IGNORED_DIRS or part.startswith(".")
            for part in path.relative_to(directory).parts[:-1]
        ):
            continue
        if path.name in IGNORED_FILES or path.name.startswith("."):
            continue
        if ignore_existing_world and path.name == "world.json":
            continue
        suffix = path.suffix.lower()
        if suffix not in {".md", ".json", ".yaml", ".yml"}:
            continue
        sources += 1
        relative = path.relative_to(directory)
        if suffix == ".md":
            text = path.read_text(encoding="utf-8")
            fragment, source_document = parse_markdown(path, text)
            source_document["path"] = str(relative)
            builder["source_documents"].append(source_document)
            _merge_fragment(builder, fragment, path)
            if not identity_from_source and fragment.get("world_id"):
                builder["world_id"] = str(fragment["world_id"]).strip()
            if not identity_from_source and fragment.get("title"):
                builder["title"] = fragment["title"]
            identity_from_source = True
        else:
            payload = read_structured_file(path)
            if not isinstance(payload, dict):
                continue
            if not (COLLECTION_KEYS & set(payload)):
                continue
            _merge_fragment(builder, payload, path)
            if not identity_from_source and payload.get("world_id"):
                builder["world_id"] = str(payload["world_id"]).strip()
            if not identity_from_source and payload.get("title"):
                builder["title"] = payload["title"]
            identity_from_source = True
            builder["source_documents"].append(
                {
                    "path": str(relative),
                    "title": payload.get("title", path.stem),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "headings": [],
                    "excerpt": (
                        "Structured world fragment "
                        f"({', '.join(sorted(COLLECTION_KEYS & set(payload)))})"
                    ),
                    "ingested_at": utc_now(),
                }
            )

    if sources == 0:
        raise IngestError(f"No Markdown, JSON, or YAML source material found in {directory}")

    builder["created_at"] = utc_now()
    builder["updated_at"] = utc_now()
    try:
        world = World.from_dict(builder)
    except ValidationError as exc:
        raise IngestError(f"Source material produced an invalid world: {exc}") from exc
    if not world.entities and not world.locations and not world.rules:
        raise IngestError(
            "No structured entities, locations, or rules were found. Add a fenced JSON "
            "world fragment or use the documented Markdown entity format."
        )
    return world


def read_world_file(path: Path) -> World:
    payload = read_structured_file(path)
    try:
        return World.from_dict(payload)
    except ValidationError as exc:
        raise IngestError(f"Invalid world file {path}: {exc}") from exc


def init_world(
    root: str | Path,
    title: str | None = None,
    *,
    ignore_existing_world: bool = False,
) -> World:
    directory = Path(root).expanduser().resolve()
    if (directory / "world.json").exists() and not ignore_existing_world:
        return read_world_file(directory / "world.json")
    return ingest_directory(directory, title=title, ignore_existing_world=ignore_existing_world)
