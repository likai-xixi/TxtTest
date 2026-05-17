from __future__ import annotations

import argparse
import json
import sys

from _common import ROOT, chapter_parts, read_text


def decision_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return None


def chapter_events(chapter: str) -> list[dict]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    events: list[dict] = []
    if not ledger.exists():
        return events
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("chapter") == chapter and item.get("verified_by") == "human":
            events.append(item)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose canon entries from human-verified shipped events without writing canon.")
    parser.add_argument("chapter")
    args = parser.parse_args()

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    events = chapter_events(args.chapter)
    print(f"# Canon Proposals: {args.chapter}")
    print()
    print("以下只是候选，不会修改 bible/canon.md。人类确认后再手动晋升 canon。")
    print()
    if decision_for(args.chapter) != "Ship":
        print("WARNING: chapter decision is not Ship; canon promotion should normally wait.")
        print()
    if not events:
        print("无可提议事实：本章没有 human-verified event ledger 记录。")
        return 0
    for event in events:
        print(f"- [{event['chapter']}] {event['fact']}")
        print(f"  Evidence: \"{event['evidence_quote']}\"")
        print("  Confirmed by: human")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
