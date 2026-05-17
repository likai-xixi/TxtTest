from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from _common import ROOT, now_iso, write_blocked_by_locks, write_text
from validate_event_ledger import validate


LEDGER = ROOT / "state" / "event_ledger.jsonl"


def load_events(path: Path) -> list[dict]:
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_open_threads(events: list[dict]) -> str:
    threads: dict[str, dict] = {}
    for event in events:
        event_type = event["type"]
        if event_type not in {"thread_opened", "thread_advanced", "thread_paid_off", "correction"}:
            continue
        key = event.get("fact", event["event_id"])
        item = threads.setdefault(
            key,
            {
                "id": event["event_id"],
                "status": "open",
                "importance": "medium",
                "opened_chapter": event["chapter"],
                "latest_chapter": event["chapter"],
                "description": key,
                "evidence_quote": event["evidence_quote"],
            },
        )
        item["latest_chapter"] = event["chapter"]
        item["evidence_quote"] = event["evidence_quote"]
        if event_type == "thread_advanced":
            item["status"] = "active"
        elif event_type == "thread_paid_off":
            item["status"] = "paid_off"
        elif event_type == "correction":
            item["status"] = "corrected"

    lines = ["threads:"]
    if not threads:
        lines.append("  []")
        return "\n".join(lines) + "\n"

    for item in threads.values():
        lines.extend(
            [
                f"  - id: {yaml_quote(item['id'])}",
                f"    status: {yaml_quote(item['status'])}",
                f"    importance: {yaml_quote(item['importance'])}",
                f"    opened_chapter: {yaml_quote(item['opened_chapter'])}",
                f"    latest_chapter: {yaml_quote(item['latest_chapter'])}",
                f"    description: {yaml_quote(item['description'])}",
                f"    evidence_quote: {yaml_quote(item['evidence_quote'])}",
            ]
        )
    return "\n".join(lines) + "\n"


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
    counts = Counter(event["type"] for event in events)
    latest_chapter = events[-1]["chapter"] if events else "none"

    current_state = [
        f"generated_at: {yaml_quote(now_iso())}",
        f"total_events: {len(events)}",
        f"latest_chapter: {yaml_quote(latest_chapter)}",
        "counts_by_type:",
    ]
    if counts:
        for key in sorted(counts):
            current_state.append(f"  {key}: {counts[key]}")
    else:
        current_state.append("  {}")

    latest_events = ["# Latest Events", ""]
    if events:
        for event in events[-20:]:
            latest_events.append(f"- {event['event_id']} ({event['type']}): {event['fact']}")
    else:
        latest_events.append("暂无。")

    write_text(ROOT / "state" / "derived" / "current_state.yaml", "\n".join(current_state) + "\n")
    write_text(ROOT / "state" / "derived" / "open_threads.yaml", build_open_threads(events))
    write_text(ROOT / "state" / "derived" / "latest_events.md", "\n".join(latest_events) + "\n")
    print("OK: built state/derived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
