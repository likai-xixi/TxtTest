from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import ROOT, now_iso, read_text, write_text


QUESTIONS = [
    ("类型是什么？", "类型"),
    ("一句话卖点是什么？", "一句话卖点"),
    ("主角是谁？", "主角"),
    ("主角想要什么？", "主角想要什么"),
    ("主角怕失去什么？", "主角怕失去什么"),
    ("主角误信念是什么？", "主角误信念"),
    ("世界最大异常是什么？", "世界最大异常"),
    ("核心冲突来自哪里？", "核心冲突"),
    ("第一章开篇吸引点是什么？", "第一章开篇吸引点"),
    ("前三章要验证什么？", "前三章要验证什么"),
    ("绝对不写什么？", "绝对不写什么"),
    ("参考作品只允许借鉴哪些抽象技法？", "参考作品抽象技法边界"),
]


HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def parse_answers(text: str) -> dict[str, str]:
    answers: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            current = match.group(1).strip()
            answers.setdefault(current, [])
            continue
        if current:
            answers[current].append(line)
    return {key: "\n".join(value).strip() for key, value in answers.items()}


def is_blank(answer: str) -> bool:
    return not answer.strip() or answer.strip() in {"待填", "待定", "TODO"}


def build_premise(answers: dict[str, str]) -> str:
    lines = [
        "# Premise",
        "",
        f"问卷落盘时间：{now_iso()}",
        "",
        "启动问卷答案先进入本文件和 `bible/open_questions.md`，不能直接进入 canon。",
        "",
    ]
    for question, title in QUESTIONS:
        lines.extend([f"## {title}", "", answers.get(question, "待定。").strip() or "待定。", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_open_questions(answers: dict[str, str]) -> str:
    lines = [
        "# Open Questions",
        "",
        "未定设定、启动问卷答案、需要人类裁决的问题都先放这里；不能直接进入 `canon.md`。",
        "",
        f"## 启动问卷记录（{now_iso()}）",
        "",
    ]
    for question, _title in QUESTIONS:
        answer = answers.get(question, "").strip()
        lines.extend([f"### {question}", "", answer or "待定。", ""])

    lines.extend(
        [
            "## 后续需确认",
            "",
            "- 最小世界观是否足够开写前三章。",
            "- 主角外在目标、内在需求、恐惧、误信念是否成立。",
            "- 第一卷 mini-outline 是否只保留方向而不过度细纲化。",
            "- 参考作品是否只使用抽象技法。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply startup questionnaire answers to premise/open questions.")
    parser.add_argument("--answers", required=True, help="Markdown file using templates/questionnaire_answers.md headings.")
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()

    path = Path(args.answers)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"ERROR: answers file missing: {path}", file=sys.stderr)
        return 1

    answers = parse_answers(read_text(path))
    missing = [question for question, _title in QUESTIONS if is_blank(answers.get(question, ""))]
    if missing and not args.allow_placeholders:
        print("ERROR: questionnaire has unanswered items:", file=sys.stderr)
        for question in missing:
            print(f"  - {question}", file=sys.stderr)
        return 1

    write_text(ROOT / "outline" / "premise.md", build_premise(answers))
    write_text(ROOT / "bible" / "open_questions.md", build_open_questions(answers))
    print("OK: wrote outline/premise.md and bible/open_questions.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

