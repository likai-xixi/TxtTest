from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256
from review_binding import quote_matches_text


MAX_PREVIOUS_CHAPTERS = 3
MAX_KEY_QUOTES = 12


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def previous_chapter_ids(chapter: str, count: int = MAX_PREVIOUS_CHAPTERS) -> list[str]:
    number = chapter_number(chapter)
    volume = chapter.split("_", 1)[0]
    start = max(1, number - count)
    return [f"{volume}_c{idx:03d}" for idx in range(start, number)]


def load_events() -> list[dict[str, Any]]:
    path = ROOT / "state" / "event_ledger.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def selected_prior_events(chapter: str) -> list[dict[str, Any]]:
    number = chapter_number(chapter)
    previous = set(previous_chapter_ids(chapter, 5))
    selected: list[dict[str, Any]] = []
    for event in load_events():
        event_chapter = str(event.get("chapter", ""))
        try:
            event_number = chapter_number(event_chapter)
        except ValueError:
            continue
        if event_number >= number:
            continue
        if event_chapter in previous or event.get("importance") in {"P0", "P1"}:
            selected.append(event)
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(
        selected,
        key=lambda item: (rank.get(str(item.get("importance", "P2")), 2), -chapter_number(str(item.get("chapter"))), str(item.get("event_id", ""))),
    )


def quote_anchor_status(source_chapter: str, quote: str) -> str:
    if not quote.strip():
        return "missing_quote"
    path = official_path(source_chapter)
    if not path.exists():
        return "source_chapter_missing"
    return "matched" if quote_matches_text(quote, read_text(path)) else "not_matched"


