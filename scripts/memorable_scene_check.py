from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text
from review_binding import markdown_review_with_hash, sha256


SCENE_MARKERS = (
    "\u95e8",
    "\u96e8",
    "\u8840",
    "\u706f",
    "\u624b",
    "\u58f0",
    "\u7a97",
    "\u684c",
    "\u51b7",
    "\u70ed",
    "door",
    "rain",
    "blood",
    "light",
    "hand",
)
ACTION_MARKERS = (
    "\u9009\u62e9",
    "\u62d2\u7edd",
    "\u6293",
    "\u63a8",
    "\u8dd1",
    "\u64d2",
    "\u85cf",
    "\u4fdd\u62a4",
    "\u6495",
    "choose",
    "refuse",
    "grab",
    "run",
    "hide",
)
BUREAUCRATIC_MARKERS = (
    "\u6d41\u7a0b",
    "\u62a5\u544a",
    "\u6863\u6848",
    "\u5ba1\u6279",
    "\u7f16\u53f7",
    "\u63d0\u4ea4",
    "process",
    "report",
    "file",
    "approval",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def first_line(text: str, markers: tuple[str, ...], *, avoid: tuple[str, ...] = ()) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if markers and not any(marker.lower() in lowered for marker in markers):
            continue
        if avoid and any(marker.lower() in lowered for marker in avoid):
            continue
        return stripped[:140]
    return ""


def memorable_language(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 8 or len(stripped) > 80:
            continue
        lowered = stripped.lower()
        if any(marker.lower() in lowered for marker in BUREAUCRATIC_MARKERS):
            continue
        if any(char in stripped for char in ("?", "!", "\uff1f", "\uff01", "\u201c", "\u201d")) or first_line(stripped, ACTION_MARKERS):
            return stripped[:140]
    return first_line(text, (), avoid=BUREAUCRATIC_MARKERS)


def evaluate(chapter: str) -> dict[str, Any]:
    path = official_path(chapter)
    text = read_text(path)
    if not text.strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": rel(path), "sha256": ""},
            "checks": {},
            "evidence_quotes": [],
            "blockers": [f"missing official chapter: {rel(path)}"],
            "warnings": [],
            "human_acceptance": None,
        }
    scene = first_line(text, SCENE_MARKERS)
    action = first_line(text, ACTION_MARKERS)
    language = memorable_language(text)
    checks = {
        "retellable_scene": bool(scene),
        "character_action_memory": bool(action),
        "non_bureaucratic_sentence": bool(language),
    }
    blockers = [key for key, value in checks.items() if not value]
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "CLEAR" if not blockers else "BLOCKED",
        "official_chapter": {"path": rel(path), "sha256": sha256(path)},
        "checks": checks,
        "evidence_quotes": [quote for quote in (scene, action, language) if quote],
        "blockers": [f"missing {key}" for key in blockers],
        "warnings": [],
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Memorable Scene Check: {report['chapter']}",
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
    lines.extend(["", "## Blockers", ""])
    values = report.get("blockers") or []
    lines.extend(f"- {item}" for item in values) if values else lines.append("- none")
    lines.extend(["", "## Evidence Quotes", ""])
    quotes = report.get("evidence_quotes") or []
    lines.extend(f"- {quote}" for quote in quotes) if quotes else lines.append("- none")
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that the chapter leaves a repeatable scene, action, and language memory point.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "memorable_scene.json", report)
        write_text(out_dir / "memorable_scene.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
