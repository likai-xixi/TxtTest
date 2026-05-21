from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256


GRAY_MARKERS = (
    "lie",
    "lied",
    "hide",
    "hidden",
    "secret",
    "selfish",
    "spite",
    "dirty",
    "blackmail",
    "betray",
    "cheat",
    "threat",
    "私心",
    "隐瞒",
    "骗",
    "威胁",
    "使坏",
    "报复",
    "背叛",
)
HIGH_IMPACT_MARKERS = (
    "relationship",
    "trust",
    "kill",
    "death",
    "rule",
    "power",
    "ability",
    "break",
    "关系",
    "信任",
    "死亡",
    "规则",
    "能力",
    "破局",
    "人格",
)
GRAY_TAGS = {"gray_behavior", "private_motive", "dirty_play", "concealment", "emotional_boundary"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def first_quote(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:140]
    return ""


def marker_hits(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [marker for marker in markers if marker.lower() in lowered]


def chapter_events(chapter: str) -> list[dict[str, Any]]:
    path = ROOT / "state" / "event_ledger.jsonl"
    events = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("chapter") == chapter:
            events.append(entry)
    return events


def event_has_gray_coverage(events: list[dict[str, Any]]) -> bool:
    for entry in events:
        tags = {str(item) for item in entry.get("tags", []) if isinstance(item, str)}
        if tags & GRAY_TAGS:
            return True
        if str(entry.get("type", "")) in {"character_decision", "relationship_change", "character_state_change"}:
            text = " ".join(str(entry.get(key, "")) for key in ("fact", "consequence"))
            if marker_hits(text, GRAY_MARKERS):
                return True
    return False


def fact_card_has_gray_coverage(chapter: str) -> bool:
    path = ROOT / "reviews" / chapter / "fact_cards.json"
    data = read_json(path, {})
    if not isinstance(data, dict):
        return False
    for card in data.get("cards", []) if isinstance(data.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        tags = {str(item) for item in card.get("tags", []) if isinstance(item, str)}
        if tags & GRAY_TAGS:
            return True
    return False


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_path(chapter)
    if not official.exists() or not read_text(official).strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": rel(official), "sha256": ""},
            "gray_markers": [],
            "high_impact_markers": [],
            "obligations": [],
            "blockers": [f"missing official chapter: {rel(official)}"],
            "warnings": [],
        }
    text = read_text(official)
    gray_hits = marker_hits(text, GRAY_MARKERS)
    impact_hits = marker_hits(text, HIGH_IMPACT_MARKERS)
    events = chapter_events(chapter)
    covered = event_has_gray_coverage(events) or fact_card_has_gray_coverage(chapter)
    obligations: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    if gray_hits and impact_hits:
        obligations.append(
            {
                "chapter": chapter,
                "kind": "gray_consequence",
                "status": "covered" if covered else "unresolved",
                "evidence_quote": first_quote(text),
                "required_followup": "Record a human-verified event or fact card for the durable consequence of this gray action.",
            }
        )
        if not covered:
            blockers.append("high-impact gray behavior needs a human-verified event or fact card coverage")
    elif gray_hits:
        warnings.append("gray behavior appears low-impact; keep it visible if it later affects relationships, personality, or plot.")
    status = "BLOCKED" if blockers else "WARNING" if warnings else "READY"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": {"path": rel(official), "sha256": sha256(official)},
        "gray_markers": gray_hits,
        "high_impact_markers": impact_hits,
        "obligations": obligations,
        "blockers": blockers,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Gray Consequence: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        f"generated_at: {report['generated_at']}",
        "",
        "## Markers",
        "",
        f"- gray_markers: {', '.join(report.get('gray_markers') or []) or 'none'}",
        f"- high_impact_markers: {', '.join(report.get('high_impact_markers') or []) or 'none'}",
        "",
        "## Obligations",
        "",
    ]
    for obligation in report.get("obligations") or []:
        lines.append(f"- {obligation.get('status')}: {obligation.get('required_followup')} quote={obligation.get('evidence_quote')}")
    if not report.get("obligations"):
        lines.append("- none")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {item}" for item in report.get(key) or ["none"])
    return "\n".join(lines).rstrip() + "\n"


def update_ledger(report: dict[str, Any]) -> None:
    path = ROOT / "state" / "derived" / "gray_consequence_ledger.json"
    current = read_json(path, {"schema_version": 1, "generated_at": "", "chapters": {}})
    if not isinstance(current, dict):
        current = {"schema_version": 1, "chapters": {}}
    chapters = current.setdefault("chapters", {})
    if isinstance(chapters, dict):
        chapters[report["chapter"]] = {
            "status": report["status"],
            "obligations": report.get("obligations", []),
            "updated_at": now_iso(),
        }
    current["generated_at"] = now_iso()
    write_json(path, current)
    md_lines = ["# Gray Consequence Ledger", "", f"generated_at: {current['generated_at']}", ""]
    for chapter, value in sorted((current.get("chapters") or {}).items()):
        md_lines.append(f"- {chapter}: {value.get('status')} obligations={len(value.get('obligations', []))}")
    write_text(ROOT / "state" / "derived" / "gray_consequence_ledger.md", "\n".join(md_lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Track gray behavior consequences without creating a new fact source.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "gray_consequence.json", report)
        write_text(out_dir / "gray_consequence.md", render_markdown(report))
        update_ledger(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] in {"READY", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
