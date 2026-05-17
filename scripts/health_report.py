from __future__ import annotations

import argparse
import json
from collections import Counter

from _common import ROOT, chapter_number, gate_decision


def load_events(max_chapter: int) -> list[dict]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    events: list[dict] = []
    if not ledger.exists():
        return events
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        chapter = str(item.get("chapter", ""))
        try:
            number = chapter_number(chapter)
        except ValueError:
            continue
        if number <= max_chapter:
            events.append(item)
    return events


def gate_risks(max_chapter: int) -> list[str]:
    risks: list[str] = []
    if max_chapter >= 3 and gate_decision("a") != "continue":
        risks.append("Gate A not recorded as continue.")
    if max_chapter >= 10 and gate_decision("b") != "continue":
        risks.append("Gate B not recorded as continue.")
    if max_chapter >= 25 and gate_decision("c") != "continue":
        risks.append("Gate C not recorded as continue.")
    if max_chapter >= 125 and gate_decision("e") != "continue":
        risks.append("Gate E not recorded as continue.")
    return risks


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a long-form health report without mutating project state.")
    parser.add_argument("--to", required=True, help="Last chapter id, e.g. v01_c010.")
    args = parser.parse_args()

    max_chapter = chapter_number(args.to)
    events = load_events(max_chapter)
    counts = Counter(event["type"] for event in events)
    open_threads = sum(counts[item] for item in ("thread_opened", "thread_advanced"))
    paid_threads = counts["thread_paid_off"]

    print(f"# Health Report: through {args.to}")
    print()
    print(f"events: {len(events)}")
    print(f"character_decisions: {counts['character_decision']}")
    print(f"character_state_changes: {counts['character_state_change']}")
    print(f"object_changes: {counts['object_change']}")
    print(f"rule_reveals: {counts['rule_reveal']}")
    print(f"open_or_active_threads: {open_threads}")
    print(f"paid_off_threads: {paid_threads}")
    print()
    print("## Drift Signals")
    print()
    if counts["rule_reveal"] > max(3, max_chapter // 2):
        print("- 规则/能力揭示偏多，注意设定膨胀。")
    if open_threads > paid_threads + 5:
        print("- 未解决伏笔偏多，建议安排回收或降级。")
    if counts["character_decision"] < max(1, max_chapter // 2):
        print("- 主角主动选择记录偏少，注意主角欲望变软。")
    if not events:
        print("- 暂无事件账本，无法评估长期健康。")
    print()
    print("## Gate Risk")
    print()
    risks = gate_risks(max_chapter)
    if risks:
        for risk in risks:
            print(f"- {risk}")
    else:
        print("- No gate blocker detected for this range.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
