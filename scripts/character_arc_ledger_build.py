from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from _common import ROOT, chapter_number, now_iso, write_json, write_text
from product_kernel import SOURCE_PRIORITY, event_ledger_path, file_ref, read_event_ledger


ARC_EVENTS = {"character_decision", "character_state_change", "relationship_change"}


def event_entities(event: dict[str, Any]) -> list[str]:
    entities = event.get("entities")
    if isinstance(entities, list):
        return [str(item) for item in entities if str(item).strip()]
    delta = event.get("personality_delta")
    if isinstance(delta, dict) and delta.get("target_entity"):
        return [str(delta["target_entity"])]
    return ["protagonist"] if event.get("type") in ARC_EVENTS else []


def delta_value(event: dict[str, Any], key: str) -> str:
    delta = event.get("personality_delta")
    if isinstance(delta, dict) and str(delta.get(key, "")).strip():
        return str(delta[key]).strip()
    value = event.get(key)
    return str(value).strip() if str(value or "").strip() else ""


def inferred_arc_state(entity: str, ordered: list[dict[str, Any]]) -> dict[str, str]:
    latest = ordered[-1]
    fact = str(latest.get("fact", "")).strip()
    consequence = str(latest.get("consequence", "")).strip()
    delta_type = delta_value(latest, "delta_type") or str(latest.get("type", "event_delta"))
    return {
        "character_id": entity,
        "chapter": str(latest.get("chapter", "")),
        "desire": delta_value(latest, "desire") or "unknown_from_event_ledger",
        "fear": delta_value(latest, "fear") or "unknown_from_event_ledger",
        "default_strategy": delta_value(latest, "default_strategy") or "unknown_from_event_ledger",
        "changed_by_event": str(latest.get("event_id", "")),
        "delta_type": delta_type,
        "allowed_future_behavior": delta_value(latest, "allowed_future_behavior") or consequence or fact or "derive_from_human_accepted_events",
        "forbidden_future_behavior": delta_value(latest, "forbidden_future_behavior") or "do_not_invent_growth_without_human_accepted_event",
    }


def evaluate(to_chapter: str) -> dict[str, Any]:
    max_chapter = chapter_number(to_chapter)
    events = [event for event in read_event_ledger() if chapter_number(str(event.get("chapter", "v00_c000"))) <= max_chapter]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("type") not in ARC_EVENTS:
            continue
        for entity in event_entities(event):
            grouped[entity].append(event)
    arcs = []
    for entity, items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: chapter_number(str(item["chapter"])))
        state = inferred_arc_state(entity, ordered)
        arcs.append(
            {
                "entity_id": entity,
                "character_id": state["character_id"],
                "chapter": state["chapter"],
                "desire": state["desire"],
                "fear": state["fear"],
                "default_strategy": state["default_strategy"],
                "changed_by_event": state["changed_by_event"],
                "delta_type": state["delta_type"],
                "allowed_future_behavior": state["allowed_future_behavior"],
                "forbidden_future_behavior": state["forbidden_future_behavior"],
                "latest_chapter": ordered[-1]["chapter"],
                "event_count": len(ordered),
                "events": [
                    {
                        "event_id": str(item.get("event_id")),
                        "chapter": str(item.get("chapter")),
                        "type": str(item.get("type")),
                        "fact": str(item.get("fact", "")),
                        "importance": str(item.get("importance", "P2")),
                    }
                    for item in ordered
                ],
                "source_priority_applied": "event_ledger",
            }
        )
    warnings = [] if arcs else ["no character arc events found through target chapter"]
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "through": to_chapter,
        "status": "WARNING" if warnings else "READY",
        "source_priority": SOURCE_PRIORITY,
        "source_event_ledger": file_ref(event_ledger_path()),
        "arcs": arcs,
        "blockers": [],
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Character Arc Ledger: through {report['through']}", "", f"status: {report['status']}", "", "## Arcs", ""]
    for item in report.get("arcs", []):
        lines.append(f"- {item['entity_id']}: events={item['event_count']} latest={item['latest_chapter']}")
    if not report.get("arcs"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the derived character arc ledger.")
    parser.add_argument("--to", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        write_json(ROOT / "state" / "derived" / "character_arc_ledger.json", report)
        write_text(ROOT / "state" / "derived" / "character_arc_ledger.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
