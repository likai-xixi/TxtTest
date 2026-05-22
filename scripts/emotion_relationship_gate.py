from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text
from review_binding import markdown_review_with_hash, sha256


PRIVATE_PRESSURE = (
    "\u538b\u529b",
    "\u5bb3\u6015",
    "\u6127",
    "\u79c1\u5fc3",
    "\u4e0d\u60f3",
    "\u60f3\u8981",
    "pressure",
    "fear",
    "guilt",
    "desire",
)
RELATIONSHIP = (
    "\u5173\u7cfb",
    "\u4fe1\u4efb",
    "\u80cc\u53db",
    "\u4eb2\u5bc6",
    "\u5bb6\u4eba",
    "\u7236",
    "\u6bcd",
    "\u670b\u53cb",
    "trust",
    "betray",
    "family",
    "friend",
)
CONSEQUENCE = (
    "\u4ee3\u4ef7",
    "\u540e\u679c",
    "\u9053\u6b49",
    "\u5931\u53bb",
    "\u727a\u7272",
    "\u8bb0\u4f4f",
    "cost",
    "consequence",
    "apology",
    "loss",
)
ABSENCE_REASON = (
    "emotion absence allowed",
    "relationship absence allowed",
    "allowed absence",
    "\u5141\u8bb8\u60c5\u611f\u7ebf\u7f3a\u5e2d",
    "\u5141\u8bb8\u5173\u7cfb\u7ebf\u7f3a\u5e2d",
    "\u672c\u7ae0\u5141\u8bb8\u7f3a\u5e2d",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def event_ledger_path() -> Path:
    return ROOT / "state" / "event_ledger.jsonl"


def count_terms(text: str, terms: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term.lower()) for term in terms)


def first_quote(text: str, terms: tuple[str, ...]) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and any(term.lower() in stripped.lower() for term in terms):
            return stripped[:140]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:140]
    return ""


def chapter_events(chapter: str) -> list[dict[str, Any]]:
    path = event_ledger_path()
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("chapter") == chapter and event.get("verified_by") == "human":
            events.append(event)
    return events


def evaluate(chapter: str) -> dict[str, Any]:
    path = official_path(chapter)
    brief = brief_path(chapter)
    text = read_text(path)
    brief_text = read_text(brief)
    if not text.strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": rel(path), "sha256": ""},
            "official_brief": {"path": rel(brief), "sha256": sha256(brief) if brief.exists() else ""},
            "checks": {},
            "evidence_quotes": [],
            "blockers": [f"missing official chapter: {rel(path)}"],
            "warnings": [],
            "human_acceptance": None,
        }
    events = chapter_events(chapter)
    event_types = {str(event.get("type")) for event in events}
    allowed_absence = any(marker.lower() in brief_text.lower() for marker in ABSENCE_REASON)
    checks = {
        "private_pressure": count_terms(text, PRIVATE_PRESSURE) > 0,
        "relationship_material": count_terms(text, RELATIONSHIP) > 0 or "relationship_change" in event_types,
        "emotional_consequence": count_terms(text, CONSEQUENCE) > 0 or "character_state_change" in event_types,
        "relationship_change_event": "relationship_change" in event_types,
        "allowed_absence_reason": allowed_absence,
    }
    evidence = [
        quote
        for quote in (
            first_quote(text, PRIVATE_PRESSURE),
            first_quote(text, RELATIONSHIP),
            first_quote(text, CONSEQUENCE),
        )
        if quote
    ]
    blockers: list[str] = []
    if not checks["allowed_absence_reason"]:
        if not checks["private_pressure"]:
            blockers.append("missing private pressure or desire consequence")
        if not (checks["relationship_material"] or checks["relationship_change_event"]):
            blockers.append("missing relationship material or human-verified relationship_change")
        if not checks["emotional_consequence"]:
            blockers.append("missing emotional consequence or character_state_change")
    status = "CLEAR" if not blockers else "BLOCKED"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": {"path": rel(path), "sha256": sha256(path)},
        "official_brief": {"path": rel(brief), "sha256": sha256(brief) if brief.exists() else ""},
        "checks": checks,
        "event_types": sorted(event_types),
        "evidence_quotes": evidence[:5],
        "blockers": blockers,
        "warnings": [] if evidence else ["machine could not find a direct emotion/relationship quote"],
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Emotion Relationship Gate: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "review_sha256:",
        "",
        "## Checks",
        "",
    ]
    for key, value in (report.get("checks") or {}).items():
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {item}" for item in values) if values else lines.append("- none")
    lines.extend(["", "## Evidence Quotes", ""])
    quotes = report.get("evidence_quotes") or []
    lines.extend(f"- {quote}" for quote in quotes) if quotes else lines.append("- none")
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check chapter emotion and relationship continuity.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "emotion_relationship_gate.json", report)
        write_text(out_dir / "emotion_relationship_gate.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
