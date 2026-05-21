from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_json, write_text


REVIEW_TEMPLATES = ("ai_taste.md", "dialogue_function.md", "codex_anti_ai_review.md", "deepseek_anti_ai_review.md")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def chapter_candidates() -> list[str]:
    chapters: set[str] = set()
    for item in (ROOT / "reviews").glob("v??_c???"):
        if item.is_dir():
            chapters.add(item.name)
    for item in (ROOT / "outline" / "chapter_briefs").glob("v??_c???.md"):
        chapters.add(item.stem)
    return sorted(chapters)


def official_ref(chapter: str) -> dict[str, str]:
    volume, chapter_file = chapter_parts(chapter)
    path = ROOT / "chapters" / volume / chapter_file
    ref = {"path": rel(path), "sha256": ""}
    if path.exists():
        import hashlib

        ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return ref


def ai_taste_draft(chapter: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "BLOCKED",
        "official_chapter": official_ref(chapter),
        "metrics": {},
        "categories": {
            key: {
                "status": "BLOCKED",
                "severity": "P1",
                "evidence_quotes": [],
                "issue": "migration draft; reviewer must inspect current official chapter",
                "revision_actions": ["fill evidence quote and decide CLEAR / BLOCKED / ACCEPTED_BY_HUMAN"],
            }
            for key in (
                "show_dont_tell",
                "rhythm_disorder",
                "emotional_risk",
                "gray_motive",
                "dialogue_agenda",
                "detail_economy",
                "consequence_integrity",
            )
        },
        "blockers": ["migration draft is not reviewed"],
        "warnings": [],
        "human_acceptance": None,
    }


def deepseek_anti_ai_draft(chapter: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "model": "deepseek-v4-pro",
        "status": "BLOCKED",
        "action": "Revise once",
        "official_chapter": official_ref(chapter),
        "inputs": [],
        "summary": "migration draft; run DeepSeek anti-AI review against the current official chapter",
        "categories": {
            key: {
                "status": "BLOCKED",
                "severity": "P1",
                "evidence_quotes": [],
                "issue": "migration draft; DeepSeek must inspect current official chapter",
                "revision_actions": [f"run `python scripts/novel.py deepseek-anti-ai-review {chapter}` before Ship"],
            }
            for key in (
                "show_dont_tell",
                "rhythm_disorder",
                "emotional_risk",
                "gray_motive",
                "dialogue_agenda",
                "detail_economy",
                "setting_integration",
                "consequence_integrity",
            )
        },
        "dialogue_samples": [],
        "blockers": ["migration draft is not reviewed by DeepSeek"],
        "warnings": [],
        "human_acceptance": None,
    }


def codex_anti_ai_draft(chapter: str) -> dict[str, Any]:
    data = deepseek_anti_ai_draft(chapter)
    data["model"] = "codex-subagent"
    data["summary"] = "migration draft; run Codex anti-AI subagent review against the current official chapter"
    for item in data["categories"].values():
        item["issue"] = "migration draft; Codex anti-AI subagent must inspect current official chapter"
        item["revision_actions"] = [f"run `python scripts/novel.py codex-anti-ai-review-start {chapter}` before Ship"]
    data["blockers"] = ["migration draft is not reviewed by Codex anti-AI subagent"]
    return data


def dialogue_draft(chapter: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "BLOCKED",
        "official_chapter": official_ref(chapter),
        "summary": {
            "dialogue_line_count": 0,
            "sample_count": 0,
            "pure_theme_statement_count": 0,
            "pure_theme_statement_ratio": 0.0,
        },
        "samples": [],
        "blockers": ["migration draft is not reviewed"],
        "warnings": [],
        "human_acceptance": None,
    }


def migrate_chapter(chapter: str, *, force: bool) -> list[str]:
    chapter_parts(chapter)
    written: list[str] = []
    review_dir = ROOT / "reviews" / chapter
    review_dir.mkdir(parents=True, exist_ok=True)
    for template_name in REVIEW_TEMPLATES:
        target = review_dir / template_name
        if not target.exists() or force:
            text = read_text(ROOT / "templates" / template_name).replace("{chapter}", chapter)
            write_text(target, text)
            written.append(rel(target))
    json_targets = {
        "ai_taste.json": ai_taste_draft(chapter),
        "dialogue_function.json": dialogue_draft(chapter),
        "codex_anti_ai_review.json": codex_anti_ai_draft(chapter),
        "deepseek_anti_ai_review.json": deepseek_anti_ai_draft(chapter),
    }
    for name, data in json_targets.items():
        target = review_dir / name
        if not target.exists() or force:
            write_json(target, data)
            written.append(rel(target))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Create anti-AI review scaffolds without marking them clear.")
    parser.add_argument("chapter", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.all:
        chapters = chapter_candidates()
    elif args.chapter:
        chapters = [args.chapter]
    else:
        print("ERROR: pass a chapter or --all")
        return 1
    print("# Migrate Anti-AI Reviews")
    print()
    for chapter in chapters:
        written = migrate_chapter(chapter, force=args.force)
        print(f"## {chapter}")
        if not written:
            print("- no files written")
        for item in written:
            print(f"- wrote {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
