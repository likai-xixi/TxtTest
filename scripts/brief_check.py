from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, read_text
from element_context import (
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    USABLE_OBJECT_ID_SECTIONS,
    declared_ids,
    has_placeholder,
    markdown_sections,
    missing_section,
    section_body,
    yaml_id_index,
)


PLACEHOLDER_MARKERS = ("待定", "待填", "TODO", "寰呭畾", "寰呭～")
REQUIRED_SECTIONS = (
    "本章功能",
    "开篇吸引点",
    "主角目标",
    "主要阻力",
    "主角主动选择",
    "章末问题",
    "本章可用人物状态",
    "本章可用道具 / 装备",
    "本章可用技能 / 能力",
    "能力限制 / 代价",
    "未解决伏笔",
    "本章禁止新增",
    "本章禁止解决",
)
REQUIRED_ELEMENT_SECTIONS = (
    USABLE_OBJECT_ID_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
)


def check_brief(path: Path) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"missing brief: {path.relative_to(ROOT)}"]
    text = read_text(path)
    parsed = markdown_sections(text)
    for name in REQUIRED_SECTIONS:
        if name not in parsed:
            failures.append(f"missing required section: {name}")
            continue
        body = parsed[name]
        if not body:
            failures.append(f"empty required section: {name}")
        elif any(marker in body for marker in PLACEHOLDER_MARKERS):
            failures.append(f"section still has placeholder text: {name}")
    for aliases in REQUIRED_ELEMENT_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required section: {label}")
        elif has_placeholder(body):
            failures.append(f"section still has placeholder text: {label}")

    object_ids = declared_ids(section_body(parsed, USABLE_OBJECT_ID_SECTIONS))
    ability_ids = declared_ids(section_body(parsed, USABLE_ABILITY_ID_SECTIONS))
    known_objects = set(yaml_id_index(ROOT / "bible" / "objects.yaml", "objects"))
    known_abilities = set(yaml_id_index(ROOT / "bible" / "abilities.yaml", "abilities"))
    for item in object_ids:
        if item not in known_objects:
            failures.append(f"unknown object id in brief: {item}")
    for item in ability_ids:
        if item not in known_abilities:
            failures.append(f"unknown ability id in brief: {item}")
    if any(marker in text for marker in PLACEHOLDER_MARKERS):
        failures.append("brief still contains placeholder text")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a chapter brief for long-form anti-drift requirements.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    failures = check_brief(path)
    print(f"# Brief Check: {args.chapter}")
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
