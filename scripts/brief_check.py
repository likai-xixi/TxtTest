from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, read_text


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


def sections(text: str) -> dict[str, str]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            result.setdefault(current, [])
            continue
        if current is not None:
            result[current].append(line)
    return {key: "\n".join(value).strip() for key, value in result.items()}


def check_brief(path: Path) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"missing brief: {path.relative_to(ROOT)}"]
    text = read_text(path)
    parsed = sections(text)
    for name in REQUIRED_SECTIONS:
        if name not in parsed:
            failures.append(f"missing required section: {name}")
            continue
        body = parsed[name]
        if not body:
            failures.append(f"empty required section: {name}")
        elif any(marker in body for marker in PLACEHOLDER_MARKERS):
            failures.append(f"section still has placeholder text: {name}")
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
