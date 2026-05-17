from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from _common import ROOT, chapter_parts, write_blocked_by_locks
from validate_event_ledger import ALLOWED_TYPES, validate


EVENT_RE = re.compile(r"^v\d{2}_c\d{3}_e(?P<num>\d{3})$")


def next_event_id(chapter: str, ledger_text: str) -> str:
    max_num = 0
    for line in ledger_text.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("chapter") != chapter:
            continue
        match = EVENT_RE.match(entry.get("event_id", ""))
        if match:
            max_num = max(max_num, int(match.group("num")))
    return f"{chapter}_e{max_num + 1:03d}"


class LedgerLock:
    def __init__(self, path: Path, timeout: float = 10.0) -> None:
        self.path = path
        self.timeout = timeout

    def __enter__(self) -> "LedgerLock":
        deadline = time.time() + self.timeout
        while True:
            try:
                self.path.mkdir(parents=True)
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(f"timed out waiting for ledger lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        try:
            self.path.rmdir()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one human-verified fact to state/event_ledger.jsonl.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--type", required=True, choices=sorted(ALLOWED_TYPES))
    parser.add_argument("--fact", required=True)
    parser.add_argument("--evidence-quote", required=True)
    parser.add_argument("--consequence", required=True)
    parser.add_argument("--event-id", default=None)
    args = parser.parse_args()

    if write_blocked_by_locks("event ledger append"):
        return 1

    chapter_parts(args.chapter)
    ledger = ROOT / "state" / "event_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)

    try:
        with LedgerLock(ledger.parent / ".event_ledger.lock"):
            current = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
            entry = {
                "event_id": args.event_id or next_event_id(args.chapter, current),
                "chapter": args.chapter,
                "type": args.type,
                "fact": args.fact,
                "evidence_quote": args.evidence_quote,
                "consequence": args.consequence,
                "verified_by": "human",
            }
            proposed_line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
            proposed = current + proposed_line
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=ledger.parent,
                prefix="event_ledger.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp = Path(handle.name)
                handle.write(proposed)
                handle.flush()
                os.fsync(handle.fileno())

            errors = validate(temp)
            if errors:
                try:
                    temp.unlink()
                except FileNotFoundError:
                    pass
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1

            os.replace(temp, ledger)
    except TimeoutError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: appended {entry['event_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
