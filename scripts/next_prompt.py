from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, gate_decision, read_text


PLACEHOLDERS = ("待定", "待填", "待评", "待生成", "待人类裁决", "TODO", "寰呭畾", "寰呭～")
IDEA_READY_FILES = (
    "original_idea.md",
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "codex_synthesis.md",
)


def has_placeholders(path: Path) -> bool:
    return any(marker in read_text(path) for marker in PLACEHOLDERS)


def ready_idea_labs() -> list[str]:
    root = ROOT / "state" / "idea_lab"
    if not root.exists():
        return []
    labs: list[tuple[float, str]] = []
    for lab in root.iterdir():
        if not lab.is_dir():
            continue
        required = [lab / name for name in IDEA_READY_FILES]
        if all(path.exists() and read_text(path).strip() for path in required):
            labs.append((max(path.stat().st_mtime for path in required), lab.name))
    return [name for _mtime, name in sorted(labs, reverse=True)]


def decision_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return None


def shipped_through(number: int) -> bool:
    return all(decision_for(f"v01_c{idx:03d}") == "Ship" for idx in range(1, number + 1))


def first_unshipped(limit: int = 126) -> str:
    for idx in range(1, limit + 1):
        chapter = f"v01_c{idx:03d}"
        if decision_for(chapter) != "Ship":
            return chapter
    return "v01_c127"


def prompt_for_chapter(chapter: str) -> str:
    volume, chapter_file = chapter_parts(chapter)
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    context = ROOT / "state" / "context_pack" / f"{chapter}.md"
    codex_draft = ROOT / "drafts" / "codex" / f"{chapter}.md"
    official = ROOT / "chapters" / volume / chapter_file
    selection = ROOT / "state" / "selections" / f"{chapter}.json"

    if not brief.exists() or has_placeholders(brief):
        return (
            f"按防漂移流程生成 {chapter} brief：先清点人物状态、道具、技能、能力限制和未解决伏笔，"
            "再写本章功能、主角目标、阻力、主动选择和章末问题；新增道具/技能只放“新增设定”等我确认。"
        )
    if not context.exists():
        return f"确认 brief，开章 {chapter}。"
    if not codex_draft.exists() or not read_text(codex_draft).strip():
        return f"生成 Codex 候选稿，并调用 DeepSeek 生成 {chapter} 外部候选。"
    if not selection.exists():
        return f"比较 {chapter} 的 Codex/DeepSeek 候选，给我推荐选择和理由。"
    if not official.exists() or not read_text(official).strip():
        return f"按已选候选方向，落正式正文 {chapter}；不得直接复制 DeepSeek，必须由 Codex 整合重写。"
    if decision_for(chapter) != "Ship":
        return f"收章 {chapter}。"
    next_number = chapter_number(chapter) + 1
    return f"写下一章，并给我 v01_c{next_number:03d} 的 brief 候选。"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Print the next recommended Codex app prompt.")
    parser.add_argument("--chapter", default=None)
    args = parser.parse_args()

    if shipped_through(125) and gate_decision("e") != "continue":
        prompt = "进入 Gate E，评估是否进入 300 万字模式，并给我 continue / pause / kill / rework 裁决建议。"
    elif shipped_through(25) and gate_decision("c") != "continue":
        prompt = "进入 Gate C，生成 gate_c_assessment，评估阶段高潮、不可逆变化、伏笔负债、设定膨胀和卷内结构。"
    elif shipped_through(10) and gate_decision("b") != "continue":
        prompt = "进入 Gate B，检查主角欲望、主要阻力、管理成本、连续问题和每 3 章爽点复盘。"
    elif shipped_through(3) and gate_decision("a") != "continue":
        prompt = "进入 Gate A 检查，汇总前三章证据，并给我是否继续到第 4 章的裁决建议。"
    else:
        labs = ready_idea_labs()
        unselected = [lab for lab in labs if not (ROOT / "state" / "idea_lab" / lab / "selection.json").exists()]
        if unselected:
            idea = unselected[0]
            prompt = (
                f"总结开书实验 {idea} 的 A/B/C/Mixed 方向，并给我 2-3 个裁决选项；"
                "推荐一个最适合三章试点的方向。"
            )
        elif has_placeholders(ROOT / "outline" / "premise.md"):
            prompt = "我想开一本新书。先判断应该走开书实验还是启动问卷，并给我下一步提示词。"
        else:
            prompt = prompt_for_chapter(args.chapter or first_unshipped())

    print("# Next Prompt")
    print()
    print("```text")
    print(prompt)
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
