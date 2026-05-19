from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, read_text
from workflow_errors import issue


SIGNALS = {
    "agency": ("决定", "选择", "主动", "拒绝", "调查", "进入", "追问", "承担", "反击", "承认"),
    "progress": ("发现", "揭示", "推进", "代价", "后果", "线索", "兑现", "解决", "打开", "变化"),
    "setting_risk": ("新规则", "新能力", "突然", "凭空", "神器", "万能", "核心设定", "L4", "规则改写"),
    "ai_taste": ("仿佛", "某种", "命运", "交织", "无法言说", "复杂情绪", "微微一怔", "不由得", "TODO", "待定"),
    "event_evidence": ("事件", "落账", "chapter_anchor", "锚点", "改变", "决定", "承诺", "代价", "后果"),
    "breaker_risk": ("破局", "突然获得", "新道具", "新技能", "无代价", "直接解决", "临场解决", "万能"),
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def candidate_paths(chapter: str, brief: bool) -> dict[str, Path]:
    suffix = f"{chapter}_brief.md" if brief else f"{chapter}.md"
    return {
        "Codex": ROOT / "drafts" / "codex" / suffix,
        "DeepSeek": ROOT / "drafts" / "deepseek" / suffix,
    }


def count_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(text.count(term) for term in terms)


def sentence_count(text: str) -> int:
    return max(1, len([item for item in re.split(r"[。！？!?]\s*", text) if item.strip()]))


def analyze(path: Path) -> dict[str, Any]:
    if not path.exists() or not read_text(path).strip():
        return {
            "path": rel(path),
            "exists": path.exists(),
            "nonempty": False,
            "issues": [issue("MISSING", "candidate file is missing or empty", rel(path))],
            "score": 0,
        }
    text = read_text(path)
    sentences = sentence_count(text)
    agency = count_terms(text, SIGNALS["agency"])
    progress = count_terms(text, SIGNALS["progress"])
    setting_risk = count_terms(text, SIGNALS["setting_risk"])
    ai_taste = count_terms(text, SIGNALS["ai_taste"])
    event_evidence = count_terms(text, SIGNALS["event_evidence"])
    breaker_risk = count_terms(text, SIGNALS["breaker_risk"])
    score = agency * 3 + progress * 3 + event_evidence * 2 - setting_risk * 3 - ai_taste - breaker_risk * 4
    return {
        "path": rel(path),
        "exists": True,
        "nonempty": True,
        "chars": len(text),
        "sentences": sentences,
        "protagonist_agency": agency,
        "mainline_progress": progress,
        "setting_new_risk": setting_risk,
        "ai_taste_risk": ai_taste,
        "ledger_event_evidence": event_evidence,
        "unauthorized_breaker_risk": breaker_risk,
        "score": score,
        "issues": [],
    }


def compare(chapter: str, brief: bool = False) -> dict[str, Any]:
    chapter_parts(chapter)
    paths = candidate_paths(chapter, brief)
    candidates = {name: analyze(path) for name, path in paths.items()}
    usable = {name: item for name, item in candidates.items() if item.get("nonempty")}
    if not usable:
        recommendation = "No usable candidate"
        reason = "Both candidate files are missing or empty."
    else:
        recommendation = max(usable, key=lambda name: int(usable[name].get("score", 0)))
        reason = f"{recommendation} has the strongest heuristic balance of agency, progress, and risk."
    return {
        "chapter": chapter,
        "mode": "brief" if brief else "chapter",
        "status": "READY" if usable else "MISSING",
        "candidates": candidates,
        "recommended_choice": recommendation,
        "recommendation_reason": reason,
        "writes_selection": False,
    }


def print_text(result: dict[str, Any]) -> None:
    print(f"# Candidate Compare: {result['chapter']} ({result['mode']})")
    print(f"status: {result['status']}")
    print(f"recommended_choice: {result['recommended_choice']}")
    print(f"reason: {result['recommendation_reason']}")
    print()
    for name, item in result["candidates"].items():
        print(f"## {name}")
        print(f"- path: {item['path']}")
        print(f"- exists: {str(bool(item.get('exists'))).lower()}")
        print(f"- protagonist_agency: {item.get('protagonist_agency', 0)}")
        print(f"- mainline_progress: {item.get('mainline_progress', 0)}")
        print(f"- setting_new_risk: {item.get('setting_new_risk', 0)}")
        print(f"- ai_taste_risk: {item.get('ai_taste_risk', 0)}")
        print(f"- ledger_event_evidence: {item.get('ledger_event_evidence', 0)}")
        print(f"- unauthorized_breaker_risk: {item.get('unauthorized_breaker_risk', 0)}")
        print(f"- score: {item.get('score', 0)}")
        print()
    print("This command does not write selection.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Codex and DeepSeek candidates without recording selection.")
    parser.add_argument("chapter")
    parser.add_argument("--brief", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = compare(args.chapter, args.brief)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