def key_quote_rows(chapter: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in selected_prior_events(chapter):
        quote = str(event.get("evidence_quote", "")).strip()
        if not quote:
            continue
        source_chapter = str(event.get("chapter", ""))
        rows.append(
            {
                "chapter": source_chapter,
                "event_id": str(event.get("event_id", "")),
                "type": str(event.get("type", "")),
                "importance": str(event.get("importance", "")),
                "fact": str(event.get("fact", "")),
                "consequence": str(event.get("consequence", "")),
                "evidence_quote": quote,
                "quote_anchor_status": quote_anchor_status(source_chapter, quote),
            }
        )
    return rows[:MAX_KEY_QUOTES]


def anchor_rows(chapter: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for previous in previous_chapter_ids(chapter):
        path = ROOT / "state" / "derived" / "chapter_anchors" / f"{previous}.json"
        if not path.exists():
            rows.append({"chapter": previous, "status": "missing"})
            continue
        data = read_json(path, {})
        if isinstance(data, dict):
            rows.append(
                {
                    "chapter": previous,
                    "status": "available",
                    "source_event_id": data.get("source_event_id", ""),
                    "end_time": data.get("end_time", ""),
                    "end_location": data.get("end_location", ""),
                    "present_characters": data.get("present_characters", []),
                    "protagonist_state": data.get("protagonist_state", ""),
                    "carried_items": data.get("carried_items", []),
                    "unfinished_action": data.get("unfinished_action", ""),
                    "next_required_continuity": data.get("next_required_continuity", ""),
                }
            )
    return rows


def active_aftermath(chapter: str) -> list[dict[str, Any]]:
    path = ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json"
    data = read_json(path, {})
    if not isinstance(data, dict):
        return []
    current = chapter_number(chapter)
    active: list[dict[str, Any]] = []
    for item in data.get("obligations", []):
        if not isinstance(item, dict):
            continue
        try:
            source_number = chapter_number(str(item.get("source_chapter", "")))
            due_number = chapter_number(str(item.get("due_chapter", "")))
        except ValueError:
            continue
        if source_number < current <= due_number or item.get("status") == "overdue":
            active.append(item)
    return active


def reader_reward_window(chapter: str) -> list[dict[str, Any]]:
    path = ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json"
    data = read_json(path, {})
    if not isinstance(data, dict):
        return []
    current = chapter_number(chapter)
    rows: list[dict[str, Any]] = []
    for item in data.get("chapters", []):
        if not isinstance(item, dict):
            continue
        try:
            number = chapter_number(str(item.get("chapter", "")))
        except ValueError:
            continue
        if current - 5 <= number <= current:
            rows.append(
                {
                    "chapter": item.get("chapter", ""),
                    "status": item.get("status", ""),
                    "reader_reward_intensity": item.get("reader_reward_intensity", ""),
                    "ending_type": item.get("ending_type", ""),
                    "core_mechanism_state": item.get("core_mechanism_state", ""),
                    "cross_blockers": item.get("cross_blockers", []),
                }
            )
    return rows


def derived_state_refs() -> list[Path]:
    return [
        ROOT / "state" / "derived" / "personality" / "protagonist.json",
        ROOT / "state" / "derived" / "protagonist_progression.json",
        ROOT / "state" / "derived" / "world_reveal_ledger.json",
        ROOT / "state" / "derived" / "suspense_ledger.json",
        ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json",
        ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json",
    ]


def source_paths(chapter: str, *, include_context_pack: bool = True) -> list[Path]:
    paths = [
        ROOT / "state" / "project_reader_promise.json",
        ROOT / "state" / "project_style_contract.json",
        ROOT / "outline" / "chapter_briefs" / f"{chapter}.md",
    ]
    if include_context_pack:
        paths.append(ROOT / "state" / "context_pack" / f"{chapter}.md")
    for previous in previous_chapter_ids(chapter):
        paths.append(ROOT / "state" / "derived" / "chapter_anchors" / f"{previous}.json")
        prior = official_path(previous)
        if prior.exists():
            paths.append(prior)
    return [path for path in paths if path.exists()]


def build_review_context(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    official = official_path(chapter)
    key_quotes = key_quote_rows(chapter)
    blocked_quotes = [row for row in key_quotes if row.get("quote_anchor_status") != "matched"]
    status = "READY" if not blocked_quotes else "WARNING"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": ref(official),
        "input_hashes": [ref(path) for path in source_paths(chapter)],
        "boundary": {
            "purpose": "review_only_structured_state_and_key_quotes",
            "no_previous_chapter_full_text": True,
            "instruction": "Review agents may use this to understand prior state without reading prior chapter bodies.",
        },
        "structured_state": {
            "previous_chapter_anchors": anchor_rows(chapter),
            "active_aftermath_obligations": active_aftermath(chapter),
            "reader_reward_window": reader_reward_window(chapter),
            "derived_state_sources": [rel(path) for path in derived_state_refs() if path.exists()],
        },
        "key_quotes": key_quotes,
        "warnings": [f"prior quote not matched: {row.get('event_id')}" for row in blocked_quotes],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Review Context: {report['chapter']}",
        "",
        f"status: {report.get('status', '')}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "",
        "## Boundary",
        "",
        "- This file contains structured state and key prior evidence quotes only.",
        "- It must not include previous chapter full text.",
        "- It is an input for independent chapter review and anti-AI review.",
        "",
        "## Structured State",
        "",
        "```json",
        json.dumps(report.get("structured_state", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Key Prior Evidence Quotes",
        "",
    ]
    quotes = report.get("key_quotes", [])
    if not quotes:
        lines.append("- none")
    else:
        for item in quotes:
            lines.append(
                "- "
                f"{item.get('chapter')} {item.get('event_id')} "
                f"({item.get('type')}, {item.get('importance')}, {item.get('quote_anchor_status')}): "
                f"{item.get('evidence_quote')}"
            )
    warnings = report.get("warnings", [])
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
    lines.append("")
    return "\n".join(lines)


def write_review_context(chapter: str) -> dict[str, Any]:
    report = build_review_context(chapter)
    base = ROOT / "state" / "context_pack"
    write_json(base / f"{chapter}_review_context.json", report)
    write_text(base / f"{chapter}_review_context.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only structured state and key quote context.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = write_review_context(args.chapter) if args.write else build_review_context(args.chapter)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report.get("status") in {"READY", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
