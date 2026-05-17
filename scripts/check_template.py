from __future__ import annotations

import ast
import sys
from pathlib import Path

from _common import ROOT
from validate_event_ledger import validate as validate_ledger


REQUIRED_PATHS = [
    "AGENTS.md",
    "README.md",
    ".gitignore",
    ".env.example",
    "setup_report.md",
    "bible/canon.md",
    "bible/worldview.md",
    "bible/rules.md",
    "bible/style_guide.md",
    "bible/characters.yaml",
    "bible/relationships.yaml",
    "bible/factions.yaml",
    "bible/locations.yaml",
    "bible/timeline.yaml",
    "bible/glossary.yaml",
    "bible/open_questions.md",
    "bible/change_log.md",
    "outline/premise.md",
    "outline/total_arc.md",
    "outline/volume_01.md",
    "outline/gate_a_3_chapters.md",
    "outline/gate_b_10_chapters.md",
    "outline/chapter_briefs/v01_c001.md",
    "ops/roles.yaml",
    "ops/model_routing.yaml",
    "ops/gate_rules.yaml",
    "ops/stop_rules.yaml",
    "ops/process_budget.yaml",
    "ops/privacy_checklist.md",
    "ops/style_borrowing_policy.md",
    "ops/automation_policy.md",
    "schemas/event_ledger.schema.json",
    "schemas/character.schema.json",
    "schemas/thread.schema.json",
    "templates/questionnaire_answers.md",
    "templates/chapter_brief.md",
    "scripts/template_init.py",
    "scripts/apply_questionnaire.py",
    "scripts/new_chapter.py",
    "scripts/start_chapter.py",
    "scripts/append_event.py",
    "scripts/record_decision.py",
    "scripts/project_status.py",
]


def check_scripts() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}: syntax error: {exc}")
    return errors


def main() -> int:
    errors: list[str] = []
    for item in REQUIRED_PATHS:
        if not (ROOT / item).exists():
            errors.append(f"missing required path: {item}")

    errors.extend(check_scripts())
    errors.extend(f"event ledger: {error}" for error in validate_ledger(ROOT / "state" / "event_ledger.jsonl"))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: template structure, scripts, and event ledger are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
