from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_json
from product_kernel import gate_chapters
from shadow_common import (
    ROUTE_SIGNALS_DIR,
    SOURCE_BOUNDARY,
    base_artifact,
    file_ref,
    load_shadow_json,
    max_route,
    shadow_markdown_path,
    shadow_paths,
    source_refs_for_chapter,
    write_shadow_json,
    write_shadow_markdown,
)
from shadow_kg_edges import build as build_kg_edges
from shadow_local_window import build as build_local_window
from shadow_rag_index import build as build_rag_index


HEAVY_EVENT_TYPES = {"character_state_change", "rule_reveal", "core_mechanism_change"}
NORMAL_EVENT_TYPES = {"relationship_change", "thread_advanced", "thread_paid_off"}
HEAVY_TERMS = {"p0", "p1", "l3", "l4", "core", "mechanism", "personality_delta"}
AI_WARNING_NAMES = ("ai_taste.json", "prose_risk.json", "dialogue_function.json")


def load_or_build(chapter: str, key: str) -> dict[str, Any]:
    path = shadow_paths(chapter)[key]
    if path.exists():
        return load_shadow_json(path)
    if key == "local_window":
        return build_local_window(chapter)
    if key == "rag_index":
        return build_rag_index(chapter)
    if key == "kg_edges":
        return build_kg_edges(chapter)
    return {}


def review_warning_count(chapter: str) -> tuple[int, list[str]]:
    warnings = []
    count = 0
    review_dir = ROOT / "reviews" / chapter
    for name in AI_WARNING_NAMES:
        path = review_dir / name
        if not path.exists():
            continue
        data = read_json(path, {})
        if isinstance(data, dict) and data.get("status") in {"WARNING", "BLOCKED"}:
            count += 1
            warnings.append(f"{name} status {data.get('status')}")
    return count, warnings


def route_from_local_window(data: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    route = "fast"
    reasons: list[str] = []
    warnings: list[str] = []
    if data.get("status") == "BLOCKED":
        return "heavy", [f"local_window blocked: {', '.join(data.get('blockers', []))}"], warnings
    for event in data.get("recent_events", []) if isinstance(data.get("recent_events"), list) else []:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        importance = str(event.get("importance") or "P2")
        if event_type in HEAVY_EVENT_TYPES or importance in {"P0", "P1"}:
            route = "heavy"
            reasons.append(f"heavy event signal {event_type or 'event'} {importance}")
        elif event_type in NORMAL_EVENT_TYPES and route != "heavy":
            route = "normal"
            reasons.append(f"normal event signal {event_type}")
    debts = data.get("active_aftermath_obligations")
    if isinstance(debts, list) and debts and route == "fast":
        route = "normal"
        reasons.append("active aftermath obligations present")
    return route, reasons, warnings


def route_from_rag(data: dict[str, Any]) -> tuple[str, list[str]]:
    route = "fast"
    reasons: list[str] = []
    for entry in data.get("entries", []) if isinstance(data.get("entries"), list) else []:
        if not isinstance(entry, dict):
            continue
        terms = {str(term).lower() for term in entry.get("terms", []) if str(term).strip()}
        if terms & HEAVY_TERMS:
            route = "heavy"
            reasons.append("rag index contains high-impact terms")
            break
    return route, reasons


def route_from_kg(data: dict[str, Any]) -> tuple[str, list[str]]:
    route = "fast"
    reasons: list[str] = []
    for item in data.get("edges", []) if isinstance(data.get("edges"), list) else []:
        if not isinstance(item, dict):
            continue
        relation = str(item.get("relation") or "")
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        importance = str(evidence.get("importance") or "")
        if importance in {"P0", "P1"} or "core" in relation:
            route = "heavy"
            reasons.append(f"kg high-impact edge {relation}")
            break
        if relation in {"touches_thread", "has_debt_status"} and route == "fast":
            route = "normal"
            reasons.append(f"kg thread/debt edge {relation}")
    return route, reasons


def build(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    route = "gate" if chapter_number(chapter) in gate_chapters() else "fast"
    reasons: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    local_window = load_or_build(chapter, "local_window")
    rag_index = load_or_build(chapter, "rag_index")
    kg_edges = load_or_build(chapter, "kg_edges")
    for label, data in (("local_window", local_window), ("rag_index", rag_index), ("kg_edges", kg_edges)):
        if data.get("status") == "BLOCKED":
            blockers.extend(f"{label}: {item}" for item in data.get("blockers", []))
            route = max_route(route, "heavy")

    local_route, local_reasons, local_warnings = route_from_local_window(local_window)
    rag_route, rag_reasons = route_from_rag(rag_index)
    kg_route, kg_reasons = route_from_kg(kg_edges)
    route = max_route(route, local_route)
    route = max_route(route, rag_route)
    route = max_route(route, kg_route)
    reasons.extend(local_reasons + rag_reasons + kg_reasons)
    warnings.extend(local_warnings)

    warning_count, review_warnings = review_warning_count(chapter)
    warnings.extend(review_warnings)
    if warning_count >= 2:
        route = max_route(route, "normal")
        reasons.append("repeated review warnings raise route")
    if blockers:
        route = max_route(route, "heavy")

    paths = shadow_paths(chapter)
    refs = source_refs_for_chapter(chapter)
    refs.extend(file_ref(paths[key]) for key in ("local_window", "rag_index", "kg_edges"))
    data = base_artifact(
        chapter,
        "route_signals",
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        warnings=warnings,
        source_refs=refs,
    )
    data.update(
        {
            "route": route,
            "route_upper_bound_only": True,
            "can_downgrade_route": False,
            "must_not_skip_ship_evidence": True,
            "reasons": sorted(set(reasons)),
            "required_review_floor": "always_required_ship_gates",
            "shadow_inputs": {
                "local_window": file_ref(paths["local_window"]),
                "rag_index": file_ref(paths["rag_index"]),
                "kg_edges": file_ref(paths["kg_edges"]),
            },
            "confidence": 0.8 if not blockers else 0.0,
            "stale": False,
        }
    )
    return data


def render_markdown(data: dict[str, Any]) -> list[str]:
    lines = ["## Route Signals", "", f"- route: {str(data.get('route', 'heavy')).upper()}", "- shadow can only upgrade route; it cannot downgrade route", "- Ship evidence remains mandatory", "", "## Reasons"]
    reasons = data.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.extend(f"- {item}" for item in reasons)
    else:
        lines.append("- none")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Build shadow route signals for one chapter.")
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
        path = ROUTE_SIGNALS_DIR / f"{args.chapter}.json"
        write_shadow_json(path, data)
        write_shadow_markdown(shadow_markdown_path(path), "Shadow Route Signals", data, render_markdown(data))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"status: {data['status']}")
        print(f"route: {str(data.get('route', 'heavy')).upper()}")
        print(f"source_boundary: {SOURCE_BOUNDARY}")
        for reason in data.get("reasons", []):
            print(f"- {reason}")
    return 0 if data["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
