from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import ROOT, now_iso, read_text, write_text


IDEA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
CHOICES = ["A", "B", "C", "Mixed"]
REQUIRED_INPUTS = [
    "original_idea.md",
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "codex_synthesis.md",
]
PLACEHOLDER_MARKERS = ("待定", "待填", "待评", "待生成", "TODO", "{idea_id}")
AGENT_OUTPUTS = [
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "codex_synthesis.md",
]
REQUIRED_DIRECTION_FIELDS = [
    "一句话卖点",
    "主角欲望",
    "核心冲突",
    "世界异常",
    "前三章验证点",
    "最大风险",
    "适合继续的信号",
    "不适合继续的信号",
]


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def has_placeholder(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return ""


def direction_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s*Direction\s+([ABC])\b.*$", text, flags=re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def validate_codex_synthesis(text: str) -> list[str]:
    errors: list[str] = []
    sections = direction_sections(text)
    for direction in ("A", "B", "C"):
        section = sections.get(direction)
        if section is None:
            errors.append(f"codex_synthesis.md missing Direction {direction}")
            continue
        for field in REQUIRED_DIRECTION_FIELDS:
            if field not in section:
                errors.append(f"codex_synthesis.md Direction {direction} missing field {field}")
    return errors


def validate_output_freshness(lab: Path) -> list[str]:
    input_mtime = max((lab / "original_idea.md").stat().st_mtime, (lab / "deepseek_idea.md").stat().st_mtime)
    errors: list[str] = []
    for name in AGENT_OUTPUTS:
        path = lab / name
        if path.stat().st_mtime + 0.001 < input_mtime:
            errors.append(f"idea-lab input {path.relative_to(ROOT)} is older than idea inputs")
    return errors


def validate_ready_contents(idea_id: str, lab: Path, contents: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for name in AGENT_OUTPUTS:
        heading = first_heading(contents[name])
        if idea_id not in heading:
            errors.append(f"idea-lab input {lab.joinpath(name).relative_to(ROOT)} heading must include {idea_id}")
    errors.extend(validate_codex_synthesis(contents["codex_synthesis.md"]))
    errors.extend(validate_output_freshness(lab))
    return errors


def require_ready_lab(idea_id: str) -> tuple[Path, dict[str, str]]:
    lab = ROOT / "state" / "idea_lab" / idea_id
    if not lab.exists():
        raise FileNotFoundError(f"missing idea lab: {lab.relative_to(ROOT)}")
    contents: dict[str, str] = {}
    for name in REQUIRED_INPUTS:
        path = lab / name
        if not path.exists():
            raise FileNotFoundError(f"missing idea-lab input: {path.relative_to(ROOT)}")
        text = read_text(path)
        if not text.strip():
            raise ValueError(f"idea-lab input is empty: {path.relative_to(ROOT)}")
        if name != "original_idea.md" and has_placeholder(text):
            raise ValueError(f"idea-lab input still has placeholders: {path.relative_to(ROOT)}")
        contents[name] = text
    errors = validate_ready_contents(idea_id, lab, contents)
    if errors:
        raise ValueError("; ".join(errors))
    return lab, contents


def build_premise(idea_id: str, args: argparse.Namespace, contents: dict[str, str]) -> str:
    return f"""# Premise

idea_lab_id: {idea_id}
selected_direction: {args.choice}
selected_at: {now_iso()}

## 一句话卖点

待人类确认：根据 `state/idea_lab/{idea_id}/codex_synthesis.md` 中的 {args.choice} 方向整理。

## 主角

待人类确认。

## 主角想要什么

待人类确认。

## 世界最大异常

待人类确认。

## 核心冲突

待人类确认。

## 前三章验证目标

待人类确认。

## 选择理由

{args.reason or "待人类补充。"}

## Mixed Strategy

{args.mixed_strategy or "无。"}

## Codex Synthesis 摘要

{contents["codex_synthesis.md"].strip()}
"""


def build_open_questions(idea_id: str, args: argparse.Namespace, contents: dict[str, str]) -> str:
    return f"""# Open Questions

idea_lab_id: {idea_id}
selected_direction: {args.choice}

本文件保存开书实验室产物和待裁决问题。以下内容不得直接视为 canon。

## 原始想法

{contents["original_idea.md"].strip()}

## DeepSeek 外部发散

{contents["deepseek_idea.md"].strip()}

## 多 Agent 审查

### Product Founder

{contents["product_founder_review.md"].strip()}

### Technical Lead

{contents["technical_lead_review.md"].strip()}

### QA Release

{contents["qa_release_review.md"].strip()}

## 人类总编选择

- choice: {args.choice}
- reason: {args.reason or "待人类补充。"}
- mixed_strategy: {args.mixed_strategy or "无。"}
- notes: {args.notes or "无。"}

## 后续必须确认

- 主角欲望是否足够强。
- 世界异常是否只保留前三章够用部分。
- 第一章开篇吸引点是否明确。
- 哪些事实可以进入 canon，必须等正文出现后再确认。
"""


def build_gate_a(idea_id: str, args: argparse.Namespace) -> str:
    return f"""# Gate A: 3 Chapters

idea_lab_id: {idea_id}
selected_direction: {args.choice}

Gate A 只判断是否继续到第 4 章，不判断 300 万字可行性。

## 必须回答

- 是否愿意写第 4 章？
- 流程是否让写作更轻？
- 主角目标是否成立？
- 核心卖点是否一句话说清？
- 3 章里是否至少 2 章让人想看下一章？
- 世界观是否展示压力而不是百科？
- 是否出现设定膨胀或漂移？
- Codex / DeepSeek 哪个更适合主写？

## 继续信号

待人类根据前三章和读者测试确认。

## 停止或重做信号

待人类根据前三章和读者测试确认。
"""


def build_c001_brief(idea_id: str, args: argparse.Namespace) -> str:
    return f"""# v01_c001 Brief

idea_lab_id: {idea_id}
selected_direction: {args.choice}

## 本章功能

待定：请人类总编确认第一章在三章试点中的功能。

## 开篇吸引点

待定：从开书实验方向中选择一个可立即进入冲突的场面。

## 主角目标

待定：必须是本章内可行动、可失败的目标。

## 主要阻力

待定。

## 主角主动选择

待定：本章必须有主角主动选择，不能只被事件推着走。

## 本章推进

待定。

## 信息增量

待定：只展示前三章够用的信息。

## 章末问题

待定。

## 本章使用设定

待定。

## 本章可用人物状态

待定。

## 本章可用道具 / 装备

待定。

## 本章可用技能 / 能力

待定。

## 能力限制 / 代价

待定。

## 未解决伏笔

待定。

## 新增设定

待定：新增设定必须先停留在 open_questions，不能直接进 canon。

## 伏笔：新开 / 推进 / 回收

待定。

## 本章禁止新增

待定。

## 本章禁止解决

待定。

## 禁止新增 / 禁止解决 / 禁止模仿

待定：禁止把 DeepSeek 或任何参考作品内容直接换皮进正文。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Record human-selected idea direction and create pilot assets.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--reason", default="")
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    try:
        lab, contents = require_ready_lab(args.id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.choice == "Mixed" and not args.mixed_strategy.strip():
        print("ERROR: Mixed choice requires --mixed-strategy.", file=sys.stderr)
        return 1

    record = {
        "idea_id": args.id,
        "selected_at": now_iso(),
        "choice": args.choice,
        "reason": args.reason,
        "mixed_strategy": args.mixed_strategy,
        "notes": args.notes,
        "verified_by": "human",
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }
    write_text(lab / "selection.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    write_text(
        lab / "selection.md",
        "\n".join(
            [
                f"# Idea Selection: {args.id}",
                "",
                f"choice: {args.choice}",
                f"reason: {args.reason or '待人类补充。'}",
                f"mixed_strategy: {args.mixed_strategy or '无。'}",
                f"notes: {args.notes or '无。'}",
                "verified_by: human",
                "",
            ]
        ),
    )
    write_text(ROOT / "outline" / "premise.md", build_premise(args.id, args, contents))
    write_text(ROOT / "bible" / "open_questions.md", build_open_questions(args.id, args, contents))
    write_text(ROOT / "outline" / "gate_a_3_chapters.md", build_gate_a(args.id, args))
    write_text(ROOT / "outline" / "chapter_briefs" / "v01_c001.md", build_c001_brief(args.id, args))
    print(f"OK: recorded idea selection {args.id} -> {args.choice}")
    print("next: human confirms or edits outline/chapter_briefs/v01_c001.md, then run `开章 v01_c001`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
