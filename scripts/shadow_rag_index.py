from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_text
from shadow_common import (
    RAG_INDEX_DIR,
    SOURCE_BOUNDARY,
    base_artifact,
    brief_path,
    chapter_path,
    event_refs,
    file_ref,
    lightweight_terms,
    read_events,
    shadow_markdown_path,
    source_refs_for_chapter,
    write_shadow_json,
    write_shadow_markdown,
)


def source_entry(path, *, kind: str, text: str, event_ids: list[str] | None = None, confidence: float = 0.75) -> dict[str, Any]:
    terms = sorted(lightweight_terms(text))[:80]
    ref = file_ref(path)
    return {
        "kind": kind,
        "source": ref,
        "event_ids": event_ids or [],
        "terms": terms,
        "confidence": confidence,
        "stale": False,
        "source_boundary": ref.get("source_boundary", SOURCE_BOUNDARY),
        "excerpt": text.strip().replace("\n", " ")[:300],
    }


def event_entry(event: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(event.get(key) or "") for key in ("fact", "consequence", "thread_id"))
    return {
        "kind": "event",
        "source": file_ref(ROOT / "state" / "event_ledger.jsonl", boundary="event_ledger_fact_source"),
        "event_ids": [str(event.get("event_id") or "")],
        "terms": sorted(lightweight_terms(text))[:80],
        "confidence": 1.0,
        "stale": False,
        "source_boundary": "event_ledger_fact_source",
        "excerpt": text[:300],
        "chapter": str(event.get("chapter") or ""),
        "importance": str(event.get("importance") or "P2"),
    }


def prior_events(chapter: str) -> list[dict[str, Any]]:
    current = chapter_number(chapter)
    selected = []
    for event in read_events():
        event_chapter = str(event.get("chapter") or "")
        if "_c" not in event_chapter:
            continue
        try:
            number = chapter_number(event_chapter)
        except ValueError:
            continue
        if number < current:
            selected.append(event)
    return selected[-200:]


def build(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    entries: list[dict[str, Any]] = []
    brief = brief_path(chapter)
    official = chapter_path(chapter)
    if not brief.exists():
        blockers.append(f"missing official brief: {brief.relative_to(ROOT).as_posix()}")
    else:
        entries.append(source_entry(brief, kind="brief_contract", text=read_text(brief), confidence=0.8))
    if official.exists():
        entries.append(source_entry(official, kind="official_chapter", text=read_text(official), confidence=0.9))
    else:
        warnings.append("official chapter is not present; rag index is pre-draft only")
    events = prior_events(chapter)
    entries.extend(event_entry(event) for event in events)
    data = base_artifact(
        chapter,
        "rag_index",
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        warnings=warnings,
        source_refs=source_refs_for_chapter(chapter, include_official_chapter=official.exists()),
    )
    data.update(
        {
            "index_kind": "deterministic_json_shadow_no_vector_db",
            "vector_memory_enabled": False,
            "queryable_fields": ["kind", "terms", "event_ids", "source.path", "confidence", "stale"],
            "entries": entries,
            "event_refs": event_refs(events),
            "confidence": 0.85 if not blockers else 0.0,
            "stale": False,
        }
    )
    return data


def render_markdown(data: dict[str, Any]) -> list[str]:
    entries = data.get("entries", [])
    lines = ["## RAG Index", "", "- mode: deterministic JSON shadow; vector DB disabled", ""]
    lines.append("## Entries")
    if isinstance(entries, list) and entries:
        for entry in entries[:40]:
            source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
            lines.append(f"- {entry.get('kind')}: {source.get('path')} confidence={entry.get('confidence')}")
    else:
        lines.append("- none")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic JSON shadow RAG index for one chapter.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    try:
        data = build(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.write:
        path = RAG_INDEX_DIR / f"{args.chapter}.json"
        write_shadow_json(path, data)
        write_shadow_markdown(shadow_markdown_path(path), "Shadow RAG Index", data, render_markdown(data))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"status: {data['status']}")
        print(f"source_boundary: {SOURCE_BOUNDARY}")
        print(f"entries: {len(data.get('entries', []))}")
        for blocker in data.get("blockers", []):
            print(f"- {blocker}")
    return 0 if data["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
