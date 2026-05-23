from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from _common import ROOT, chapter_number, now_iso, write_json, write_text
from product_kernel import SOURCE_PRIORITY, event_ledger_path, file_ref, read_event_ledger


THREAD_EVENTS = {
    "thread_opened",
    "thread_advanced",
    "thread_paid_off",
    "thread_deferred",
    "thread_abandoned",
    "correction",
}
ADVANCE_WINDOWS = {"P0": 3, "P1": 5, "P2": 10}
PAYOFF_WINDOWS = {"P0": 25, "P1": 40, "P2": 80}
DEFAULT_ALLOWED_DEFERRALS = {"P0": 1, "P1": 2, "P2": 3, "P3": 999}


def chapter_id(volume: str, number: int) -> str:
    return f"{volume}_c{max(number, 1):03d}"


def normalized_level(*values: object) -> str:
    combined = " ".join(str(value or "") for value in values)
    for level in ("P0", "P1", "P2", "P3"):
        if level in combined:
            return level
    return "P2"


def event_thread_id(event: dict[str, Any]) -> str:
    return str(event.get("thread_id") or event.get("fact") or event.get("event_id") or "unknown_thread")


def event_has_human_abandon_reason(event: dict[str, Any]) -> bool:
    if event.get("verified_by") != "human":
        return False
    for key in ("reason", "human_reason", "consequence", "fact"):
        if str(event.get(key, "")).strip():
            return True
    return False


def evaluate(to_chapter: str) -> dict[str, Any]:
    max_chapter = chapter_number(to_chapter)
    volume = to_chapter[:3]
    events = [event for event in read_event_ledger() if chapter_number(str(event.get("chapter", "v00_c000"))) <= max_chapter]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("type") not in THREAD_EVENTS:
            continue
        thread_id = event_thread_id(event)
        grouped[thread_id].append(event)
    threads: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for thread_id, items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: chapter_number(str(item["chapter"])))
        first = ordered[0]
        latest = ordered[-1]
        level = normalized_level(
            first.get("importance"),
            latest.get("importance"),
            thread_id,
            *(tag for item in ordered for tag in item.get("tags", []) if str(tag).strip()),
        )
        opened_number = chapter_number(str(first["chapter"]))
        latest_number = chapter_number(str(latest["chapter"]))
        last_advance_event = next(
            (item for item in reversed(ordered) if item.get("type") in {"thread_opened", "thread_advanced"}),
            first,
        )
        last_advanced_number = chapter_number(str(last_advance_event["chapter"]))
        paid_off = any(item.get("type") == "thread_paid_off" for item in ordered)
        abandon_events = [item for item in ordered if item.get("type") == "thread_abandoned" or item.get("status") == "abandoned_by_human"]
        deferred_events = [item for item in ordered if item.get("type") == "thread_deferred" or item.get("status") == "deferred"]
        status = "open"
        if paid_off:
            status = "paid_off"
        elif abandon_events:
            status = "abandoned_by_human"
        elif deferred_events and deferred_events[-1] is latest:
            status = "deferred"
        elif any(item.get("type") == "thread_advanced" for item in ordered):
            status = "active"
        age = max_chapter - opened_number + 1
        advance_window = ADVANCE_WINDOWS.get(level)
        payoff_window = PAYOFF_WINDOWS.get(level)
        next_required_number = last_advanced_number + advance_window if advance_window else None
        payoff_due_number = opened_number + payoff_window if payoff_window else None
        current_deferrals = len(deferred_events)
        allowed_deferrals = DEFAULT_ALLOWED_DEFERRALS.get(level, 3)
        advance_due = (
            status not in {"paid_off", "abandoned_by_human"}
            and next_required_number is not None
            and max_chapter >= next_required_number
        )
        payoff_due = (
            status not in {"paid_off", "abandoned_by_human"}
            and payoff_due_number is not None
            and max_chapter >= payoff_due_number
        )
        deferral_overuse = current_deferrals > allowed_deferrals
        abandoned_without_reason = bool(abandon_events) and not any(event_has_human_abandon_reason(item) for item in abandon_events)
        if advance_due:
            warnings.append(f"{thread_id} {level} needs advancement by {chapter_id(volume, next_required_number or max_chapter)}")
        if payoff_due:
            warnings.append(f"{thread_id} {level} payoff window reached by {chapter_id(volume, payoff_due_number or max_chapter)}")
        if deferral_overuse:
            blockers.append(f"{thread_id} exceeded allowed deferrals: {current_deferrals}/{allowed_deferrals}")
        if abandoned_without_reason:
            blockers.append(f"{thread_id} abandoned_by_human requires a human reason")
        threads.append(
            {
                "thread_id": thread_id,
                "level": level,
                "status": status,
                "opened_at": first["chapter"],
                "opened_chapter": first["chapter"],
                "last_advanced_at": last_advance_event["chapter"],
                "latest_chapter": latest["chapter"],
                "next_required_advance_by": chapter_id(volume, next_required_number) if next_required_number else "gate_check",
                "payoff_due_by": chapter_id(volume, payoff_due_number) if payoff_due_number else "gate_check",
                "allowed_deferrals": allowed_deferrals,
                "current_deferrals": current_deferrals,
                "age_chapters": age,
                "due": advance_due or payoff_due or deferral_overuse,
                "advance_due": advance_due,
                "payoff_due": payoff_due,
                "importance": level,
                "event_ids": [str(item.get("event_id")) for item in ordered],
                "source_priority_applied": "event_ledger",
            }
        )
    status = "BLOCKED" if blockers else ("WARNING" if warnings else "READY")
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "through": to_chapter,
        "status": status,
        "source_priority": SOURCE_PRIORITY,
        "source_event_ledger": file_ref(event_ledger_path()),
        "threads": threads,
        "blockers": blockers,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Thread Debt Ledger: through {report['through']}",
        "",
        f"status: {report['status']}",
        "",
        "## Threads",
        "",
    ]
    for item in report.get("threads", []):
        lines.append(
            f"- {item['thread_id']}: {item.get('level', 'P2')} {item['status']} "
            f"age={item['age_chapters']} due={item['due']} next={item.get('next_required_advance_by')}"
        )
    if not report.get("threads"):
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the derived thread debt ledger.")
    parser.add_argument("--to", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        write_json(ROOT / "state" / "derived" / "thread_debt_ledger.json", report)
        write_text(ROOT / "state" / "derived" / "thread_debt_ledger.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
