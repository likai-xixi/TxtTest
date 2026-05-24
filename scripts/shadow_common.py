from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256


SCHEMA_VERSION = 1
SHADOW_VERSION = 1
ROUTES = ("fast", "normal", "heavy", "gate")
ROUTE_RANK = {name: index for index, name in enumerate(ROUTES)}
SHADOW_ROOT = ROOT / "state" / "shadow"
LOCAL_WINDOW_DIR = SHADOW_ROOT / "local_window"
RAG_INDEX_DIR = SHADOW_ROOT / "rag_index"
KG_EDGES_DIR = SHADOW_ROOT / "kg_edges"
ROUTE_SIGNALS_DIR = SHADOW_ROOT / "route_signals"
MANIFEST_DIR = SHADOW_ROOT / "manifests"
SOURCE_BOUNDARY = "shadow_advisory_not_fact_source"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path, *, boundary: str = SOURCE_BOUNDARY) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "exists": path.exists(), "source_boundary": boundary}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
        item["stale"] = False
    else:
        item["sha256"] = ""
        item["stale"] = False
    return item


def read_events() -> list[dict[str, Any]]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def context_manifest_path(chapter: str) -> Path:
    return ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"


def shadow_paths(chapter: str) -> dict[str, Path]:
    return {
        "local_window": LOCAL_WINDOW_DIR / f"{chapter}.json",
        "rag_index": RAG_INDEX_DIR / f"{chapter}.json",
        "kg_edges": KG_EDGES_DIR / f"{chapter}.json",
        "route_signals": ROUTE_SIGNALS_DIR / f"{chapter}.json",
        "manifest": MANIFEST_DIR / f"{chapter}.json",
    }


def shadow_markdown_path(path: Path) -> Path:
    return path.with_suffix(".md")


def source_refs_for_chapter(chapter: str, *, include_official_chapter: bool = True) -> list[dict[str, Any]]:
    paths = [
        ROOT / "state" / "event_ledger.jsonl",
        brief_path(chapter),
        ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json",
        ROOT / "state" / "derived" / "thread_debt_ledger.json",
        ROOT / "state" / "derived" / "character_arc_ledger.json",
        ROOT / "state" / "derived" / "style_voice_ledger.json",
        ROOT / "state" / "derived" / "personality" / "protagonist.json",
        ROOT / "state" / "derived" / "world_reveal_ledger.json",
        ROOT / "state" / "derived" / "suspense_ledger.json",
    ]
    previous_number = chapter_number(chapter) - 1
    if previous_number >= 1:
        paths.append(ROOT / "state" / "derived" / "chapter_anchors" / f"{chapter[:3]}_c{previous_number:03d}.json")
    manifest = context_manifest_path(chapter)
    if manifest.exists():
        paths.append(manifest)
    if include_official_chapter:
        paths.append(chapter_path(chapter))
    return [file_ref(path) for path in paths]


def current_ref_failures(ref: Any) -> list[str]:
    if not isinstance(ref, dict):
        return ["source ref must be an object"]
    rel_path = str(ref.get("path") or "").strip()
    recorded_sha = str(ref.get("sha256") or "").strip()
    recorded_exists = ref.get("exists")
    if not rel_path:
        return ["source ref missing path"]
    path = ROOT / rel_path
    if recorded_exists is False:
        if path.exists():
            return [f"{rel_path} was recorded missing but now exists"]
        return []
    if not path.exists():
        return [f"{rel_path} is missing"]
    if not recorded_sha:
        return [f"{rel_path} missing sha256"]
    if sha256(path) != recorded_sha:
        return [f"{rel_path} hash is stale"]
    return []


def event_refs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for event in events:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        refs.append(
            {
                "event_id": event_id,
                "chapter": str(event.get("chapter") or ""),
                "type": str(event.get("type") or ""),
                "importance": str(event.get("importance") or "P2"),
                "confidence": 1.0,
                "source_boundary": "event_ledger_fact_source",
            }
        )
    return refs


def max_route(left: str, right: str) -> str:
    left = left if left in ROUTE_RANK else "heavy"
    right = right if right in ROUTE_RANK else "heavy"
    return left if ROUTE_RANK[left] >= ROUTE_RANK[right] else right


def write_shadow_json(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def write_shadow_markdown(path: Path, title: str, data: dict[str, Any], lines: list[str]) -> None:
    body = [f"# {title}", "", f"chapter: {data.get('chapter', '')}", f"status: {data.get('status', '')}", f"source_boundary: {SOURCE_BOUNDARY}", ""]
    body.extend(lines)
    body.extend(["", "## Source Refs", ""])
    for ref in data.get("source_refs", []):
        bits = [str(ref.get("path") or "")]
        if ref.get("event_id"):
            bits.append(f"event_id={ref['event_id']}")
        if ref.get("sha256"):
            bits.append(f"sha256={str(ref['sha256'])[:12]}")
        body.append("- " + "; ".join(bit for bit in bits if bit))
    write_text(path, "\n".join(body).rstrip() + "\n")


def lightweight_terms(text: str) -> set[str]:
    tokens: set[str] = set()
    current = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            current.append(char)
        else:
            if len(current) >= 2:
                tokens.add("".join(current).lower())
            current = []
    if len(current) >= 2:
        tokens.add("".join(current).lower())
    return tokens


def group_events_by_entity(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        entities = event.get("entities")
        if not isinstance(entities, list):
            continue
        for entity in entities:
            entity_id = str(entity).strip()
            if entity_id:
                grouped[entity_id].append(event)
    return dict(grouped)


def base_artifact(
    chapter: str,
    artifact: str,
    *,
    status: str,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    source_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "artifact": artifact,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "source_boundary": SOURCE_BOUNDARY,
        "can_write_context_pack": False,
        "can_write_canon": False,
        "can_write_event_ledger": False,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "source_refs": source_refs or source_refs_for_chapter(chapter),
        "stale": False,
    }


def load_shadow_json(path: Path) -> dict[str, Any]:
    data = read_json(path, {})
    return data if isinstance(data, dict) else {}
