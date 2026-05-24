from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_json
from shadow_common import (
    KG_EDGES_DIR,
    SOURCE_BOUNDARY,
    base_artifact,
    event_refs,
    file_ref,
    group_events_by_entity,
    read_events,
    shadow_markdown_path,
    source_refs_for_chapter,
    write_shadow_json,
    write_shadow_markdown,
)


def edge(source: str, relation: str, target: str, *, evidence: dict[str, Any], confidence: float = 1.0) -> dict[str, Any]:
    return {
        "source": source,
        "relation": relation,
        "target": target,
        "evidence": evidence,
        "confidence": confidence,
        "stale": False,
        "source_boundary": evidence.get("source_boundary", SOURCE_BOUNDARY),
    }


def event_evidence(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(event.get("event_id") or ""),
        "chapter": str(event.get("chapter") or ""),
        "event_type": str(event.get("type") or ""),
        "importance": str(event.get("importance") or "P2"),
        "quote": str(event.get("evidence_quote") or event.get("fact") or "")[:240],
        "source": file_ref(ROOT / "state" / "event_ledger.jsonl", boundary="event_ledger_fact_source"),
        "source_boundary": "event_ledger_fact_source",
    }


def prior_events(chapter: str) -> list[dict[str, Any]]:
    current = chapter_number(chapter)
    values = []
    for event in read_events():
        raw = str(event.get("chapter") or "")
        if "_c" not in raw:
            continue
        try:
            number = chapter_number(raw)
        except ValueError:
            continue
        if number < current:
            values.append(event)
    return values[-300:]


def derived_thread_edges() -> list[dict[str, Any]]:
    path = ROOT / "state" / "derived" / "thread_debt_ledger.json"
    data = read_json(path, {})
    if not isinstance(data, dict):
        return []
    result = []
    for item in data.get("threads", []) if isinstance(data.get("threads"), list) else []:
        if not isinstance(item, dict):
            continue
        thread_id = str(item.get("thread_id") or item.get("id") or "")
        if not thread_id:
            continue
        status = str(item.get("status") or item.get("state") or "unknown")
        result.append(
            edge(
                thread_id,
                "has_debt_status",
                status,
                evidence={"source": file_ref(path), "source_boundary": "derived_rebuild_not_fact_source"},
                confidence=0.7,
            )
        )
    return result


def build(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    events = prior_events(chapter)
    edges: list[dict[str, Any]] = []
    for entity_id, entity_events in group_events_by_entity(events).items():
        for event in entity_events:
            evidence = event_evidence(event)
            event_type = str(event.get("type") or "event")
            edges.append(edge(entity_id, f"participates_in_{event_type}", str(event.get("event_id") or ""), evidence=evidence))
            thread_id = str(event.get("thread_id") or "").strip()
            if thread_id:
                edges.append(edge(entity_id, "touches_thread", thread_id, evidence=evidence))
            consequence = str(event.get("consequence") or "").strip()
            if consequence:
                edges.append(edge(str(event.get("event_id") or ""), "causes_consequence", consequence[:120], evidence=evidence))
    edges.extend(derived_thread_edges())
    blockers: list[str] = []
    warnings: list[str] = []
    data = base_artifact(
        chapter,
        "kg_edges",
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        warnings=warnings,
        source_refs=source_refs_for_chapter(chapter),
    )
    data.update(
        {
            "kg_kind": "deterministic_json_shadow_no_graph_db",
            "knowledge_graph_enabled": False,
            "edge_policy": "every edge must point to an event id, official quote, brief authorization, or derived source ref",
            "edges": edges[:1000],
            "event_refs": event_refs(events),
            "confidence": 0.8,
            "stale": False,
        }
    )
    return data


def render_markdown(data: dict[str, Any]) -> list[str]:
    edges = data.get("edges", [])
    lines = ["## KG Edges", "", "- mode: deterministic JSON shadow; graph DB disabled", ""]
    if isinstance(edges, list) and edges:
        for item in edges[:60]:
            lines.append(f"- {item.get('source')} --{item.get('relation')}--> {item.get('target')}")
    else:
        lines.append("- none")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic JSON shadow KG edges for one chapter.")
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
        path = KG_EDGES_DIR / f"{args.chapter}.json"
        write_shadow_json(path, data)
        write_shadow_markdown(shadow_markdown_path(path), "Shadow KG Edges", data, render_markdown(data))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"status: {data['status']}")
        print(f"source_boundary: {SOURCE_BOUNDARY}")
        print(f"edges: {len(data.get('edges', []))}")
        for blocker in data.get("blockers", []):
            print(f"- {blocker}")
    return 0 if data["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
