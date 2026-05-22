from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, read_json, read_text
from element_context import brief_schema_version, markdown_sections, missing_section, section_body
from reader_personality_contracts import (
    READER_BRIEF_REQUIRED_LABELS,
    READER_BRIEF_REQUIRED_SECTIONS,
    READER_EXPERIENCE_REVIEWS,
    accepted_by_human_is_current,
    metadata_value,
    official_chapter_path,
    required_reviews_for_chapter,
    review_bound_to_current_chapter,
    review_status,
)


def check_brief_reader_contracts(chapter: str) -> list[str]:
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    if not brief.exists():
        return [f"missing brief: {brief.relative_to(ROOT)}"]
    text = read_text(brief)
    if brief_schema_version(text) == 2:
        return []
    parsed = markdown_sections(text)
    failures: list[str] = []
    for aliases in READER_BRIEF_REQUIRED_SECTIONS:
        if missing_section(parsed, aliases):
            failures.append(f"missing reader contract section: {aliases[0]}")
        elif not section_body(parsed, aliases).strip():
            failures.append(f"empty reader contract section: {aliases[0]}")
        else:
            body = section_body(parsed, aliases)
            for field in READER_BRIEF_REQUIRED_LABELS.get(aliases[0], ()):
                if not metadata_value(body, field):
                    failures.append(f"reader contract section {aliases[0]} missing field: {field}")
    return failures


def check_reviews(chapter: str) -> list[str]:
    failures: list[str] = []
    official = official_chapter_path(chapter)
    for name in required_reviews_for_chapter(chapter):
        path = ROOT / "reviews" / chapter / name
        if not path.exists() or not read_text(path).strip():
            failures.append(f"missing review: {path.relative_to(ROOT)}")
            continue
        text = read_text(path)
        status = review_status(text)
        if status not in {"CLEAR", "BLOCKED", "ACCEPTED_BY_HUMAN"}:
            failures.append(f"{name} status is {status or 'MISSING'}")
        if status == "BLOCKED":
            failures.append(f"{name} is BLOCKED")
        if status == "CLEAR" and name in required_reviews_for_chapter(chapter) and not review_bound_to_current_chapter(text, official):
            failures.append(f"{name} official chapter hash is missing or stale")
        if status == "ACCEPTED_BY_HUMAN" and not accepted_by_human_is_current(text, path, official):
            failures.append(f"{name} human acceptance is stale or incomplete")
    return failures


def check_derived(kind: str) -> list[str]:
    mapping = {
        "personality": ROOT / "state" / "derived" / "personality" / "protagonist.json",
        "suspense": ROOT / "state" / "derived" / "suspense_ledger.json",
        "world": ROOT / "state" / "derived" / "world_reveal_ledger.json",
        "progression": ROOT / "state" / "derived" / "protagonist_progression.json",
    }
    path = mapping[kind]
    if not path.exists():
        return [f"missing derived {kind}: {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    failures = [str(item) for item in data.get("blockers", []) if str(item).strip()] if isinstance(data, dict) else ["derived report malformed"]
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check reader experience/personality derived evidence.")
    parser.add_argument("kind", choices=["opening-retention", "personality", "suspense", "world-reveal", "protagonist-progression", "reader-experience"])
    parser.add_argument("chapter", nargs="?")
    args = parser.parse_args()
    failures: list[str] = []
    if args.chapter:
        try:
            chapter_parts(args.chapter)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if args.kind in {"opening-retention", "reader-experience"}:
        if not args.chapter:
            print("ERROR: chapter is required for review checks", file=sys.stderr)
            return 1
        failures.extend(check_brief_reader_contracts(args.chapter))
        failures.extend(check_reviews(args.chapter))
    if args.kind == "personality":
        failures.extend(check_derived("personality"))
    if args.kind == "suspense":
        failures.extend(check_derived("suspense"))
    if args.kind == "world-reveal":
        failures.extend(check_derived("world"))
    if args.kind == "protagonist-progression":
        failures.extend(check_derived("progression"))
    print(f"# {args.kind} Check{': ' + args.chapter if args.chapter else ''}")
    print()
    if failures:
        print("status: NOT_READY")
        print()
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
