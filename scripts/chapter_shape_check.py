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
    return {
        "opening": pick(opening_text, OPENING_PATTERNS, "unclear"),
        "obstacle": pick(text, OBSTACLE_PATTERNS, "unclear"),
        "resolution": pick(ending_text or text, RESOLUTION_PATTERNS, "unclear"),
        "hook": pick(ending_text or text, HOOK_PATTERNS, "unclear"),
    }


def shape_key(shape: dict[str, str]) -> str:
    return "|".join(shape.get(key, "unclear") for key in ("opening", "obstacle", "resolution", "hook"))


def load_shape_ledger() -> dict[str, Any]:
    return read_json(ROOT / "state" / "derived" / "chapter_shapes.json", {"schema_version": 1, "generated_at": "", "chapters": {}})


def prior_repetition_count(chapter: str, key: str, ledger: dict[str, Any]) -> int:
    count = 0
    for previous, value in sorted((ledger.get("chapters") or {}).items(), reverse=True):
        if previous >= chapter:
            continue
        if not isinstance(value, dict):
            continue
        if value.get("shape_key") == key:
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
    warnings: list[str] = []
    blockers: list[str] = []
    if repeat_count >= 2:
        message = f"chapter shape repeats the previous {repeat_count} shipped/checked chapters: {key}"
        if number >= 6:
            blockers.append(message)
        else:
            warnings.append(message)
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
