from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256


OPENING_PATTERNS = {
    "meeting": ("meeting", "briefing", "office", "conference", "会议"),
    "pursuit": ("chase", "pursuit", "run", "追", "逃"),
    "arrival": ("arrive", "station", "door", "进入", "到达"),
    "aftermath": ("after", "wake", "morning", "醒", " aftermath", "事后"),
    "dialogue": ("said", "asked", "dialogue", "问", "说"),
}
OBSTACLE_PATTERNS = {
    "bureaucracy": ("form", "record", "archive", "approval", "流程", "档案", "回函"),
    "combat": ("fight", "attack", "blood", "打", "杀", "伤"),
    "investigation": ("clue", "case", "trace", "调查", "线索", "证据"),
    "negotiation": ("bargain", "deal", "promise", "谈", "交易"),
    "revelation": ("rule", "secret", "truth", "规则", "秘密", "真相"),
}
RESOLUTION_PATTERNS = {
    "new_clue": ("clue", "signal", "发现", "线索"),
    "procedure": ("record", "file", "submit", "归档", "记录", "提交"),
    "force": ("fight", "break", "attack", "打", "破"),
    "bargain": ("deal", "promise", "exchange", "交易", "承诺"),
    "delay": ("wait", "pending", "later", "待", "搁置"),
}
HOOK_PATTERNS = {
    "new_threat": ("threat", "enemy", "danger", "威胁", "敌", "危险"),
    "new_rule": ("rule", "law", "forbidden", "规则", "禁"),
    "relationship_shift": ("trust", "betray", "relationship", "信任", "背叛", "关系"),
    "mystery": ("why", "unknown", "signal", "为何", "未知", "信号"),
    "cost": ("cost", "price", "debt", "代价", "债"),
}
PROTAGONIST_POSITION_PATTERNS = {
    "active": ("选择", "决定", "拒绝", "反制", "承担", "交换", "主动", "拆穿", "逼问", "保护"),
    "reactive": ("被迫", "只好", "不得不", "被带", "被问", "被要求", "等待", "旁观"),
}
PROTAGONIST_SOLUTION_PATTERNS = {
    "active_choice": ("选择", "决定", "拒绝", "反制", "承担", "交换", "拆穿"),
    "procedure": ("提交", "归档", "申请", "记录", "审批", "流程"),
    "new_clue": ("发现", "线索", "信号", "证据"),
    "force": ("打", "破", "杀", "抢", "冲"),
    "delay": ("等待", "搁置", "稍后", "未决"),
}
SIDE_CHARACTER_PATTERNS = {
    "messenger": ("通知", "告诉", "转述", "汇报", "递给", "发送"),
    "obstacle": ("阻止", "威胁", "刁难", "拒绝", "审问"),
    "ally": ("帮助", "掩护", "提醒", "协助"),
    "mirror": ("看着", "沉默", "旁观", "反问"),
}
EXPLANATION_MARKERS = ("解释", "说明", "意味着", "也就是说", "规则是", "原因是", "总结", "因此")
SCENE_MARKERS = ("门", "手", "眼", "血", "汗", "灯", "声音", "脚步", "雨", "桌", "窗")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def pick(text: str, patterns: dict[str, tuple[str, ...]], fallback: str) -> str:
    lowered = text.lower()
    scores = {
        name: sum(1 for marker in markers if marker.lower() in lowered)
        for name, markers in patterns.items()
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score > 0 else fallback


def chapter_shape(chapter: str) -> dict[str, str]:
    official = official_path(chapter)
    text = read_text(official)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    opening_text = "\n".join(lines[:8])
    ending_text = "\n".join(lines[-8:])
    explanation_hits = sum(text.count(marker) for marker in EXPLANATION_MARKERS)
    scene_hits = sum(text.count(marker) for marker in SCENE_MARKERS)
    exposition_load = "explanation_only" if explanation_hits >= 4 and scene_hits < 4 else "mixed" if explanation_hits >= 2 else "scene_first"
    protagonist_position = pick(text, PROTAGONIST_POSITION_PATTERNS, "unclear")
    if protagonist_position == "reactive" and any(marker in text for marker in PROTAGONIST_POSITION_PATTERNS["active"]):
        protagonist_position = "mixed"
    return {
        "opening": pick(opening_text, OPENING_PATTERNS, "unclear"),
        "obstacle": pick(text, OBSTACLE_PATTERNS, "unclear"),
        "resolution": pick(ending_text or text, RESOLUTION_PATTERNS, "unclear"),
        "hook": pick(ending_text or text, HOOK_PATTERNS, "unclear"),
        "protagonist_position": protagonist_position,
        "protagonist_solution": pick(ending_text or text, PROTAGONIST_SOLUTION_PATTERNS, "unclear"),
        "side_character_function": pick(text, SIDE_CHARACTER_PATTERNS, "unclear"),
        "exposition_load": exposition_load,
    }


def shape_key(shape: dict[str, str]) -> str:
    return "|".join(
        shape.get(key, "unclear")
        for key in (
            "opening",
            "obstacle",
            "resolution",
            "hook",
            "protagonist_position",
            "protagonist_solution",
            "side_character_function",
            "exposition_load",
        )
    )


def shape_keys_match(current_key: str, previous_key: str) -> bool:
    current_parts = current_key.split("|") if current_key else []
    previous_parts = previous_key.split("|") if previous_key else []
    if not current_parts or not previous_parts:
        return False
    if current_parts == previous_parts:
        return True
    shared = min(len(current_parts), len(previous_parts))
    return shared >= 4 and current_parts[:shared] == previous_parts[:shared]


def load_shape_ledger() -> dict[str, Any]:
    return read_json(ROOT / "state" / "derived" / "chapter_shapes.json", {"schema_version": 1, "generated_at": "", "chapters": {}})


def prior_repetition_count(chapter: str, key: str, ledger: dict[str, Any]) -> int:
    count = 0
    for previous, value in sorted((ledger.get("chapters") or {}).items(), reverse=True):
        if previous >= chapter:
            continue
        if not isinstance(value, dict):
            continue
        if shape_keys_match(key, str(value.get("shape_key", ""))):
            count += 1
        else:
            break
    return count


def prior_component_repetition_count(chapter: str, component: str, value: str, ledger: dict[str, Any]) -> int:
    count = 0
    if not value or value == "unclear":
        return 0
    for previous, item in sorted((ledger.get("chapters") or {}).items(), reverse=True):
        if previous >= chapter:
            continue
        if not isinstance(item, dict):
            continue
        shape = item.get("shape") if isinstance(item.get("shape"), dict) else {}
        if shape.get(component) == value:
            count += 1
        else:
            break
    return count


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_path(chapter)
    if not official.exists() or not read_text(official).strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": rel(official), "sha256": ""},
            "shape": {},
            "shape_key": "",
            "repeat_count": 0,
            "blockers": [f"missing official chapter: {rel(official)}"],
            "warnings": [],
        }
    number = chapter_number(chapter)
    shape = chapter_shape(chapter)
    key = shape_key(shape)
    ledger = load_shape_ledger()
    repeat_count = prior_repetition_count(chapter, key, ledger)
    component_repeats = {
        component: prior_component_repetition_count(chapter, component, value, ledger)
        for component, value in shape.items()
    }
    warnings: list[str] = []
    blockers: list[str] = []
    if repeat_count >= 2:
        message = f"chapter shape repeats the previous {repeat_count} shipped/checked chapters: {key}"
        if number >= 6:
            blockers.append(message)
        else:
            warnings.append(message)
    for component, count in component_repeats.items():
        if count >= 2:
            message = f"chapter {component} repeats the previous {count} checked chapters: {shape.get(component)}"
            if number >= 6:
                blockers.append(message)
            else:
                warnings.append(message)
    if (
        shape.get("obstacle") == "investigation"
        and shape.get("resolution") in {"delay", "procedure", "new_clue"}
        and shape.get("hook") in {"mystery", "new_threat", "new_rule"}
        and number >= 6
    ):
        warnings.append("investigation/procedure/new-clue shape detected; ensure it does not repeat as a low-drama loop.")
    if number >= 6 and shape.get("protagonist_position") == "reactive":
        blockers.append("chapter 6+ has reactive protagonist shape; protagonist must actively alter the situation")
    if number >= 6 and shape.get("exposition_load") == "explanation_only":
        blockers.append("chapter 6+ is explanation-heavy without enough scene anchors")
    if number >= 6 and shape.get("side_character_function") == "messenger":
        warnings.append("side character is primarily a messenger; avoid tool-like support cast")
    if number <= 3 and not blockers:
        warnings.append("warmup chapter: shape repetition is advisory only.")
    status = "BLOCKED" if blockers else "WARNING" if warnings else "READY"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": {"path": rel(official), "sha256": sha256(official)},
        "shape": shape,
        "shape_key": key,
        "repeat_count": repeat_count,
        "component_repeats": component_repeats,
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Chapter Shape: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        f"generated_at: {report['generated_at']}",
        f"shape_key: {report.get('shape_key', '')}",
        f"repeat_count: {report.get('repeat_count', 0)}",
        "",
        "## Shape",
        "",
    ]
    for key, value in (report.get("shape") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Component Repeats", ""])
    for key, value in (report.get("component_repeats") or {}).items():
        lines.append(f"- {key}: {value}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {item}" for item in report.get(key) or ["none"])
    return "\n".join(lines).rstrip() + "\n"


def update_ledger(report: dict[str, Any]) -> None:
    path = ROOT / "state" / "derived" / "chapter_shapes.json"
    ledger = load_shape_ledger()
    if not isinstance(ledger, dict):
        ledger = {"schema_version": 1, "chapters": {}}
    chapters = ledger.setdefault("chapters", {})
    if isinstance(chapters, dict):
        chapters[report["chapter"]] = {
            "status": report["status"],
            "shape": report.get("shape", {}),
            "shape_key": report.get("shape_key", ""),
            "component_repeats": report.get("component_repeats", {}),
            "official_chapter": report.get("official_chapter", {}),
            "updated_at": now_iso(),
        }
    ledger["generated_at"] = now_iso()
    write_json(path, ledger)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect repeated chapter shapes across the long-form workflow.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "chapter_shape.json", report)
        write_text(out_dir / "chapter_shape.md", render_markdown(report))
        update_ledger(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] in {"READY", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
