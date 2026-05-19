from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, read_text, write_json, write_text
from element_context import markdown_sections, section_body


TABLE_PREFIXES = ("outline/tables/", "state/derived/tables/")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_events() -> list[dict[str, Any]]:
    path = ROOT / "state" / "event_ledger.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def brief_title_intro(path: Path) -> tuple[str, str]:
    sections = markdown_sections(read_text(path))
    title = section_body(sections, ("章节标题", "Chapter Title")).strip()
    intro = section_body(sections, ("章节简介", "Chapter Intro")).strip()
    return title, intro


def build_chapter_plan() -> dict[str, Any]:
    chapters = []
    for path in sorted((ROOT / "outline" / "chapter_briefs").glob("v*_c*.md")):
        title, intro = brief_title_intro(path)
        chapters.append(
            {
                "chapter": path.stem,
                "brief_path": rel(path),
                "title": title,
                "intro": intro,
                "advisory_only": True,
            }
        )
    return {"schema_version": 1, "generated_at": now_iso(), "chapters": chapters, "advisory_only": True}


def build_arc_table(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_chapter.setdefault(str(event.get("chapter", "unknown")), []).append(
            {
                "event_id": event.get("event_id"),
                "type": event.get("type"),
                "importance": event.get("importance", "P2"),
                "thread_id": event.get("thread_id", ""),
                "fact": event.get("fact", ""),
            }
        )
    return {"schema_version": 1, "generated_at": now_iso(), "chapters": by_chapter, "advisory_only": True}


def render_markdown_table(title: str, headers: list[str], rows: list[list[str]]) -> str:
    lines = [f"# {title}", "", "advisory_only: true", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    if not rows:
        lines.append("| " + " | ".join("none" for _ in headers) + " |")
    else:
        for row in rows:
            lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines).rstrip() + "\n"


def write_tables() -> None:
    events = load_events()
    chapter_plan = build_chapter_plan()
    arc_table = build_arc_table(events)
    write_json(ROOT / "outline" / "tables" / "chapter_plan.json", chapter_plan)
    write_json(ROOT / "outline" / "tables" / "arc_table.json", arc_table)
    write_json(ROOT / "state" / "derived" / "catalog" / "chapters.json", chapter_plan)

    chapter_rows = [
        [item["chapter"], item.get("title") or "", item.get("intro") or "", item["brief_path"]]
        for item in chapter_plan["chapters"]
    ]
    write_text(
        ROOT / "state" / "derived" / "tables" / "chapters.md",
        render_markdown_table("Chapter Table", ["chapter", "title", "intro", "brief"], chapter_rows),
    )

    threads = [
        [str(event.get("thread_id") or ""), str(event.get("chapter", "")), str(event.get("type", "")), str(event.get("fact", ""))]
        for event in events
        if event.get("type") in {"thread_opened", "thread_advanced", "thread_paid_off", "correction"}
    ]
    write_text(
        ROOT / "state" / "derived" / "tables" / "threads.md",
        render_markdown_table("Thread Table", ["thread", "chapter", "type", "fact"], threads),
    )

    characters = [
        [",".join(str(entity) for entity in event.get("entities", [])), str(event.get("chapter", "")), str(event.get("fact", ""))]
        for event in events
        if event.get("entities")
    ]
    write_text(
        ROOT / "state" / "derived" / "tables" / "characters.md",
        render_markdown_table("Character Table", ["entities", "chapter", "fact"], characters),
    )


def table_paths_in_manifest(manifest: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for item in manifest.get("input_hashes", []) or []:
        path = str(item.get("path", "")) if isinstance(item, dict) else ""
        if path.startswith(TABLE_PREFIXES):
            found.append(path)
    for section in manifest.get("sections", []) or []:
        if not isinstance(section, dict):
            continue
        for source in section.get("sources", []) or []:
            path = str(source.get("path", "")) if isinstance(source, dict) else ""
            if path.startswith(TABLE_PREFIXES):
                found.append(path)
    return sorted(set(found))


def check_tables() -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    required = [
        ROOT / "outline" / "tables" / "chapter_plan.json",
        ROOT / "outline" / "tables" / "arc_table.json",
        ROOT / "state" / "derived" / "tables" / "characters.md",
        ROOT / "state" / "derived" / "tables" / "chapters.md",
        ROOT / "state" / "derived" / "tables" / "threads.md",
    ]
    missing = [rel(path) for path in required if not path.exists()]
    if missing:
        warnings.extend(f"missing advisory table: {path}" for path in missing)
    for path in sorted((ROOT / "state" / "context_pack").glob("*.manifest.json")):
        try:
            manifest = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            blockers.append(f"invalid context manifest {rel(path)}: {exc}")
            continue
        found = table_paths_in_manifest(manifest)
        if found:
            blockers.append(f"context manifest {rel(path)} uses advisory table as fact source: {', '.join(found)}")
    if blockers:
        return "BLOCKED", blockers, warnings
    if warnings:
        return "INFO", blockers, warnings
    return "READY", blockers, warnings


def print_check() -> int:
    status, blockers, warnings = check_tables()
    print("# Table Check")
    print()
    print(f"status: {status}")
    if blockers:
        print()
        print("## Blockers")
        for item in blockers:
            print(f"- {item}")
    if warnings:
        print()
        print("## Notes")
        for item in warnings:
            print(f"- {item}")
    return 1 if blockers else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or check advisory editor tables.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return print_check()
    write_tables()
    print("OK: wrote outline/tables and state/derived/tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
