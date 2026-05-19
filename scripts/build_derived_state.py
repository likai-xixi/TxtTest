from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, now_iso, write_blocked_by_locks, write_text
from brief_contract import (
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    PROGRESS_CONTRACT_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
    digestion_window_chapters,
    normalized_consequence_level,
    normalized_impact_scale,
    normalized_progress_mode,
    progress_value,
)
from context_governance import rel
from element_context import markdown_sections, section_body
from validate_event_ledger import validate

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


LEDGER = ROOT / "state" / "event_ledger.jsonl"
DERIVED = ROOT / "state" / "derived"
ENTITY_SOURCES = {
    "characters": (ROOT / "bible" / "characters.yaml", "characters"),
    "objects": (ROOT / "bible" / "objects.yaml", "objects"),
    "abilities": (ROOT / "bible" / "abilities.yaml", "abilities"),
    "locations": (ROOT / "bible" / "locations.yaml", "locations"),
}
THREAD_TYPES = {"thread_opened", "thread_advanced", "thread_paid_off", "correction"}


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def yaml_quote(value: object) -> str:
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dump_data(data: Any) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def read_yaml_items(path: Path, root_key: str) -> list[dict[str, Any]]:
    if not path.exists() or yaml is None:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    items = data.get(root_key) or []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and str(item.get("id", "")).strip()]


def reset_generated_dirs() -> None:
    for path in [
        DERIVED / "entities",
        DERIVED / "threads",
        DERIVED / "indexes" / "events_by_chapter",
        DERIVED / "indexes" / "events_by_type",
        DERIVED / "arcs",
        DERIVED / "chapter_anchors",
        DERIVED / "pacing",
    ]:
        if path.exists():
            shutil.rmtree(path)


def event_entities(event: dict[str, Any]) -> list[str]:
    entities = event.get("entities")
    if isinstance(entities, list):
        return [str(item) for item in entities if str(item).strip()]
    return []


def infer_entity_type(entity_id: str) -> str:
    lowered = entity_id.lower()
    if lowered.startswith(("object_", "obj_", "item_")):
        return "objects"
    if lowered.startswith(("ability_", "skill_", "power_")):
        return "abilities"
    if lowered.startswith(("location_", "loc_", "place_")):
        return "locations"
    return "characters"


def build_entity_cards(events: list[dict[str, Any]]) -> None:
    events_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        for entity_id in event_entities(event):
            events_by_entity[entity_id].append(event)

    all_seen: set[str] = set()
    for entity_type, (source, root_key) in ENTITY_SOURCES.items():
        source_items = read_yaml_items(source, root_key)
        for item in source_items:
            entity_id = str(item["id"])
            all_seen.add(entity_id)
            card = {
                "id": entity_id,
                "entity_type": entity_type,
                "source_path": rel(source),
                "rebuilt_at": now_iso(),
                "base": item,
                "events": [
                    {
                        "event_id": event["event_id"],
                        "chapter": event["chapter"],
                        "type": event["type"],
                        "fact": event["fact"],
                        "importance": event.get("importance", "P2"),
                        "tags": event.get("tags", []),
                    }
                    for event in events_by_entity.get(entity_id, [])
                ],
            }
            write_text(DERIVED / "entities" / entity_type / f"{entity_id}.yaml", dump_data(card))

    for entity_id, matched_events in sorted(events_by_entity.items()):
        if entity_id in all_seen:
            continue
        entity_type = infer_entity_type(entity_id)
        inferred = {
            "id": entity_id,
            "entity_type": entity_type,
            "source_path": "state/event_ledger.jsonl",
            "rebuilt_at": now_iso(),
            "base": {"id": entity_id, "inferred_from_ledger": True},
            "events": [
                {
                    "event_id": event["event_id"],
                    "chapter": event["chapter"],
                    "type": event["type"],
                    "fact": event["fact"],
                    "importance": event.get("importance", "P2"),
                    "tags": event.get("tags", []),
                }
                for event in matched_events
            ],
        }
        write_text(DERIVED / "entities" / entity_type / f"{entity_id}.yaml", dump_data(inferred))


