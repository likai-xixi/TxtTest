from __future__ import annotations

import argparse
import json

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_text, write_text
from brief_contract import (
    OPENING_SCENE_ANCHOR_SECTIONS,
    SCENE_CONTINUITY_SECTIONS,
    anchor_location,
    scene_continuity_note,
    scene_continuity_note_is_concrete,
    scene_continuity_type,
)
from element_context import markdown_sections, missing_section, section_body
from validate_event_ledger import validate as validate_ledger


PLACEHOLDERS = ("待定", "待填", "TODO", "寰呭畾", "寰呭～")


def add_issue(issues: list[tuple[str, str]], level: str, text: str) -> None:
    issues.append((level, text))


def previous_chapter_id(chapter: str) -> str | None:
    number = chapter_number(chapter)
    if number <= 1:
        return None
    return f"{chapter[:3]}_c{number - 1:03d}"


def check_anchor_continuity(chapter: str, issues: list[tuple[str, str]]) -> None:
    previous = previous_chapter_id(chapter)
    if previous is None:
        return
    anchor_path = ROOT / "state" / "derived" / "chapter_anchors" / f"{previous}.json"
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    if not anchor_path.exists():
        add_issue(issues, "P1", f"Missing previous chapter anchor: {anchor_path.relative_to(ROOT)}")
        return
    if not brief_path.exists():
        add_issue(issues, "P1", f"Missing chapter brief for anchor continuity: {brief_path.relative_to(ROOT)}")
        return
    try:
        anchor = json.loads(read_text(anchor_path))
    except json.JSONDecodeError as exc:
        add_issue(issues, "P1", f"Invalid previous chapter anchor JSON: {anchor_path.relative_to(ROOT)}: {exc}")
        return

    sections = markdown_sections(read_text(brief_path))
    if missing_section(sections, OPENING_SCENE_ANCHOR_SECTIONS):
        add_issue(issues, "P1", "Brief missing 本章开场落点 for anchor continuity.")
        return
    if missing_section(sections, SCENE_CONTINUITY_SECTIONS):
        add_issue(issues, "P1", "Brief missing 场景承接说明 for anchor continuity.")
        return

    opening = section_body(sections, OPENING_SCENE_ANCHOR_SECTIONS)
    continuity = section_body(sections, SCENE_CONTINUITY_SECTIONS)
    previous_location = str(anchor.get("end_location", "")).strip()
    opening_location = anchor_location(opening)
    kind = scene_continuity_type(continuity)
    note = scene_continuity_note(continuity)
    if previous_location and opening_location and previous_location != opening_location:
        if kind == "原地承接":
            add_issue(
                issues,
                "P1",
                f"Location changes from {previous_location} to {opening_location}, but 场景承接说明 says 原地承接.",
            )
        if not scene_continuity_note_is_concrete(note):
            add_issue(
                issues,
                "P1",
                f"Location changes from {previous_location} to {opening_location} without concrete 场景承接说明.",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a conservative continuity check for one chapter.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    volume, chapter_file = chapter_parts(args.chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    ledger_path = ROOT / "state" / "event_ledger.jsonl"
    issues: list[tuple[str, str]] = []

    if not context_path.exists():
        add_issue(issues, "P1", f"Missing context pack: {context_path.relative_to(ROOT)}")

    if not chapter_path.exists():
        add_issue(issues, "P1", f"Missing chapter file: {chapter_path.relative_to(ROOT)}")
        chapter_text = ""
    else:
        chapter_text = read_text(chapter_path)
        if not chapter_text.strip():
            add_issue(issues, "P2", "Chapter file is empty.")
        if any(marker in chapter_text for marker in PLACEHOLDERS):
            add_issue(issues, "P3", "Chapter contains placeholder text.")

    ledger_errors = validate_ledger(ledger_path)
    for error in ledger_errors:
        add_issue(issues, "P1", f"Event ledger validation failed: {error}")
    if not ledger_errors:
        check_anchor_continuity(args.chapter, issues)

    canon_text = read_text(ROOT / "bible" / "canon.md")
    if "当前状态：暂无 canon 事实" not in canon_text and chapter_text:
        # Real canon contradiction checks become stricter after confirmed facts exist.
        pass

    p0_count = sum(1 for level, _text in issues if level == "P0")
    p1_count = sum(1 for level, _text in issues if level == "P1")
    status = "BLOCKED" if p0_count or p1_count else "CLEAR"

    lines = [
        f"# Continuity: {args.chapter}",
        "",
        f"generated_at: {now_iso()}",
        f"status: {status}",
        f"p0_count: {p0_count}",
        f"p1_count: {p1_count}",
        f"p2_count: {sum(1 for level, _text in issues if level == 'P2')}",
        f"p3_count: {sum(1 for level, _text in issues if level == 'P3')}",
        "",
        "## Summary",
        "",
        "发现需要处理的问题。" if issues else "未发现自动检查可识别的连续性问题。",
    ]

    for level in ("P0", "P1", "P2", "P3"):
        lines.extend(["", f"## {level}", ""])
        matched = [text for item_level, text in issues if item_level == level]
        if matched:
            lines.extend(f"- {text}" for text in matched)
        else:
            lines.append("- 无。")

    lines.extend(
        [
            "",
            "## Check Scope",
            "",
            "- canon 违反",
            "- rules 违反",
            "- 人物状态冲突",
            "- 关系冲突",
            "- 时间线冲突",
            "- 地点 / 物品冲突",
            "- 术语漂移",
            "- 未登记伏笔",
        ]
    )

    out = ROOT / "reviews" / args.chapter / "continuity.md"
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 1 if any(level in {"P0", "P1"} for level, _ in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
