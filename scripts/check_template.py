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
    "reader_tests/gate_a_synthesis.md",
    "reader_tests/gate_b_synthesis.md",
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
    "templates/candidate_selection.md",
    "state/stops/project_locks.json",
    "scripts/template_init.py",
    "scripts/apply_questionnaire.py",
    "scripts/new_chapter.py",
    "scripts/novel.py",
    "scripts/start_chapter.py",
    "scripts/append_event.py",
    "scripts/record_decision.py",
    "scripts/project_status.py",
    "scripts/diff_scope_check.py",
    "scripts/continuity_check.py",
    "scripts/run_deepseek_generate.py",
    "scripts/run_deepseek_review.py",
    "scripts/compare_model_reviews.py",
    "scripts/gate_check.py",
    "scripts/chapter_evidence.py",
    "scripts/record_gate_decision.py",
    "scripts/record_candidate_selection.py",
    "scripts/record_chapter_landing.py",
    "scripts/reader_test.py",
    "scripts/stop_check.py",
    "scripts/project_lock.py",
    "scripts/review_manifest.py",
    "scripts/self_test.py",
    "tests/test_workflow_guards.py",
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