def build_threads(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    threads: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["type"] not in THREAD_TYPES:
            continue
        thread_id = str(event.get("thread_id") or event.get("fact") or event["event_id"])
        item = threads.setdefault(
            thread_id,
            {
                "id": thread_id,
                "status": "open",
                "importance": event.get("importance", "P2"),
                "opened_chapter": event["chapter"],
                "latest_chapter": event["chapter"],
                "description": event.get("fact", thread_id),
                "event_ids": [],
                "entities": [],
                "tags": [],
            },
        )
        item["latest_chapter"] = event["chapter"]
        item["description"] = event.get("fact", item["description"])
        item["importance"] = event.get("importance", item["importance"])
        item["event_ids"].append(event["event_id"])
        item["entities"] = sorted(set(item["entities"]) | set(event_entities(event)))
        tags = event.get("tags") if isinstance(event.get("tags"), list) else []
        item["tags"] = sorted(set(item["tags"]) | {str(tag) for tag in tags})
        if event["type"] == "thread_advanced":
            item["status"] = "active"
        elif event["type"] == "thread_paid_off":
            item["status"] = "paid_off"
        elif event["type"] == "correction":
            item["status"] = "corrected"
    open_items = [item for item in threads.values() if item["status"] in {"open", "corrected"}]
    active_items = [item for item in threads.values() if item["status"] == "active"]
    paid_items = [item for item in threads.values() if item["status"] == "paid_off"]
    write_text(DERIVED / "threads" / "open.yaml", dump_data({"threads": open_items}))
    write_text(DERIVED / "threads" / "active.yaml", dump_data({"threads": active_items}))
    write_text(DERIVED / "threads" / "paid_off_index.yaml", dump_data({"threads": paid_items}))
    write_text(DERIVED / "open_threads.yaml", dump_data({"threads": open_items + active_items}))
    return threads


def build_event_state(events: list[dict[str, Any]], event_type: str, root_key: str) -> str:
    items = [event for event in events if event["type"] == event_type]
    lines = [f"{root_key}:"]
    if not items:
        lines.append("  []")
        return "\n".join(lines) + "\n"
    for event in items:
        lines.extend(
            [
                f"  - id: {yaml_quote(event['event_id'])}",
                f"    latest_chapter: {yaml_quote(event['chapter'])}",
                f"    fact: {yaml_quote(event['fact'])}",
                f"    evidence_quote: {yaml_quote(event['evidence_quote'])}",
                f"    consequence: {yaml_quote(event['consequence'])}",
                f"    importance: {yaml_quote(event.get('importance', 'P2'))}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_rule_reveals(events: list[dict[str, Any]]) -> str:
    lines = ["# Rule Reveals", ""]
    matched = [event for event in events if event["type"] == "rule_reveal"]
    if not matched:
        lines.append("none")
        return "\n".join(lines) + "\n"
    for event in matched[-20:]:
        lines.append(f"- {event['event_id']} ({event['chapter']}): {event['fact']}")
    return "\n".join(lines) + "\n"


def build_indexes(events: list[dict[str, Any]]) -> None:
    by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        compact = {
            "event_id": event["event_id"],
            "chapter": event["chapter"],
            "type": event["type"],
            "fact": event["fact"],
            "importance": event.get("importance", "P2"),
            "entities": event.get("entities", []),
            "thread_id": event.get("thread_id"),
            "tags": event.get("tags", []),
        }
        by_chapter[event["chapter"]].append(compact)
        by_type[event["type"]].append(compact)
    for chapter, items in by_chapter.items():
        write_text(DERIVED / "indexes" / "events_by_chapter" / f"{chapter}.json", json.dumps(items, ensure_ascii=False, indent=2) + "\n")
    for event_type, items in by_type.items():
        write_text(DERIVED / "indexes" / "events_by_type" / f"{event_type}.json", json.dumps(items, ensure_ascii=False, indent=2) + "\n")


def chunk_bounds(number: int) -> tuple[int, int]:
    start = ((number - 1) // 50) * 50 + 1
    return start, start + 49


def build_arcs(events: list[dict[str, Any]]) -> None:
    by_chunk: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_chunk[chunk_bounds(chapter_number(event["chapter"]))].append(event)

    volume_lines = ["# Volume 01 Derived Arc", "", f"rebuilt_at: {now_iso()}", ""]
    if not by_chunk:
        volume_lines.append("- no event-ledger facts yet")
    for (start, end), chunk_events in sorted(by_chunk.items()):
        p_critical = [event for event in chunk_events if event.get("importance") in {"P0", "P1"}]
        volume_lines.append(f"- chunk_{start:03d}_{end:03d}: {len(chunk_events)} events, {len(p_critical)} P0/P1")
        lines = [f"# Arc Chunk {start:03d}-{end:03d}", "", f"rebuilt_at: {now_iso()}", ""]
        for event in chunk_events:
            marker = f" [{event.get('importance')}]" if event.get("importance") else ""
            lines.append(f"- {event['event_id']}{marker} ({event['type']}): {event['fact']}")
        write_text(DERIVED / "arcs" / f"chunk_{start:03d}_{end:03d}.md", "\n".join(lines).rstrip() + "\n")
    write_text(DERIVED / "arcs" / "volume_01.md", "\n".join(volume_lines).rstrip() + "\n")


def build_chapter_anchors(events: list[dict[str, Any]]) -> None:
    anchors: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "chapter_anchor":
            continue
        anchor = event.get("anchor")
        if not isinstance(anchor, dict):
            continue
        item = {
            "schema_version": 1,
            "chapter": event["chapter"],
            "source_event_id": event["event_id"],
            "source_path": "state/event_ledger.jsonl",
            "evidence_quote": event["evidence_quote"],
            "fact": event["fact"],
            "consequence": event["consequence"],
            "end_time": anchor.get("end_time", ""),
            "end_location": anchor.get("end_location", ""),
            "present_characters": anchor.get("present_characters", []),
            "protagonist_state": anchor.get("protagonist_state", ""),
            "carried_items": anchor.get("carried_items", []),
            "unfinished_action": anchor.get("unfinished_action", ""),
            "next_required_continuity": anchor.get("next_required_continuity", ""),
        }
        anchors[event["chapter"]] = item

    index = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "anchors": [
            {
                "chapter": item["chapter"],
                "source_event_id": item["source_event_id"],
                "end_time": item["end_time"],
                "end_location": item["end_location"],
                "next_required_continuity": item["next_required_continuity"],
            }
            for item in sorted(anchors.values(), key=lambda value: chapter_number(value["chapter"]))
        ],
    }
    write_text(DERIVED / "chapter_anchors" / "index.json", json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    latest_lines = ["# Chapter Anchors", ""]
    if not anchors:
        latest_lines.append("none")
    else:
        for item in index["anchors"][-20:]:
            latest_lines.append(
                f"- {item['chapter']} ({item['source_event_id']}): {item['end_time']} / "
                f"{item['end_location']} -> {item['next_required_continuity']}"
            )
    write_text(DERIVED / "chapter_anchors" / "latest.md", "\n".join(latest_lines).rstrip() + "\n")
    for item in anchors.values():
        write_text(DERIVED / "chapter_anchors" / f"{item['chapter']}.json", json.dumps(item, ensure_ascii=False, indent=2) + "\n")


def brief_progress_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (ROOT / "outline" / "chapter_briefs").glob("v*_c*.md"),
        key=lambda item: (item.stem[:3], chapter_number(item.stem)),
    ):
        sections = markdown_sections(path.read_text(encoding="utf-8"))
        progress = section_body(sections, PROGRESS_CONTRACT_SECTIONS)
        cost = section_body(sections, COST_CONSEQUENCE_CONTRACT_SECTIONS)
        boundary = section_body(sections, RESOLUTION_BOUNDARY_SECTIONS)
        if not progress and not cost and not boundary:
            continue
        entries.append(
            {
                "chapter": path.stem,
                "chapter_number": chapter_number(path.stem),
                "brief_path": rel(path),
                "progress_mode": normalized_progress_mode(progress_value(progress, "progress_mode")),
                "progress_target": progress_value(progress, "progress_target"),
                "start_state_ref": progress_value(progress, "start_state_ref"),
                "end_state_delta": progress_value(progress, "end_state_delta"),
                "minimum_ledger_event": progress_value(progress, "minimum_ledger_event").strip(),
                "progress_importance": progress_value(progress, "progress_importance").strip(),
                "buffer_function": progress_value(progress, "buffer_function"),
                "impact_scale": normalized_impact_scale(progress_value(cost, "impact_scale")),
                "consequence_level": normalized_consequence_level(progress_value(cost, "consequence_level")),
                "cost_type": progress_value(cost, "cost_type"),
                "cost_paid_now": progress_value(cost, "cost_paid_now"),
                "deferred_cost": progress_value(cost, "deferred_cost"),
                "aftermath_obligation": progress_value(cost, "aftermath_obligation"),
                "digestion_window": progress_value(cost, "digestion_window"),
                "digestion_window_chapters": digestion_window_chapters(progress_value(cost, "digestion_window")),
                "cooldown_scope": progress_value(cost, "cooldown_scope"),
                "opened_threads": progress_value(boundary, "opened_threads"),
                "advanced_threads": progress_value(boundary, "advanced_threads"),
                "resolved_threads": progress_value(boundary, "resolved_threads"),
                "forbidden_resolution": progress_value(boundary, "forbidden_resolution"),
                "resolution_requires_cost": progress_value(boundary, "resolution_requires_cost"),
            }
        )
    return entries


def build_progress_and_aftermath() -> None:
    entries = brief_progress_entries()
    write_text(
        DERIVED / "pacing" / "progress_index.json",
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": now_iso(),
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    obligations: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        window = entry.get("digestion_window_chapters")
        resolved_threads = str(entry.get("resolved_threads", "")).strip().lower()
        creates_obligation = (
            entry.get("impact_scale") in {"C3", "C4", "I3", "I4"}
            or entry.get("progress_mode") == "payoff"
            or resolved_threads not in {"", "none", "无", "无。"}
        )
        if not creates_obligation or window is None or window == 0:
            continue
        due_number = int(entry["chapter_number"]) + int(window)
        later = [
            item
            for item in entries[index + 1 :]
            if int(item["chapter_number"]) <= due_number
        ]
        resolving = [item for item in later if item.get("progress_mode") in {"digest", "cost_payment"}]
        status = "resolved" if resolving else "active"
        if not resolving and entries and int(entries[-1]["chapter_number"]) >= due_number:
            status = "overdue"
        obligations.append(
            {
                "source_chapter": entry["chapter"],
                "source_brief_path": entry["brief_path"],
                "progress_target": entry.get("progress_target", ""),
                "impact_scale": entry.get("impact_scale", ""),
                "aftermath_obligation": entry.get("aftermath_obligation", ""),
                "digestion_window_chapters": window,
                "due_chapter": f"{entry['chapter'][:3]}_c{due_number:03d}",
                "cooldown_scope": entry.get("cooldown_scope", ""),
                "status": status,
                "resolved_by": [item["chapter"] for item in resolving],
            }
        )
    write_text(
        DERIVED / "pacing" / "aftermath_obligations.json",
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": now_iso(),
                "obligations": obligations,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build derived state from event ledger.")
    parser.add_argument("--ledger", default=str(LEDGER))
    args = parser.parse_args()

    if write_blocked_by_locks("derived state rebuild"):
        return 1

    ledger = Path(args.ledger)
    if not ledger.is_absolute():
        ledger = ROOT / ledger

    errors = validate(ledger)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    events = load_events(ledger)
    reset_generated_dirs()
    counts = Counter(event["type"] for event in events)
    latest_chapter = events[-1]["chapter"] if events else "none"

    current_state = {
        "schema_version": 2,
        "generated_at": now_iso(),
        "total_events": len(events),
        "latest_chapter": latest_chapter,
        "counts_by_type": dict(sorted(counts.items())),
        "layers": {
            "entities": "state/derived/entities/",
            "threads": "state/derived/threads/",
            "indexes": "state/derived/indexes/",
            "arcs": "state/derived/arcs/",
            "chapter_anchors": "state/derived/chapter_anchors/",
            "pacing": "state/derived/pacing/",
            "context_quality": "state/derived/context_quality/",
        },
    }

    latest_events = ["# Latest Events", ""]
    if events:
        for event in events[-20:]:
            latest_events.append(f"- {event['event_id']} ({event['type']}): {event['fact']}")
    else:
        latest_events.append("none")

    build_entity_cards(events)
    build_threads(events)
    build_indexes(events)
    build_arcs(events)
    build_chapter_anchors(events)
    build_progress_and_aftermath()

    write_text(DERIVED / "current_state.yaml", dump_data(current_state))
    write_text(DERIVED / "latest_events.md", "\n".join(latest_events) + "\n")
    write_text(DERIVED / "current_objects.yaml", build_event_state(events, "object_change", "objects"))
    write_text(DERIVED / "current_abilities.yaml", build_event_state(events, "rule_reveal", "abilities"))
    write_text(DERIVED / "rule_reveals.md", build_rule_reveals(events))
    print("OK: built state/derived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
