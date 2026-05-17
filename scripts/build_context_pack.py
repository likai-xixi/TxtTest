from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_text, truncate, write_text


def file_section(title: str, path: Path, limit: int) -> str:
    text = read_text(path, "缺失。")
    return f"## {title}\n\n{truncate(text, limit)}\n"


def context_limit_for(chapter: str) -> int:
    number = chapter_number(chapter)
    if number > 50:
        return 8000
    if number > 10:
        return 5000
    return 3000


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the single allowed context pack for a chapter.")
    parser.add_argument("--chapter", required=True, help="Chapter id like v01_c001.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--allow-truncated", action="store_true")
    args = parser.parse_args()

    chapter = args.chapter
    chapter_parts(chapter)
    limit = args.limit or context_limit_for(chapter)

    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    if not brief_path.exists():
        print(f"ERROR: missing chapter brief: {brief_path.relative_to(ROOT)}")
        return 1

    parts = [
        f"# Context Pack: {chapter}",
        "",
        f"generated_at: {now_iso()}",
        "",
        "## 写作硬边界",
        "",
        "- 正文只能依据本 context pack 和当章 brief。",
        "- 上下文不足时列缺口，不自行补设定。",
        "- context pack 与 brief 冲突时停止并请求人类裁决。",
        "- DeepSeek 输出只是候选或审查建议，不是 canon、正文或状态事实。",
        "",
        file_section("一句话卖点与主角核心", ROOT / "outline" / "premise.md", 900),
        file_section("当前卷目标", ROOT / "outline" / "volume_01.md", 700),
        file_section("主角与主要人物状态", ROOT / "bible" / "characters.yaml", 700),
        file_section("关系变化", ROOT / "bible" / "relationships.yaml", 500),
        file_section("地点 / 物品状态", ROOT / "bible" / "locations.yaml", 500),
        file_section("道具 / 装备台账", ROOT / "bible" / "objects.yaml", 500),
        file_section("技能 / 能力台账", ROOT / "bible" / "abilities.yaml", 500),
        file_section("当前道具 / 装备变化", ROOT / "state" / "derived" / "current_objects.yaml", 500),
        file_section("当前技能 / 规则揭示", ROOT / "state" / "derived" / "current_abilities.yaml", 500),
        file_section("未解决伏笔", ROOT / "state" / "derived" / "open_threads.yaml", 700),
        file_section("最近事实事件", ROOT / "state" / "derived" / "latest_events.md", 700),
        file_section("最近规则揭示", ROOT / "state" / "derived" / "rule_reveals.md", 500),
        file_section("本章 brief", brief_path, 1200),
        file_section("禁止改动 canon", ROOT / "bible" / "canon.md", 700),
        file_section("允许使用设定与规则", ROOT / "bible" / "rules.md", 900),
        file_section("禁止新增设定 / 风格边界", ROOT / "bible" / "style_guide.md", 700),
    ]
    text = "\n".join(parts).strip() + "\n"

    if len(text) > limit:
        snapshot = ROOT / "state" / "snapshots" / f"{chapter}_oversize_context.md"
        write_text(snapshot, text)
        if not args.allow_truncated:
            print(
                f"ERROR: context pack exceeds {limit} chars; full candidate saved to {snapshot.relative_to(ROOT)}. "
                "Tighten source files or rerun with --allow-truncated for diagnostics."
            )
            return 1
        text = (
            "\n".join(parts[:10]).strip()
            + f"\n\n## Snapshot\n\nContext exceeded {limit} chars. Full candidate pack saved to `{snapshot.relative_to(ROOT)}`. Tighten source files before drafting.\n"
        )
        if len(text) > limit:
            text = text[: limit - 120].rstrip() + "\n\n[context truncated; rebuild required]\n"

    out = ROOT / "state" / "context_pack" / f"{chapter}.md"
    write_text(out, text)
    print(f"OK: wrote {out.relative_to(ROOT)} ({len(text)} chars, limit {limit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
