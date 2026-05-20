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
from validate_event_ledger import ALLOWED_TYPES, IMPORTANCE_LEVELS, validate
from reader_personality_contracts import parse_personality_delta_json, validate_personality_delta


EVENT_RE = re.compile(r"^v\d{2}_c\d{3}_e(?P<num>\d{3})$")


def anchor_args_present(args: argparse.Namespace) -> bool:
    return any(
        [
            args.anchor_end_time,
            args.anchor_end_location,
            args.anchor_present_character,
            args.anchor_protagonist_state,
            args.anchor_carried_item,
            args.anchor_unfinished_action,
            args.anchor_next_required_continuity,
        ]
    )


def build_anchor(args: argparse.Namespace) -> dict | None:
    if args.type != "chapter_anchor":
        if anchor_args_present(args):
            raise ValueError("anchor fields are only allowed with --type chapter_anchor")
        return None
    required = {
        "--anchor-end-time": args.anchor_end_time,
        "--anchor-end-location": args.anchor_end_location,
        "--anchor-protagonist-state": args.anchor_protagonist_state,
        "--anchor-unfinished-action": args.anchor_unfinished_action,
        "--anchor-next-required-continuity": args.anchor_next_required_continuity,
    }
    missing = [flag for flag, value in required.items() if not str(value or "").strip()]
    if not args.anchor_present_character:
        missing.append("--anchor-present-character")
    if not args.anchor_carried_item:
        missing.append("--anchor-carried-item")
    if missing:
        raise ValueError("chapter_anchor requires " + ", ".join(missing))
    return {
        "end_time": args.anchor_end_time.strip(),
        "end_location": args.anchor_end_location.strip(),
        "present_characters": args.anchor_present_character,
        "protagonist_state": args.anchor_protagonist_state.strip(),
        "carried_items": args.anchor_carried_item,
        "unfinished_action": args.anchor_unfinished_action.strip(),
        "next_required_continuity": args.anchor_next_required_continuity.strip(),
    }


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
    parser.add_argument("--entity", action="append", default=[], help="Entity id touched by this event; may be repeated.")
    parser.add_argument("--thread-id", default="", help="Long-running thread id when the event opens/advances/pays off a thread.")
    parser.add_argument("--importance", choices=sorted(IMPORTANCE_LEVELS), default=None)
    parser.add_argument("--tag", action="append", default=[], help="Search tag for this event; may be repeated.")
    parser.add_argument("--anchor-end-time", default="", help="For chapter_anchor: visible end time.")
    parser.add_argument("--anchor-end-location", default="", help="For chapter_anchor: visible end location.")
    parser.add_argument("--anchor-present-character", action="append", default=[], help="For chapter_anchor: character present at chapter end; may be repeated.")
    parser.add_argument("--anchor-protagonist-state", default="", help="For chapter_anchor: protagonist physical/emotional state.")
    parser.add_argument("--anchor-carried-item", action="append", default=[], help="For chapter_anchor: carried item or evidence; may be repeated.")
    parser.add_argument("--anchor-unfinished-action", default="", help="For chapter_anchor: unfinished action at chapter end.")
    parser.add_argument("--anchor-next-required-continuity", default="", help="For chapter_anchor: continuity the next chapter must address.")
    parser.add_argument("--personality-delta-json", default="", help="For character_state_change: JSON personality_delta object.")
    args = parser.parse_args()

    if write_blocked_by_locks("event ledger append"):
        return 1

    chapter_parts(args.chapter)
    ledger = ROOT / "state" / "event_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    try:
        anchor = build_anchor(args)
        personality_delta = parse_personality_delta_json(args.personality_delta_json)
        delta_errors = validate_personality_delta(personality_delta, args.type)
        if delta_errors:
            raise ValueError("; ".join(delta_errors))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid --personality-delta-json: {exc}", file=sys.stderr)
        return 1

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
            if args.entity:
                entry["entities"] = args.entity
            if args.thread_id:
                entry["thread_id"] = args.thread_id
            if args.importance:
                entry["importance"] = args.importance
            if args.tag:
                entry["tags"] = args.tag
            if anchor is not None:
                entry["anchor"] = anchor
            if personality_delta is not None:
                entry["personality_delta"] = personality_delta
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
