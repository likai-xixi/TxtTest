from __future__ import annotations

import argparse
import json
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, read_text, write_json, write_text
from product_kernel import SOURCE_PRIORITY, event_ledger_path, file_ref, official_brief_path, official_chapter_path, review_dir


STYLE_REVIEW_FILES = (
    "style_metrics.json",
    "series_style.json",
    "human_flavor.json",
    "highlights_review.json",
    "prose_risk.json",
)


def chapter_id(number: int, volume: str) -> str:
    return f"{volume}_c{number:03d}"


def safe_json(path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, None
    try:
        data = read_json(path, {})
    except Exception as exc:
        return {}, f"{path.relative_to(ROOT).as_posix()} invalid JSON: {exc}"
    if not isinstance(data, dict):
        return {}, f"{path.relative_to(ROOT).as_posix()} must be a JSON object"
    return data, None


def sample_line_from_chapter(chapter: str) -> str:
    text = read_text(official_chapter_path(chapter))
    for paragraph in text.split("\n\n"):
        line = " ".join(paragraph.split())
        if len(line) >= 12:
            return line[:180]
    return ""


def evaluate(to_chapter: str) -> dict:
    max_chapter = chapter_number(to_chapter)
    volume = to_chapter[:3]
    chapters = []
    voice_samples: list[str] = []
    forbidden_traits: set[str] = set()
    voice_traits: set[str] = set()
    warnings = []
    blockers = []
    for number in range(1, max_chapter + 1):
        chapter = chapter_id(number, volume)
        refs = [file_ref(official_chapter_path(chapter)), file_ref(official_brief_path(chapter))]
        statuses = {}
        for name in STYLE_REVIEW_FILES:
            path = review_dir(chapter) / name
            if path.exists():
                refs.append(file_ref(path))
                data, error = safe_json(path)
                if error:
                    blockers.append(error)
                    continue
                statuses[name] = data.get("status", "UNKNOWN")
                if name == "highlights_review.json":
                    for item in data.get("protected_highlights", []) if isinstance(data.get("protected_highlights"), list) else []:
                        if isinstance(item, dict) and str(item.get("quote", "")).strip():
                            voice_samples.append(str(item["quote"]).strip()[:180])
                if name == "human_flavor.json" and data.get("status") == "CLEAR":
                    voice_traits.add("human_flavor_clear")
                if name == "prose_risk.json":
                    categories = data.get("categories") if isinstance(data.get("categories"), dict) else {}
                    for key, value in categories.items():
                        if isinstance(value, dict) and value.get("status") in {"WARNING", "BLOCKED"}:
                            forbidden_traits.add(str(key))
        if any(ref.get("exists") for ref in refs):
            sample = sample_line_from_chapter(chapter)
            if sample:
                voice_samples.append(sample)
            chapters.append(
                {
                    "chapter": chapter,
                    "source_refs": refs,
                    "review_statuses": statuses,
                    "source_priority_applied": "official chapter evidence > official brief > review artifacts",
                }
            )
        if "human_flavor.json" not in statuses:
            warnings.append(f"{chapter}: missing human_flavor style signal")
        if "highlights_review.json" not in statuses:
            warnings.append(f"{chapter}: missing protected highlights style signal")
    voices = [
        {
            "character_id": "protagonist",
            "voice_traits": sorted(voice_traits) or ["derive_from_official_chapter_evidence"],
            "forbidden_traits": sorted(forbidden_traits) or ["summary_voice_without_scene_anchor"],
            "sample_lines": voice_samples[:8],
            "source_priority_applied": "official chapter evidence > official brief > review artifacts",
        }
    ]
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "through": to_chapter,
        "status": "BLOCKED" if blockers else ("WARNING" if warnings else "READY"),
        "source_priority": SOURCE_PRIORITY,
        "source_event_ledger": file_ref(event_ledger_path()),
        "voices": voices,
        "chapters": chapters,
        "blockers": blockers,
        "warnings": warnings[:50],
    }


def render_markdown(report: dict) -> str:
    lines = [f"# Style Voice Ledger: through {report['through']}", "", f"status: {report['status']}", "", "## Voices", ""]
    for voice in report.get("voices", []):
        samples = "; ".join(voice.get("sample_lines", [])[:2]) or "no samples"
        lines.append(f"- voice {voice.get('character_id')}: {samples}")
    lines.extend(["", "## Chapters", ""])
    for item in report.get("chapters", []):
        statuses = ", ".join(f"{key}={value}" for key, value in item.get("review_statuses", {}).items()) or "no reviews"
        lines.append(f"- {item['chapter']}: {statuses}")
    if not report.get("chapters"):
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the derived style voice ledger.")
    parser.add_argument("--to", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        write_json(ROOT / "state" / "derived" / "style_voice_ledger.json", report)
        write_text(ROOT / "state" / "derived" / "style_voice_ledger.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
