from __future__ import annotations

import argparse
import re
import sys

from _common import ROOT, chapter_parts, read_text
from brief_contract import LEDGER_EVENT_TYPES, PROGRESS_CONTRACT_SECTIONS, progress_value
from element_context import markdown_sections, section_body


def first_quote(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return ""


def add_suggestion(items: list[tuple[str, str, str, str]], kind: str, fact: str, quote: str, consequence: str) -> None:
    items.append((kind, fact, quote, consequence))


def quote_arg(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def command_for(chapter: str, kind: str, fact: str, quote: str, consequence: str) -> str:
    parts = [
        "python",
        "scripts/novel.py",
        "event",
        chapter,
        "--type",
        kind,
        "--fact",
        quote_arg(fact),
        "--evidence-quote",
        quote_arg(quote or "TODO：粘贴正文原文证据"),
        "--consequence",
        quote_arg(consequence),
    ]
    if kind == "chapter_anchor":
        parts.extend(
            [
                "--importance",
                "P1",
                "--tag",
                "chapter_anchor",
                "--anchor-end-time",
                quote_arg("TODO：人类确认章末时间"),
                "--anchor-end-location",
                quote_arg("TODO：人类确认章末地点"),
                "--anchor-present-character",
                quote_arg("TODO：在场人物ID"),
                "--anchor-protagonist-state",
                quote_arg("TODO：主角章末状态"),
                "--anchor-carried-item",
                quote_arg("TODO：携带物或证据；没有则写 none"),
                "--anchor-unfinished-action",
                quote_arg("TODO：未完成动作"),
                "--anchor-next-required-continuity",
                quote_arg("TODO：下一章必须承接的连续性"),
            ]
        )
    return " ".join(parts)


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
    brief = read_text(ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md")
    progress = section_body(markdown_sections(brief), PROGRESS_CONTRACT_SECTIONS)
    minimum_event = progress_value(progress, "minimum_ledger_event").strip()
    suggestions: list[tuple[str, str, str, str]] = []
    add_suggestion(
        suggestions,
        "chapter_anchor",
        "记录本章章末可见状态：时间、地点、在场人物、主角状态、携带物/证据、未完成动作。",
        quote,
        "下一章 brief 和 context pack 必须承接该章末锚点，防止无解释跳场。",
    )
    if minimum_event in LEDGER_EVENT_TYPES and minimum_event != "chapter_anchor":
        add_suggestion(
            suggestions,
            minimum_event,
            f"记录 brief 进展契约承诺的最低落账事件：{minimum_event}。",
            quote,
            "Ship evidence 会检查该事件是否进入 event ledger。",
        )
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
    print("以下只是建议和命令草案，不会写入 state/event_ledger.jsonl。人类确认并替换 TODO 后再执行。")
    print()
    for index, (kind, fact, evidence_quote, consequence) in enumerate(suggestions, 1):
        print(f"## Suggestion {index}")
        print()
        print(f"- type: {kind}")
        print(f"- fact: {fact}")
        print(f"- evidence_quote: {evidence_quote}")
        print(f"- consequence: {consequence}")
        print()
        print("```bash")
        print(command_for(args.chapter, kind, fact, evidence_quote, consequence))
        print("```")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
