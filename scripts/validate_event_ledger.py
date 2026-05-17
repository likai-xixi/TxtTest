from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import ROOT


ALLOWED_TYPES = {
    "character_decision",
    "character_state_change",
    "relationship_change",
    "world_fact",
    "rule_reveal",
    "thread_opened",
    "thread_advanced",
    "thread_paid_off",
    "location_change",
    "object_change",
    "correction",
}

REQUIRED = {
    "event_id",
    "chapter",
    "type",
    "fact",
    "evidence_quote",
    "consequence",
    "verified_by",
}

EVENT_RE = re.compile(r"^v\d{2}_c\d{3}_e\d{3}$")
CHAPTER_RE = re.compile(r"^v\d{2}_c\d{3}$")


def chapter_path(chapter: str) -> Path:
    return ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"


def collapse_ws(value: str) -> str:
    return re.sub(r"\s+", "", value)


def quote_is_anchored(chapter: str, quote: str) -> tuple[bool, str]:
    path = chapter_path(chapter)
    rel = path.relative_to(ROOT)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return False, f"missing official chapter for evidence_quote: {rel}"
    normalized_quote = collapse_ws(quote)
    normalized_chapter = collapse_ws(path.read_text(encoding="utf-8"))
    if normalized_quote not in normalized_chapter:
        return False, f"evidence_quote not found in official chapter {rel}"
    return True, ""


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    if not path.exists():
        return [f"Missing ledger: {path}"]

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc}")
            continue

        missing = REQUIRED - set(entry)
        if missing:
            errors.append(f"line {line_no}: missing fields: {', '.join(sorted(missing))}")

        extra = set(entry) - REQUIRED
        if extra:
            errors.append(f"line {line_no}: extra fields: {', '.join(sorted(extra))}")

        event_id = entry.get("event_id", "")
        if not EVENT_RE.match(str(event_id)):
            errors.append(f"line {line_no}: invalid event_id {event_id!r}")
        elif event_id in seen:
            errors.append(f"line {line_no}: duplicate event_id {event_id}")
        else:
            seen.add(event_id)

        chapter = entry.get("chapter", "")
        chapter_valid = False
        if not CHAPTER_RE.match(str(chapter)):
            errors.append(f"line {line_no}: invalid chapter {chapter!r}")
        elif EVENT_RE.match(str(event_id)) and not str(event_id).startswith(f"{chapter}_e"):
            errors.append(f"line {line_no}: event_id {event_id!r} does not match chapter {chapter!r}")
            chapter_valid = True
        else:
            chapter_valid = True

        event_type = entry.get("type")
        if event_type not in ALLOWED_TYPES:
            errors.append(f"line {line_no}: invalid type {event_type!r}")

        if entry.get("verified_by") != "human":
            errors.append(f"line {line_no}: verified_by must be 'human'")

        for field in ("fact", "evidence_quote", "consequence"):
            if not str(entry.get(field, "")).strip():
                errors.append(f"line {line_no}: {field} must not be empty")

        quote = str(entry.get("evidence_quote", "")).strip()
        if chapter_valid and quote:
            anchored, message = quote_is_anchored(str(chapter), quote)
            if not anchored:
                errors.append(f"line {line_no}: {message}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate state/event_ledger.jsonl.")
    parser.add_argument("--path", default="state/event_ledger.jsonl")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    errors = validate(path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
