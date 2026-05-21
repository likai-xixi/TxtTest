from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text
from review_binding import markdown_review_with_hash, sha256


CATEGORIES = (
    "show_dont_tell",
    "rhythm_disorder",
    "emotional_risk",
    "gray_motive",
    "dialogue_agenda",
    "detail_economy",
    "consequence_integrity",
)

EXPOSITION_MARKERS = ("因为", "所以", "意味着", "规则", "机制", "解释", "说明", "事实上", "换句话说", "本质")
SUMMARY_MARKERS = ("真正", "本质", "其实", "说到底", "归根结底", "最怕", "最重要")
ABSTRACT_EMOTION_MARKERS = ("复杂情绪", "无法言说", "微微一怔", "不由得", "有点", "忽然觉得")
GRAY_MARKERS = ("私心", "嫉妒", "迁怒", "撒谎", "隐瞒", "误导", "报复", "贪念", "控制欲", "不体面")
DETAIL_MARKERS = ("一次性胶条", "水印", "编号", "刻度", "读数", "包装袋", "小指", "裂纹")
DIALOGUE_THEME_MARKERS = ("应该", "必须", "原则", "程序", "真相", "边界", "正义", "规则")


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def normalized(text: str) -> str:
    return "".join(text.split())


def marker_density(text: str, markers: tuple[str, ...]) -> float:
    compact = normalized(text)
    if not compact:
        return 0.0
    return round(sum(compact.count(marker) for marker in markers) / len(compact) * 1000, 3)


def sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?]+", text) if item.strip()]


def paragraph_texts(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]


def dialogue_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(("“", "\"", "'", "「", "『", "- ")) or ("“" in line and "”" in line)
    ]


def first_quote(text: str, markers: tuple[str, ...] = ()) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and (not markers or any(marker in stripped for marker in markers)):
            return stripped[:140]
    for sentence in sentences(text):
        if sentence:
            return sentence[:140]
    return ""


def uniform_sentence_run_ratio(text: str) -> float:
    lengths = [len(item) for item in sentences(text)]
    if len(lengths) < 4:
        return 0.0
    runs = 0
    for index in range(len(lengths) - 2):
        window = lengths[index : index + 3]
        if max(window) - min(window) <= 6:
            runs += 1
    return round(runs / max(len(lengths) - 2, 1), 3)


def category_result(
    *,
    name: str,
    blocked: bool,
    severity: str,
    quote: str,
    issue: str,
    action: str,
) -> dict[str, Any]:
    hard_blocked = blocked and severity in {"P0", "P1"}
    return {
        "status": "BLOCKED" if hard_blocked else "CLEAR",
        "severity": severity if blocked else "P3",
        "machine_flagged": blocked,
        "evidence_quotes": [quote] if quote else [],
        "issue": issue,
        "revision_actions": [action],
    }


