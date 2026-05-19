from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, read_json, write_text
from pacing_check import analyze, brief_paths, parse_entry


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def safe_chapter_number(value: str) -> int | None:
    try:
        return chapter_number(value)
    except ValueError:
        return None


def load_obligations(chapter: str | None) -> list[dict[str, Any]]:
    path = ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json"
    data = read_json(path, {"obligations": []})
    obligations = data.get("obligations", []) if isinstance(data, dict) else []
    if not isinstance(obligations, list):
        return []
    if chapter is None:
        return [item for item in obligations if isinstance(item, dict)]
    target_number = chapter_number(chapter)
    volume = chapter[:3]
    result: list[dict[str, Any]] = []
    for item in obligations:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_chapter") or "")
        if not source.startswith(volume):
            continue
        source_number = safe_chapter_number(source)
        if source_number is None or source_number <= target_number:
            result.append(item)
    return result


def due_soon(item: dict[str, Any], chapter: str | None) -> bool:
    if chapter is None or item.get("status") != "active":
        return False
    due = str(item.get("due_chapter") or "")
    due_number = safe_chapter_number(due)
    return due_number is not None and due_number <= chapter_number(chapter) + 1


def build_dashboard(chapter: str | None, window: int) -> dict[str, Any]:
    paths = brief_paths(chapter)
    entries = [parse_entry(path) for path in paths]
    status, blockers, warnings = analyze(entries, window)
    obligations = load_obligations(chapter)
    groups = {
        "overdue": [item for item in obligations if item.get("status") == "overdue"],
        "due_soon": [item for item in obligations if due_soon(item, chapter)],
        "active": [item for item in obligations if item.get("status") == "active"],
        "resolved": [item for item in obligations if item.get("status") == "resolved"],
    }
    recent = entries[-5:]
    return {
        "schema_version": 1,
        "status": status,
        "target_chapter": chapter,
        "window": window,
        "chapters_checked": len(entries),
        "recent": recent,
        "blockers": blockers,
        "warnings": warnings,
        "aftermath": groups,
        "source_files": {
            "progress_index": "state/derived/pacing/progress_index.json",
            "aftermath_obligations": "state/derived/pacing/aftermath_obligations.json",
        },
    }


def obligation_label(item: dict[str, Any]) -> str:
    source = item.get("source_chapter", "unknown")
    due = item.get("due_chapter", "unknown")
    body = item.get("aftermath_obligation") or item.get("progress_target") or "unspecified obligation"
    resolved_by = item.get("resolved_by") or []
    suffix = f" resolved_by={', '.join(resolved_by)}" if resolved_by else ""
    return f"{source} -> {due}: {body}{suffix}"


def render_markdown(report: dict[str, Any]) -> str:
    title = report.get("target_chapter") or "all"
    lines = [
        f"# Pacing / Aftermath Dashboard: {title}",
        "",
        f"status: {report.get('status')}",
        f"chapters_checked: {report.get('chapters_checked')}",
        f"window: {report.get('window')}",
        "",
        "## Recent Pacing",
        "",
    ]
    recent = report.get("recent") or []
    if recent:
        for entry in recent:
            lines.append(
                "- {chapter}: S={s} W={w} progress={progress} impact={impact} consequence={consequence}".format(
                    chapter=entry.get("chapter"),
                    s=entry.get("mainline_level") or "?",
                    w=entry.get("external_level") or "?",
                    progress=entry.get("progress_mode") or "?",
                    impact=entry.get("impact_scale") or "?",
                    consequence=entry.get("consequence_level") or "?",
                )
            )
    else:
        lines.append("- none")
    for title, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        lines.extend(["", f"## {title}", ""])
        items = report.get(key) or []
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    aftermath = report.get("aftermath") or {}
    for title, key in (("Overdue", "overdue"), ("Due Soon", "due_soon"), ("Active", "active"), ("Resolved", "resolved")):
        lines.extend(["", f"## Aftermath: {title}", ""])
        items = aftermath.get(key) or []
        lines.extend(f"- {obligation_label(item)}" for item in items) if items else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def print_text(report: dict[str, Any]) -> None:
    print(render_markdown(report), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a pacing and aftermath dashboard without changing workflow gates.")
    parser.add_argument("chapter", nargs="?")
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_dashboard(args.chapter, args.window)
    markdown = render_markdown(report)
    if args.write:
        out = ROOT / "state" / "derived" / "pacing" / "dashboard.md"
        write_text(out, markdown)
        print(f"wrote_report: {rel(out)}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
