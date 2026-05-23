from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Any

from _common import ROOT, now_iso, read_text, write_json, write_text
from product_kernel import file_ref, official_chapter_path, rel


def paragraphs(text: str) -> list[str]:
    values = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    return [item for item in values if not item.startswith("#")]


def quote_hash(quote: str) -> str:
    return hashlib.sha256(" ".join(quote.split()).encode("utf-8")).hexdigest()


def highlight_type(index: int) -> str:
    return ["life_texture", "character_friction", "memorable_language"][index % 3]


def select_highlights(text: str, limit: int = 3) -> list[dict[str, Any]]:
    candidates = []
    for para in paragraphs(text):
        quote = " ".join(para.split())
        if len(quote) < 18:
            continue
        score = min(len(quote), 240) + quote.count("，") * 2 + quote.count("。") * 2 + quote.count("、")
        candidates.append((score, quote[:220]))
    selected = [quote for _score, quote in sorted(candidates, reverse=True)[:limit]]
    highlights = []
    for index, quote in enumerate(selected, start=1):
        highlights.append(
            {
                "highlight_id": f"h{index:03d}",
                "type": highlight_type(index - 1),
                "quote": quote,
                "quote_sha256": quote_hash(quote),
                "reason": "Protect this local observation, friction, or language texture from being smoothed out during review.",
                "protection_level": "preserve_or_human_reason",
            }
        )
    return highlights


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_chapter_path(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    if not official.exists() or not read_text(official).strip():
        blockers.append(f"missing official chapter: {rel(official)}")
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": file_ref(official),
            "input_hashes": [file_ref(official)],
            "protected_highlights": [],
            "warnings": warnings,
            "blockers": blockers,
        }
    highlights = select_highlights(read_text(official))
    if not highlights:
        warnings.append("no protectable highlight quote found")
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "WARNING" if warnings else "CLEAR",
        "official_chapter": file_ref(official),
        "input_hashes": [file_ref(official)],
        "protected_highlights": highlights,
        "warnings": warnings,
        "blockers": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Highlights Review: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        f"generated_at: {report['generated_at']}",
        "",
        "## Protected Highlights",
        "",
    ]
    highlights = report.get("protected_highlights") or []
    if not highlights:
        lines.append("- none")
    for item in highlights:
        lines.extend(
            [
                f"- highlight_id: {item.get('highlight_id')}",
                f"  type: {item.get('type')}",
                f"  quote: {item.get('quote')}",
                f"  quote_sha256: {item.get('quote_sha256')}",
                f"  reason: {item.get('reason')}",
                f"  protection_level: {item.get('protection_level')}",
            ]
        )
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    blockers = report.get("blockers") or []
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisory protected highlights review for a chapter.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.chapter)
    if args.write and not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "highlights_review.json", report)
        write_text(out_dir / "highlights_review.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "NOT_READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
