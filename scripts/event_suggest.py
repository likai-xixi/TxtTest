from __future__ import annotations

import argparse
import re
import sys

from _common import ROOT, chapter_parts, read_text


def first_quote(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return ""


def add_suggestion(items: list[tuple[str, str, str, str]], kind: str, fact: str, quote: str, consequence: str) -> None:
    items.append((kind, fact, quote, consequence))


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest human-confirmable event ledger entries without writing them.")
    parser.add_argument("chapter")
    args = parser.parse_args()

    try:
        volume, chapter_file = chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    chapter_path = ROOT / "chapters" / volume / chapter_file
    text = read_text(chapter_path)
    if not text.strip():
        print(f"ERROR: missing non-empty official chapter: {chapter_path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    quote = first_quote(text)
    suggestions: list[tuple[str, str, str, str]] = []
    add_suggestion(
        suggestions,
        "character_decision",
        "记录本章主角最重要的主动选择。",
        quote,
        "明确下一章的人物动机或信息差。",
    )
    if re.search(r"义眼|设备|钥匙|刀|枪|符|手机|芯片|道具|装备", text):
        add_suggestion(
            suggestions,
            "object_change",
            "记录本章关键道具、装备或物品状态变化。",
            quote,
            "防止后续遗忘道具归属、限制或损坏状态。",
        )
    if re.search(r"规则|只能|不能|代价|限制|能力|技能", text):
        add_suggestion(
            suggestions,
            "rule_reveal",
            "记录本章揭示的技能、能力或世界规则边界。",
            quote,
            "防止后续把能力写成万能规则。",
        )
    if re.search(r"伏笔|信号|谜|线索|旧案", text):
        add_suggestion(
            suggestions,
            "thread_opened",
            "记录本章新开或推进的未解决伏笔。",
            quote,
            "让 open_threads 在后续 context pack 中持续可见。",
        )

    print(f"# Event Suggestions: {args.chapter}")
    print()
    print("以下只是建议，不会写入 state/event_ledger.jsonl。人类确认后再运行 `python scripts/novel.py event ...`。")
    print()
    for index, (kind, fact, evidence_quote, consequence) in enumerate(suggestions, 1):
        print(f"## Suggestion {index}")
        print()
        print(f"- type: {kind}")
        print(f"- fact: {fact}")
        print(f"- evidence_quote: {evidence_quote}")
        print(f"- consequence: {consequence}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
