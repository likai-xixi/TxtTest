from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text
from brief_contract import LEDGER_EVENT_TYPES, PROGRESS_CONTRACT_SECTIONS, progress_value
from element_context import markdown_sections, section_body


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_quote(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def card(card_id: str, kind: str, fact: str, quote: str, consequence: str, importance: str = "P2") -> dict[str, Any]:
    return {
        "id": card_id,
        "type": kind,
        "importance": importance,
        "fact": fact,
        "evidence_quote": quote,
        "consequence": consequence,
        "entities": [],
        "tags": [card_id],
    }


def evaluate(chapter: str) -> dict[str, Any]:
    volume, chapter_file = chapter_parts(chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    if not chapter_path.exists() or not read_text(chapter_path).strip():
        raise FileNotFoundError(f"missing non-empty official chapter: {chapter_path.relative_to(ROOT)}")
    text = read_text(chapter_path)
    quote = first_quote(text)
    brief = read_text(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md")
    progress = section_body(markdown_sections(brief), PROGRESS_CONTRACT_SECTIONS)
    minimum_event = progress_value(progress, "minimum_ledger_event").strip()
    cards = [
        card(
            "chapter_anchor",
            "chapter_anchor",
            "Record the visible end state: time, place, people present, protagonist state, carried items, unfinished action.",
            quote,
            "The next chapter brief and context pack must inherit this anchor.",
            "P1",
        )
    ]
    if minimum_event in LEDGER_EVENT_TYPES and minimum_event != "chapter_anchor":
        cards.append(
            card(
                "minimum_ledger_event",
                minimum_event,
                f"Record the brief's minimum ledger event: {minimum_event}.",
                quote,
                "Ship evidence can verify the brief progress contract.",
                "P1",
            )
        )
    cards.append(
        card(
            "protagonist_choice",
            "character_decision",
            "Record the protagonist's most important active choice in this chapter.",
            quote,
            "Preserves agency and motivation continuity.",
            "P1",
        )
    )
    if re.search(r"\[(object|ability):[A-Za-z0-9_.-]+\]", text):
        cards.append(
            card(
                "element_state",
                "object_change",
                "Record the state change of the authorized object or ability used in this chapter.",
                quote,
                "Prevents later confusion about ownership, cost, limits, or damage.",
            )
        )
    if re.search(r"\bthread\b|clue|signal|case|伏笔|线索", text, flags=re.I):
        cards.append(
            card(
                "thread_update",
                "thread_opened",
                "Record the new or advanced unresolved thread.",
                quote,
                "Keeps the thread visible in later context packs.",
            )
        )
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "source_chapter": chapter_path.relative_to(ROOT).as_posix(),
        "source_hashes": {
            "official_chapter": sha256(chapter_path),
            "official_brief": sha256(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"),
        },
        "cards": cards[:5],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Fact Cards: {report['chapter']}", "", f"generated_at: {report['generated_at']}", ""]
    for item in report["cards"]:
        lines.extend(
            [
                f"## {item['id']}",
                "",
                f"- type: {item['type']}",
                f"- importance: {item['importance']}",
                f"- fact: {item['fact']}",
                f"- evidence_quote: {item['evidence_quote']}",
                f"- consequence: {item['consequence']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate human-confirmable chapter fact cards.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args.chapter)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.write:
        base = ROOT / "reviews" / args.chapter
        write_json(base / "fact_cards.json", report)
        write_text(base / "fact_cards.md", render_markdown(report))
        print(f"wrote: {(base / 'fact_cards.json').relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
