from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, gate_decision, now_iso, read_text, truncate, write_blocked_by_locks, write_text
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze, freeze_markdown_path
from element_context import yaml_id_index


def file_section(title: str, path: Path, limit: int) -> str:
    text = read_text(path, "缺失。")
    return f"## {title}\n\n{truncate(text, limit)}\n"


def text_section(title: str, text: str) -> str:
    return f"## {title}\n\n{text.strip() or 'none'}\n"


def id_index_section(title: str, path: Path, root_key: str) -> str:
    ids = yaml_id_index(path, root_key)
    body = "\n".join(f"- {item}" for item in ids) if ids else "none"
    return f"## {title}\n\n{body}\n"


def gate_ready(chapter: str) -> list[str]:
    number = chapter_number(chapter)
    errors: list[str] = []
    if number >= 4 and gate_decision("a") != "continue":
        errors.append("Gate A must be recorded as continue before preparing chapter 4+.")
    if number >= 11 and gate_decision("b") != "continue":
        errors.append("Gate B must be recorded as continue before preparing chapter 11+.")
    if number >= 26 and gate_decision("c") != "continue":
        errors.append("Gate C must be recorded as continue before preparing chapter 26+.")
    if number >= 126 and gate_decision("e") != "continue":
        errors.append("Gate E must be recorded as continue before preparing chapter 126+.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the allowed source pack for Codex/DeepSeek brief candidates.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--limit", type=int, default=7000)
    args = parser.parse_args()

    if write_blocked_by_locks("brief candidate pack build"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for error in gate_ready(args.chapter):
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1

    template = read_text(ROOT / "templates" / "chapter_brief.md")
    parts = [
        f"# Brief Candidate Pack: {args.chapter}",
        "",
        f"generated_at: {now_iso()}",
        "",
        "## 用途边界",
        "",
        "- 本文件只供 Codex 与 DeepSeek 生成当章 brief 候选。",
        "- 候选 brief 不等于正式 brief；必须经人类选择 / 混合 / 修改后由 Codex landing。",
        "- 不能写正文，不能改 canon，不能追加 event ledger。",
        "- brief 候选必须保留防漂移字段：可用道具 IDs、可用技能 IDs、允许新增元素、禁止临场解决。",
        "- 未在本章 brief 中授权的新道具、新技能、新规则，后续不得成为正文破局钥匙。",
        "",
        file_section("开书前核心设定冻结", freeze_markdown_path() or ROOT / "state" / "idea_lab" / "missing.md", 1400),
        file_section("一句话卖点与主角核心", ROOT / "outline" / "premise.md", 900),
        file_section("当前卷目标", ROOT / "outline" / "volume_01.md", 700),
        file_section("主角与主要人物状态", ROOT / "bible" / "characters.yaml", 700),
        file_section("关系变化", ROOT / "bible" / "relationships.yaml", 500),
        file_section("地点状态", ROOT / "bible" / "locations.yaml", 500),
        file_section("已确认 canon", ROOT / "bible" / "canon.md", 700),
        file_section("允许使用设定与规则", ROOT / "bible" / "rules.md", 900),
        file_section("风格和禁用边界", ROOT / "bible" / "style_guide.md", 700),
        file_section("当前道具 / 装备变化", ROOT / "state" / "derived" / "current_objects.yaml", 500),
        file_section("当前技能 / 规则揭示", ROOT / "state" / "derived" / "current_abilities.yaml", 500),
        file_section("未解决伏笔", ROOT / "state" / "derived" / "open_threads.yaml", 700),
        file_section("最近事实事件", ROOT / "state" / "derived" / "latest_events.md", 700),
        id_index_section("全局道具 ID 索引", ROOT / "bible" / "objects.yaml", "objects"),
        id_index_section("全局技能 ID 索引", ROOT / "bible" / "abilities.yaml", "abilities"),
        text_section("必须输出的正式 brief 模板", template),
    ]
    text = "\n".join(parts).strip() + "\n"
    if len(text) > args.limit:
        snapshot = ROOT / "state" / "snapshots" / f"{args.chapter}_oversize_brief_pack.md"
        write_text(snapshot, text)
        print(
            f"ERROR: brief pack exceeds {args.limit} chars; full candidate saved to {snapshot.relative_to(ROOT)}.",
            file=sys.stderr,
        )
        return 1

    out = ROOT / "state" / "context_pack" / f"{args.chapter}_brief.md"
    write_text(out, text)
    print(f"OK: wrote {out.relative_to(ROOT)} ({len(text)} chars, limit {args.limit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
