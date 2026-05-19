from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from record_idea_selection import (
    CHOICES,
    REQUIRED_FIELDS,
    core_fields,
    direction_sections,
    field_value,
    require_ready_lab,
    validate_idea_id,
)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    _lab, contents = require_ready_lab(args.id)
    fields = core_fields(args, contents)
    source = args.mixed_strategy if args.choice == "Mixed" else direction_sections(contents["codex_synthesis.md"]).get(args.choice, "")
    return {
        "schema_version": 1,
        "idea_id": args.id,
        "choice": args.choice,
        "status": "READY_TO_PREVIEW",
        "hook": field_value(source, "一句话卖点") or field_value(source, "涓€鍙ヨ瘽鍗栫偣"),
        "protagonist_desire": field_value(source, "主角欲望") or field_value(source, "涓昏娆叉湜"),
        "core_conflict": field_value(source, "核心冲突") or field_value(source, "鏍稿績鍐茬獊"),
        "fields": fields,
        "red_lines": fields.get("forbidden_changes", ""),
        "open_questions": fields.get("open_questions_allowed", ""),
        "writes": [
            "state/idea_lab/{idea_id}/selection.json",
            "state/idea_lab/{idea_id}/core_setting_freeze.json",
            "state/idea_lab/{idea_id}/core_setting_freeze.md",
            "outline/premise.md",
            "bible/rules.md",
            "bible/characters.yaml",
        ],
        "will_not_write": ["bible/canon.md", "chapters/", "state/event_ledger.jsonl"],
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"# Freeze Preview: {report['idea_id']}")
    print()
    print(f"choice: {report['choice']}")
    print(f"status: {report['status']}")
    print()
    print("## Selected Direction")
    print(f"- hook: {report.get('hook') or 'none'}")
    print(f"- protagonist_desire: {report.get('protagonist_desire') or 'none'}")
    print(f"- core_conflict: {report.get('core_conflict') or 'none'}")
    print()
    print("## Core Fields")
    for key, label in REQUIRED_FIELDS.items():
        print(f"- {key} ({label}): {report['fields'].get(key) or 'MISSING'}")
    print()
    print("## Red Lines")
    print(report.get("red_lines") or "none")
    print()
    print("## Still Open")
    print(report.get("open_questions") or "none")
    print()
    print("## Writes If idea-select Runs")
    for item in report["writes"]:
        print(f"- {item.format(idea_id=report['idea_id'])}")
    print()
    print("## Will Not Write")
    for item in report["will_not_write"]:
        print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview the core setting freeze before idea-select.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