def evaluate(chapter: str) -> dict[str, Any]:
    path = chapter_path(chapter)
    text = read_text(path)
    if not text.strip():
        raise FileNotFoundError(f"missing non-empty official chapter: {path.relative_to(ROOT)}")
    compact = normalized(text)
    exposition_density = marker_density(text, EXPOSITION_MARKERS)
    summary_density = marker_density(text, SUMMARY_MARKERS)
    abstract_emotion_density = marker_density(text, ABSTRACT_EMOTION_MARKERS)
    gray_density = marker_density(text, GRAY_MARKERS)
    detail_density = marker_density(text, DETAIL_MARKERS)
    dialogue = dialogue_lines(text)
    dialogue_text = "\n".join(dialogue)
    dialogue_theme_density = marker_density(dialogue_text, DIALOGUE_THEME_MARKERS)
    uniform_ratio = uniform_sentence_run_ratio(text)
    paragraphs = paragraph_texts(text)
    short_detail_paragraphs = sum(1 for item in paragraphs if any(marker in item for marker in DETAIL_MARKERS) and len(item) > 90)

    categories = {
        "show_dont_tell": category_result(
            name="show_dont_tell",
            blocked=exposition_density >= 9.0 and summary_density >= 3.0,
            severity="P1",
            quote=first_quote(text, EXPOSITION_MARKERS + SUMMARY_MARKERS),
            issue="解释/总结标记密度过高，可能替读者总结而不是让场景证明。",
            action="删减结论句，改成动作、选择、后果或误解来展示。",
        ),
        "rhythm_disorder": category_result(
            name="rhythm_disorder",
            blocked=uniform_ratio >= 0.55,
            severity="P2",
            quote=first_quote(text),
            issue="句长连续过齐，可能形成机械排比或金句化节奏。",
            action="打散连续短句，加入动作打断、半句、长短混排或口语毛边。",
        ),
        "emotional_risk": category_result(
            name="emotional_risk",
            blocked=abstract_emotion_density >= 5.0 and not any(marker in compact for marker in ("恨", "嫉妒", "恶心", "后悔", "羞耻", "怒")),
            severity="P1",
            quote=first_quote(text, ABSTRACT_EMOTION_MARKERS),
            issue="抽象情绪标记偏多，角色可能停留在安全中间态。",
            action="补足不体面冲动、身体反应、失控边缘或负面情绪后果。",
        ),
        "gray_motive": category_result(
            name="gray_motive",
            blocked=gray_density == 0.0,
            severity="P2",
            quote=first_quote(text),
            issue="未识别到私心、隐瞒、误导、迁怒或其他灰度动机标记。",
            action="确认本章是否需要灰度；若需要，补主角/配角不体面动机及代价。",
        ),
        "dialogue_agenda": category_result(
            name="dialogue_agenda",
            blocked=bool(dialogue) and dialogue_theme_density >= 12.0,
            severity="P1",
            quote=first_quote(dialogue_text or text, DIALOGUE_THEME_MARKERS),
            issue="对白中主题/规则标记偏高，角色可能在替作者讲话。",
            action="给对白加入欲望、遮掩、误解、利益交换或权力变化。",
        ),
        "detail_economy": category_result(
            name="detail_economy",
            blocked=detail_density >= 4.0 and short_detail_paragraphs >= 2,
            severity="P2",
            quote=first_quote(text, DETAIL_MARKERS),
            issue="具体物件/读数类细节密度偏高，可能是无功能仿真纹理。",
            action="为重描细节标明压力、线索、误导、情绪泄漏或后续回收功能。",
        ),
        "consequence_integrity": category_result(
            name="consequence_integrity",
            blocked=gray_density > 0.0 and not any(marker in compact for marker in ("后果", "代价", "追讨", "反噬", "记恨", "受损")),
            severity="P1",
            quote=first_quote(text, GRAY_MARKERS),
            issue="灰度行为出现但没有后果/代价标记。",
            action="补即时收益、他人损失和后续反噬；必要时进入 event ledger。",
        ),
    }
    blockers = [
        f"{name}: {item['issue']}"
        for name, item in categories.items()
        if item["status"] == "BLOCKED" and item["severity"] in {"P0", "P1"}
    ]
    status = "BLOCKED" if blockers else "CLEAR"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)},
        "metrics": {
            "exposition_marker_density": exposition_density,
            "summary_voice_density": summary_density,
            "abstract_emotion_density": abstract_emotion_density,
            "gray_motive_density": gray_density,
            "detail_marker_density": detail_density,
            "dialogue_theme_density": dialogue_theme_density,
            "uniform_sentence_run_ratio": uniform_ratio,
        },
        "categories": categories,
        "blockers": blockers,
        "warnings": [
            f"{name}: {item['issue']}"
            for name, item in categories.items()
            if item.get("machine_flagged") and item["severity"] not in {"P0", "P1"}
        ],
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    chapter = report["chapter"]
    lines = [
        f"# Anti AI Taste Review: {chapter}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report['official_chapter'].get('sha256', '')}",
        "review_sha256:",
        "",
        "## Scope",
        "",
        "检查过度解释、句式过工整、情绪安全区、角色传声筒、细节仿真堆砌、角色灰度不足或灰度无后果。",
        "",
        "## Findings",
        "",
        "| severity | category | evidence_quote | issue | required_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, item in report["categories"].items():
        quote = (item.get("evidence_quotes") or [""])[0]
        action = "; ".join(item.get("revision_actions") or [])
        lines.append(f"| {item.get('severity')} | {name} | {quote} | {item.get('issue')} | {action} |")
    lines.extend(["", "## Evidence Quotes", ""])
    used: list[str] = []
    for item in report["categories"].values():
        for quote in item.get("evidence_quotes") or []:
            if quote and quote not in used:
                used.append(quote)
                lines.append(f"- {quote}")
    lines.extend(
        [
            "",
            "## Category Checks",
            "",
        ]
    )
    for name, item in report["categories"].items():
        lines.append(f"- {name}: {item.get('status')} / {item.get('severity')}")
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a chapter for structured anti-AI taste risks.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args.chapter)
    except Exception as exc:
        print(f"# Anti AI Taste: {args.chapter}")
        print("status: NOT_READY")
        print(f"- {exc}")
        return 1
    if not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "ai_taste.json", report)
        write_text(out_dir / "ai_taste.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Anti AI Taste: {args.chapter}")
        print(f"status: {report['status']}")
        for item in report.get("blockers", []):
            print(f"- {item}")
    return 0 if report["status"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
