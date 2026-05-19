from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, write_json, write_text
from health_report import gate_risks, infer_last_chapter, load_events


def evaluate(to_chapter: str | None = None) -> dict[str, Any]:
    target = to_chapter or infer_last_chapter()
    max_chapter = chapter_number(target)
    events = load_events(max_chapter)
    counts = Counter(event.get("type") for event in events)
    threads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("type") in {"thread_opened", "thread_advanced", "thread_paid_off"}:
            thread_id = str(event.get("thread_id") or event.get("fact") or event.get("event_id"))
            threads[thread_id].append(event)
    unresolved_ages: list[int] = []
    payoff_intervals: list[int] = []
    for items in threads.values():
        ordered = sorted(items, key=lambda item: chapter_number(str(item["chapter"])))
        opened = chapter_number(str(ordered[0]["chapter"]))
        paid = [chapter_number(str(item["chapter"])) for item in ordered if item.get("type") == "thread_paid_off"]
        if paid:
            payoff_intervals.append(max(paid) - opened)
        else:
            unresolved_ages.append(max_chapter - opened + 1)
    agency_density = 0.0 if max_chapter == 0 else counts["character_decision"] / max_chapter
    setting_debt = counts["rule_reveal"] + counts["object_change"] - counts["thread_paid_off"]
    risks: list[str] = []
    if unresolved_ages and max(unresolved_ages) >= 10:
        risks.append("old_unresolved_thread")
    if agency_density < 0.5 and max_chapter >= 3:
        risks.append("low_agency_density")
    if setting_debt > max(5, max_chapter // 2):
        risks.append("setting_debt_growing")
    if counts["thread_opened"] > counts["thread_paid_off"] + 8:
        risks.append("payoff_backlog")
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "through": target,
        "chapters": max_chapter,
        "events": len(events),
        "counts_by_type": dict(sorted(counts.items())),
        "unresolved_thread_count": len(unresolved_ages),
        "oldest_unresolved_thread_age": max(unresolved_ages) if unresolved_ages else 0,
        "average_payoff_interval": mean(payoff_intervals) if payoff_intervals else None,
        "agency_density": agency_density,
        "setting_debt_index": setting_debt,
        "gate_risks": gate_risks(max_chapter),
        "risk_flags": risks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Long Health: through {report['through']}",
        "",
        f"generated_at: {report['generated_at']}",
        f"chapters: {report['chapters']}",
        f"events: {report['events']}",
        f"agency_density: {report['agency_density']:.2f}",
        f"oldest_unresolved_thread_age: {report['oldest_unresolved_thread_age']}",
        f"average_payoff_interval: {report['average_payoff_interval']}",
        f"setting_debt_index: {report['setting_debt_index']}",
        "",
        "## Risk Flags",
        "",
    ]
    lines.extend(f"- {item}" for item in report["risk_flags"]) if report["risk_flags"] else lines.append("- none")
    lines.extend(["", "## Gate Risks", ""])
    lines.extend(f"- {item}" for item in report["gate_risks"]) if report["gate_risks"] else lines.append("- none")
    lines.extend(["", "## Counts", ""])
    lines.extend(f"- {key}: {value}" for key, value in report["counts_by_type"].items()) if report["counts_by_type"] else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show long-form health signals for a long novel run.")
    parser.add_argument("--to", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        out_dir = ROOT / "state" / "derived" / "long_health"
        write_json(out_dir / "latest.json", report)
        write_text(out_dir / "latest.md", render_markdown(report))
        print(f"wrote: {(out_dir / 'latest.md').relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
