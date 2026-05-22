from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text
from review_binding import markdown_review_with_hash, sha256


FUNCTION_MARKERS = {
    "information_progress": ("线索", "证据", "告诉", "发现", "知道", "看见"),
    "desire_exposure": ("我要", "我想", "不想", "给我", "别", "凭什么"),
    "conflict_pressure": ("不行", "不能", "必须", "你敢", "否则", "现在"),
    "concealment": ("没什么", "不知道", "以后再说", "别问", "算了", "不是"),
    "relationship_probe": ("你信", "你怕", "你觉得", "你到底", "我们"),
    "theme_statement": ("原则", "正义", "真相", "规则", "程序", "意义", "边界", "流程", "报告", "档案"),
}
PRIVATE_AGENDA_FUNCTIONS = {"desire_exposure", "conflict_pressure", "concealment", "relationship_probe"}
EXPLANATION_ONLY_FUNCTIONS = {"pure_theme_statement", "rule_delivery_only"}
VALID_DIALOGUE_FUNCTIONS = {
    "information_progress",
    "desire_exposure",
    "conflict_pressure",
    "concealment",
    "relationship_probe",
    "theme_with_agenda",
}
FUNCTION_MARKERS["information_progress"] += ("clue", "evidence", "tell", "find", "know", "see")
FUNCTION_MARKERS["desire_exposure"] += ("want", "need", "refuse")
FUNCTION_MARKERS["conflict_pressure"] += ("cannot", "or else", "now")
FUNCTION_MARKERS["concealment"] += ("nothing", "do not know", "later", "do not ask")
FUNCTION_MARKERS["relationship_probe"] += ("trust", "we", "us")
FUNCTION_MARKERS["theme_statement"] += (
    "principle",
    "justice",
    "truth",
    "rule",
    "procedure",
    "meaning",
    "boundary",
    "process",
    "report",
    "file",
)
RULE_DELIVERY_MARKERS = ("规则", "程序", "流程", "档案", "报告", "线索", "证据")
RULE_DELIVERY_MARKERS = RULE_DELIVERY_MARKERS + ("rule", "procedure", "process", "file", "report", "clue", "evidence")


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def dialogue_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("“", "‘", '"', "'", "「", "『", "- ")) or ("“" in stripped and "”" in stripped):
            lines.append(stripped)
    return lines


def first_narrative_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:140]
    return ""


def classify(line: str) -> str:
    scores = {
        name: sum(line.count(marker) for marker in markers)
        for name, markers in FUNCTION_MARKERS.items()
    }
    best = max(scores, key=lambda key: scores[key])
    if scores[best] == 0:
        return "character_texture"
    if any(marker in line for marker in RULE_DELIVERY_MARKERS) and not any(
        scores.get(name, 0) for name in PRIVATE_AGENDA_FUNCTIONS
    ):
        return "rule_delivery_only"
    if best == "theme_statement":
        other_score = sum(value for key, value in scores.items() if key != "theme_statement")
        if other_score > 0:
            return "theme_with_agenda"
        return "pure_theme_statement"
    return best


def sample_for_line(line: str) -> dict[str, Any]:
    function = classify(line)
    blocked = function in EXPLANATION_ONLY_FUNCTIONS or function not in VALID_DIALOGUE_FUNCTIONS
    return {
        "evidence_quote": line[:140],
        "speaker": "unknown",
        "function": function,
        "character_goal": "advance pressure, desire, concealment, relationship, or information rather than only state theme",
        "subtext_or_hidden_agenda": "reviewer must confirm the line has subtext or a concrete agenda",
        "consequence_or_power_shift": "reviewer must confirm what changes after this line",
        "status": "BLOCKED" if blocked else "CLEAR",
    }


def max_explanation_run(functions: list[str]) -> int:
    longest = 0
    current = 0
    for function in functions:
        if function in EXPLANATION_ONLY_FUNCTIONS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def evaluate(chapter: str) -> dict[str, Any]:
    path = chapter_path(chapter)
    text = read_text(path)
    if not text.strip():
        raise FileNotFoundError(f"missing non-empty official chapter: {path.relative_to(ROOT)}")
    lines = dialogue_lines(text)
    if not lines:
        samples = [
            {
                "evidence_quote": first_narrative_line(text),
                "speaker": "narration",
                "function": "no_dialogue_scene",
                "character_goal": "chapter has no dialogue sample; reviewer must confirm this is intentional",
                "subtext_or_hidden_agenda": "n/a",
                "consequence_or_power_shift": "n/a",
                "status": "CLEAR",
            }
        ]
    else:
        samples = [sample_for_line(line) for line in lines[:20]]
    all_functions = [classify(line) for line in lines]
    pure_count = sum(1 for function in all_functions if function in EXPLANATION_ONLY_FUNCTIONS)
    invalid_count = sum(1 for function in all_functions if function not in VALID_DIALOGUE_FUNCTIONS)
    explanation_run = max_explanation_run(all_functions)
    ratio = round(pure_count / max(len(all_functions), 1), 3)
    blockers = []
    if pure_count and ratio >= 0.35:
        blockers.append("dialogue has too many pure theme/rule-delivery statements without visible character agenda")
    if explanation_run >= 2:
        blockers.append("dialogue has consecutive explanation-only lines without conflict, concealment, relationship movement, or power shift")
    if invalid_count:
        blockers.append("dialogue contains lines without one of the required functions: conflict, concealment, relationship, desire, pressure, or information turn")
    if any(item.get("status") == "BLOCKED" for item in samples) and (ratio >= 0.35 or explanation_run >= 2 or invalid_count):
        status = "BLOCKED"
    else:
        status = "CLEAR"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)},
        "summary": {
            "dialogue_line_count": len(lines),
            "sample_count": len(samples),
            "pure_theme_statement_count": pure_count,
            "pure_theme_statement_ratio": ratio,
            "invalid_function_count": invalid_count,
            "max_explanation_only_run": explanation_run,
        },
        "samples": samples,
        "blockers": blockers,
        "warnings": [] if lines else ["no dialogue lines detected; reviewer should confirm this is intentional"],
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Dialogue Function Review: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report['official_chapter'].get('sha256', '')}",
        "review_sha256:",
        "",
        "## Scope",
        "",
        "抽查关键对白是否有信息推进、欲望暴露、冲突施压、遮掩、关系试探或权力变化；阻断纯主题陈述过高的章节。",
        "",
        "## Samples",
        "",
        "| status | function | evidence_quote | character_goal | subtext_or_hidden_agenda | consequence_or_power_shift |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["samples"]:
        lines.append(
            f"| {item.get('status')} | {item.get('function')} | {item.get('evidence_quote')} | "
            f"{item.get('character_goal')} | {item.get('subtext_or_hidden_agenda')} | {item.get('consequence_or_power_shift')} |"
        )
    lines.extend(["", "## Evidence Quotes", ""])
    used: list[str] = []
    for item in report["samples"]:
        quote = str(item.get("evidence_quote", "")).strip()
        if quote and quote not in used:
            used.append(quote)
            lines.append(f"- {quote}")
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check dialogue function and theme-speech risk.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args.chapter)
    except Exception as exc:
        print(f"# Dialogue Function: {args.chapter}")
        print("status: NOT_READY")
        print(f"- {exc}")
        return 1
    if not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "dialogue_function.json", report)
        write_text(out_dir / "dialogue_function.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Dialogue Function: {args.chapter}")
        print(f"status: {report['status']}")
        for item in report.get("blockers", []):
            print(f"- {item}")
    return 0 if report["status"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
