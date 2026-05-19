from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_text, truncate, write_blocked_by_locks, write_text
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze, freeze_markdown_path
from element_context import yaml_id_index
from gate_policy import gate_errors_for_chapter


def file_section(title: str, path: Path, limit: int) -> str:
    text = read_text(path, "缺失。")
    return f"## {title}\n\n{truncate(text, limit)}\n"


def text_section(title: str, text: str) -> str:
    return f"## {title}\n\n{text.strip() or 'none'}\n"


def id_index_section(title: str, path: Path, root_key: str) -> str:
    ids = yaml_id_index(path, root_key)
    body = "\n".join(f"- {item}" for item in ids) if ids else "none"
    return f"## {title}\n\n{body}\n"


def previous_chapter_id(chapter: str) -> str | None:
    number = chapter_number(chapter)
    if number <= 1:
        return None
    return f"{chapter[:3]}_c{number - 1:03d}"


def previous_anchor_section(chapter: str) -> tuple[str, list[str]]:
    previous = previous_chapter_id(chapter)
    if previous is None:
        return "## 上一章章末锚点\n\n开篇章，无上章。\n", []
    path = ROOT / "state" / "derived" / "chapter_anchors" / f"{previous}.json"
    if not path.exists():
        return "", [f"missing previous chapter anchor: {path.relative_to(ROOT)}; record a chapter_anchor event for {previous} before preparing {chapter}"]
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return "", [f"invalid previous chapter anchor JSON: {path.relative_to(ROOT)}: {exc}"]
    body = "\n".join(
        [
            f"- source_event_id: {data.get('source_event_id', 'unknown')}",
            f"- 时间：{data.get('end_time', '')}",
            f"- 地点：{data.get('end_location', '')}",
            "- 在场人物：" + "、".join(str(item) for item in data.get("present_characters", [])),
            f"- 主角状态：{data.get('protagonist_state', '')}",
            "- 携带物 / 证据：" + "、".join(str(item) for item in data.get("carried_items", [])),
            f"- 未完成动作：{data.get('unfinished_action', '')}",
            f"- 下一章必须承接：{data.get('next_required_continuity', '')}",
        ]
    )
    return f"## 上一章章末锚点\n\n{body}\n", []


def gate_ready(chapter: str) -> list[str]:
    return gate_errors_for_chapter(chapter, "preparing")


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
    anchor_text, anchor_errors = previous_anchor_section(args.chapter)
    if anchor_errors:
        for error in anchor_errors:
            print(f"ERROR: {error}", file=sys.stderr)
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
        "- brief 候选必须保留连续性字段：上章章末锚点、本章开场落点、场景承接说明。",
        "- brief 候选必须保留进展治理字段：本章进展契约、本章代价与后果契约、本章解决边界。",
        "- 每章必须留下结束状态变化和最低落账事件；低牵引章要说明低牵引功能，高推进章要写代价、后果承接义务、消化窗口和冷却范围。",
        "- 如果本章开场时间、地点或状态不同于上一章章末锚点，必须写清过桥原因和动作。",
        "- 未在本章 brief 中授权的新道具、新技能、新规则，后续不得成为正文破局钥匙。",
        "",
        anchor_text,
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
        file_section("后果承接债务", ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json", 700),
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
