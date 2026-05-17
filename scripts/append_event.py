from __future__ import annotations

import argparse
import json
import re
import sys

from _common import ROOT, chapter_parts
from validate_event_ledger import ALLOWED_TYPES, validate


EVENT_RE = re.compile(r"^v\d{2}_c\d{3}_e(?P<num>\d{3})$")


def next_event_id(chapter: str) -> str:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    max_num = 0
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("chapter") != chapter:
                continue
            match = EVENT_RE.match(entry.get("event_id", ""))
            if match:
                max_num = max(max_num, int(match.group("num")))
    return f"{chapter}_e{max_num + 1:03d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one human-verified fact to state/event_ledger.jsonl.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--type", required=True, choices=sorted(ALLOWED_TYPES))
    parser.add_argument("--fact", required=True)
    parser.add_argument("--evidence-quote", required=True)
    parser.add_argument("--consequence", required=True)
    parser.add_argument("--event-id", default=None)
    args = parser.parse_args()

    chapter_parts(args.chapter)
    ledger = ROOT / "state" / "event_ledger.jsonl"
    entry = {
        "event_id": args.event_id or next_event_id(args.chapter),
        "chapter": args.chapter,
        "type": args.type,
        "fact": args.fact,
        "evidence_quote": args.evidence_quote,
        "consequence": args.consequence,
        "verified_by": "human",
    }

    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")

    errors = validate(ledger)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: appended {entry['event_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

