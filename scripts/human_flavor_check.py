from __future__ import annotations

import argparse
import json
import re
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, read_text, write_json, write_text
from product_kernel import file_ref, official_brief_path, official_chapter_path, rel, sha256


SECTION_NAMES = {
    "focus": ("本章人味焦点", "Human Flavor Focus"),
    "texture": ("本章生活毛边", "Life Texture"),
    "preserve": ("本章禁止写平", "Do Not Flatten"),
}
PLACEHOLDER_MARKERS = {"", "TODO", "TBD", "待定", "待填", "none", "None", "无"}


def clean_line(line: str) -> str:
    return line.strip().lstrip("-*+0123456789. ").strip()


def markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def section_body(sections: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        if alias in sections:
            return sections[alias]
    readable_hints = {
        "Human Flavor Focus": ("人味", "cost", "misjudgment"),
        "Life Texture": ("生活毛边", "life texture"),
        "Do Not Flatten": ("禁止写平", "flatten"),
    }
    hints = tuple(hint for alias in aliases for hint in readable_hints.get(alias, ()))
    if hints:
        for name, body in sections.items():
            if any(hint in name for hint in hints):
                return body
    return ""


def value_after_colon(line: str) -> str:
    text = clean_line(line)
    for sep in (":", "："):
        if sep in text:
            return text.split(sep, 1)[1].strip()
    return text


def ready_value(value: str) -> bool:
    stripped = value.strip()
    if stripped in PLACEHOLDER_MARKERS:
        return False
    return not any(marker in stripped for marker in ("TODO", "待定", "待填"))


def body_has_ready_value(body: str) -> bool:
    return any(ready_value(value_after_colon(line)) for line in body.splitlines() if clean_line(line))


def paragraphs(text: str) -> list[str]:
    values = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    return [item for item in values if not item.startswith("#")]


def sample_quotes(text: str, limit: int = 3) -> list[str]:
    quotes: list[str] = []
    for para in paragraphs(text):
        value = " ".join(para.split())
        if len(value) < 12:
            continue
        quotes.append(value[:180])
        if len(quotes) >= limit:
            break
    return quotes


def prior_human_flavor_reports(chapter: str, window: int) -> list[dict[str, Any]]:
    current = chapter_number(chapter)
    volume = chapter[:3]
    reports: list[dict[str, Any]] = []
    # The window is current-inclusive; a 3-chapter window means two prior
    # reports plus the current chapter.
    for number in range(max(1, current - window + 1), current):
        path = ROOT / "reviews" / f"{volume}_c{number:03d}" / "human_flavor.json"
        data = read_json(path, {})
        if isinstance(data, dict) and data:
            reports.append(data)
    return reports


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_chapter_path(chapter)
    brief = official_brief_path(chapter)
    blockers: list[str] = []
    warnings: list[str] = []

    if not official.exists() or not read_text(official).strip():
        blockers.append(f"missing official chapter: {rel(official)}")
    if not brief.exists() or not read_text(brief).strip():
        blockers.append(f"missing official brief: {rel(brief)}")
    if blockers:
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "blocking": False,
            "official_chapter": file_ref(official),
            "official_brief": file_ref(brief),
            "input_hashes": [file_ref(official), file_ref(brief)],
            "signals": {},
            "window": {},
            "evidence_quotes": [],
            "warnings": warnings,
            "blockers": blockers,
        }

    brief_text = read_text(brief)
    chapter_text = read_text(official)
    sections = markdown_sections(brief_text)
    focus = section_body(sections, SECTION_NAMES["focus"])
    texture = section_body(sections, SECTION_NAMES["texture"])
    preserve = section_body(sections, SECTION_NAMES["preserve"])

    signals = {
        "has_human_flavor_focus": bool(focus),
        "has_life_texture_contract": bool(texture),
        "has_do_not_flatten_contract": bool(preserve),
        "protagonist_cost_or_misjudgment_declared": body_has_ready_value(focus),
        "private_motive_or_evasion_declared": body_has_ready_value(focus),
        "life_texture_declared": body_has_ready_value(texture),
        "do_not_flatten_declared": body_has_ready_value(preserve),
    }
    for key, value in signals.items():
        if not value:
            warnings.append(f"{key} is missing or not ready")

    quotes = sample_quotes(chapter_text)
    if not quotes:
        warnings.append("official chapter has no usable human-flavor evidence quote sample")

    prior3 = prior_human_flavor_reports(chapter, 3)
    prior5 = prior_human_flavor_reports(chapter, 5)
    current_missing_cost = not signals["protagonist_cost_or_misjudgment_declared"]
    consecutive_missing_cost = sum(
        1 for item in prior3 if not (item.get("signals") or {}).get("protagonist_cost_or_misjudgment_declared")
    ) + (1 if current_missing_cost else 0)
    warning_run = sum(1 for item in prior5 if item.get("status") == "WARNING") + (1 if warnings else 0)
    window = {
        "last_3_missing_cost_or_misjudgment": consecutive_missing_cost,
        "last_5_human_flavor_warnings": warning_run,
        "route_recommendation": "NORMAL" if consecutive_missing_cost >= 3 or warning_run >= 5 else "FAST_OK",
    }
    if consecutive_missing_cost >= 3:
        warnings.append("3-chapter window lacks protagonist cost or misjudgment; route should upgrade to NORMAL")
    if warning_run >= 5 and warnings:
        warnings.append("5-chapter window has repeated human-flavor warnings; long health should observe")

    status = "WARNING" if warnings else "CLEAR"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "blocking": False,
        "official_chapter": file_ref(official),
        "official_brief": file_ref(brief),
        "input_hashes": [file_ref(official), file_ref(brief)],
        "signals": signals,
        "window": window,
        "evidence_quotes": quotes,
        "warnings": warnings,
        "blockers": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Human Flavor Review: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        f"official_brief_sha256: {report.get('official_brief', {}).get('sha256', '')}",
        f"generated_at: {report['generated_at']}",
        "",
        "## Advisory Signals",
        "",
    ]
    signals = report.get("signals") or {}
    if signals:
        lines.extend(f"- {key}: {value}" for key, value in sorted(signals.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence Quotes", ""])
    quotes = report.get("evidence_quotes") or []
    lines.extend(f"- {quote}" for quote in quotes) if quotes else lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    blockers = report.get("blockers") or []
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisory human-flavor review for a chapter.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.chapter)
    if args.write and not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "human_flavor.json", report)
        write_text(out_dir / "human_flavor.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "NOT_READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
