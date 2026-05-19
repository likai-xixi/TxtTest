from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import context_quality_path


MARKER_RE = re.compile(r"\[(object|ability):([A-Za-z0-9_.-]+)\]")


def authorized_ids(chapter: str) -> tuple[set[str], set[str]]:
    quality = read_json(context_quality_path(chapter), {})
    return (
        {str(item) for item in quality.get("object_ids", []) if str(item).strip()},
        {str(item) for item in quality.get("ability_ids", []) if str(item).strip()},
    )


def evaluate(chapter: str) -> dict[str, Any]:
    volume, chapter_file = chapter_parts(chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    if not chapter_path.exists() or not read_text(chapter_path).strip():
        raise FileNotFoundError(f"missing non-empty official chapter: {chapter_path.relative_to(ROOT)}")
    text = read_text(chapter_path)
    objects, abilities = authorized_ids(chapter)
    used_objects: list[str] = []
    used_abilities: list[str] = []
    blockers: list[str] = []
    for kind, item_id in MARKER_RE.findall(text):
        if kind == "object":
            used_objects.append(item_id)
            if item_id not in objects:
                blockers.append(f"unauthorized object marker: {item_id}")
        else:
            used_abilities.append(item_id)
            if item_id not in abilities:
                blockers.append(f"unauthorized ability marker: {item_id}")
    l34_markers = sorted(set(re.findall(r"\bL[34]\b", text)))
    if l34_markers:
        brief = read_text(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md")
        if not re.search(r"\bL[34]\b", brief):
            blockers.append("official chapter contains L3/L4 marker not authorized by the brief")
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "READY" if not blockers else "NOT_READY",
        "official_chapter": {"path": chapter_path.relative_to(ROOT).as_posix()},
        "authorized_object_ids": sorted(objects),
        "authorized_ability_ids": sorted(abilities),
        "used_object_ids": sorted(set(used_objects)),
        "used_ability_ids": sorted(set(used_abilities)),
        "l34_markers": l34_markers,
        "blockers": blockers,
        "warnings": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Element Usage: {report['chapter']}",
        "",
        f"status: {report['status']}",
        "",
        "## Used Objects",
        "",
        *(f"- {item}" for item in report["used_object_ids"]),
    ]
    if not report["used_object_ids"]:
        lines.append("- none")
    lines.extend(["", "## Used Abilities", ""])
    lines.extend(f"- {item}" for item in report["used_ability_ids"])
    if not report["used_ability_ids"]:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in report["blockers"])
    if not report["blockers"]:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check official chapter object/ability/mechanism usage against the brief-scoped context.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args.chapter)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.write:
        base = ROOT / "reviews" / args.chapter
        write_json(base / "element_usage.json", report)
        write_text(base / "element_usage.md", render_markdown(report))
        print(f"wrote: {(base / 'element_usage.json').relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
