from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_json, read_text
from shadow_common import (
    LOCAL_WINDOW_DIR,
    SOURCE_BOUNDARY,
    base_artifact,
    brief_path,
    event_refs,
    file_ref,
    read_events,
    shadow_markdown_path,
    source_refs_for_chapter,
    write_shadow_json,
    write_shadow_markdown,
)


def recent_events(chapter: str, events: list[dict[str, Any]], window: int = 5) -> list[dict[str, Any]]:
    current = chapter_number(chapter)
    lower = max(1, current - window)
    selected = []
    for event in events:
        event_chapter = str(event.get("chapter") or "")
        if "_c" not in event_chapter:
            continue
        try:
            number = chapter_number(event_chapter)
        except ValueError:
            continue
        importance = str(event.get("importance") or "P2")
        if lower <= number < current or (number < current and importance in {"P0", "P1"}):
            selected.append(event)
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(selected, key=lambda item: (rank.get(str(item.get("importance") or "P2"), 2), str(item.get("chapter") or ""), str(item.get("event_id") or "")))[:80]


def previous_anchor_ref(chapter: str) -> dict[str, Any] | None:
    number = chapter_number(chapter)
    if number <= 1:
        return None
    path = ROOT / "state" / "derived" / "chapter_anchors" / f"{chapter[:3]}_c{number - 1:03d}.json"
    return file_ref(path)


def current_debts() -> list[dict[str, Any]]:
    path = ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json"
    data = read_json(path, {})
    if not isinstance(data, dict):
        return []
    values = data.get("obligations") or data.get("items") or []
    return [item for item in values if isinstance(item, dict)][:40] if isinstance(values, list) else []


def build(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    events = recent_events(chapter, read_events())
    brief = brief_path(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    if not brief.exists():
        blockers.append(f"missing official brief: {brief.relative_to(ROOT).as_posix()}")
    anchor = previous_anchor_ref(chapter)
    refs = source_refs_for_chapter(chapter, include_official_chapter=False)
    if anchor is not None:
        refs.append(anchor)
    data = base_artifact(
        chapter,
        "local_window",
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        warnings=warnings,
        source_refs=refs,
    )
    data.update(
        {
            "window_policy": {
                "recent_chapter_window": 5,
                "include_all_prior_p0_p1": True,
                "purpose": "tone_action_emotion_continuity_only",
            },
            "allowed_use": ["tone_continuity", "action_carryover", "emotion_carryover", "unresolved_debt_visibility"],
            "forbidden_use": ["canon_source", "plot_breaker_authorization", "context_pack_fact_injection"],
            "official_brief": file_ref(brief, boundary="brief_instruction_not_fact_source"),
            "previous_anchor": anchor,
            "recent_event_refs": event_refs(events),
            "recent_events": [
                {
                    "event_id": str(event.get("event_id") or ""),
                    "chapter": str(event.get("chapter") or ""),
                    "type": str(event.get("type") or ""),
                    "importance": str(event.get("importance") or "P2"),
                    "fact": str(event.get("fact") or ""),
                    "consequence": str(event.get("consequence") or ""),
                    "thread_id": str(event.get("thread_id") or ""),
                    "entities": event.get("entities") if isinstance(event.get("entities"), list) else [],
                    "confidence": 1.0,
                    "source_boundary": "event_ledger_fact_source",
                }
                for event in events
            ],
            "active_aftermath_obligations": current_debts(),
            "confidence": 1.0 if not blockers else 0.0,
            "stale": False,
        }
    )
    return data


def render_markdown(data: dict[str, Any]) -> str:
    events = data.get("recent_events", [])
    lines = ["## Local Window", ""]
    lines.append("- allowed_use: tone/action/emotion continuity only")
    lines.append("- forbidden_use: canon, plot breaker authorization, direct fact injection")
    lines.append("")
    lines.append("## Recent Events")
    if isinstance(events, list) and events:
        for event in events[:20]:
            lines.append(f"- {event.get('event_id')}: {event.get('fact')} -> {event.get('consequence')}")
    else:
        lines.append("- none")
    debts = data.get("active_aftermath_obligations")
    lines.extend(["", "## Active Aftermath Obligations"])
    if isinstance(debts, list) and debts:
        for debt in debts[:20]:
            label = debt.get("obligation_id") or debt.get("id") or debt.get("thread_id") or "obligation"
            lines.append(f"- {label}: {debt.get('description') or debt.get('consequence') or debt}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the shadow local-window artifact for one chapter.")
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
        path = LOCAL_WINDOW_DIR / f"{args.chapter}.json"
        write_shadow_json(path, data)
        write_shadow_markdown(shadow_markdown_path(path), "Shadow Local Window", data, render_markdown(data).splitlines())
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"status: {data['status']}")
        print(f"source_boundary: {SOURCE_BOUNDARY}")
        print(f"recent_events: {len(data.get('recent_events', []))}")
        if data.get("blockers"):
            for blocker in data["blockers"]:
                print(f"- {blocker}")
    return 0 if data["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
