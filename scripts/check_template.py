from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from _common import ROOT
from schema_validate import validate_json_file, validate_jsonl_file, validate_schema_document
from validate_event_ledger import validate as validate_ledger
from workflow_errors import format_issue

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


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
    "bible/objects.yaml",
    "bible/abilities.yaml",
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
    "schemas/core_setting_freeze.schema.json",
    "schemas/agent_review_manifest.schema.json",
    "schemas/context_quality.schema.json",
    "schemas/selection.schema.json",
    "schemas/landing.schema.json",
    "templates/questionnaire_answers.md",
    "templates/idea_seed.md",
    "templates/chapter_brief.md",
    "templates/brief_candidate_selection.md",
    "templates/candidate_selection.md",
    "templates/ai_taste.md",
    "templates/web_satisfaction.md",
    "templates/retention_risk.md",
    "templates/originality.md",
    "templates/similarity_risk.md",
    "templates/reader_response_gate_a.json",
    "templates/reader_response_gate_b.json",
    "templates/model_disagreement.md",
    "templates/continuity.md",
    "templates/gate_c_assessment.md",
    "templates/gate_e_300w_assessment.md",
    "state/stops/project_locks.json",
    "state/idea_lab",
    "docs/editor_commands.md",
    "scripts/template_init.py",
    "scripts/apply_questionnaire.py",
    "scripts/run_deepseek_idea.py",
    "scripts/run_deepseek_brief.py",
    "scripts/deepseek_client.py",
    "scripts/core_setting_freeze.py",
    "scripts/record_idea_selection.py",
    "scripts/record_agent_review_manifest.py",
    "scripts/record_agent_run.py",
    "scripts/audit.py",
    "scripts/ci.py",
    "scripts/build_brief_pack.py",
    "scripts/build_context_pack.py",
    "scripts/build_derived_state.py",
    "scripts/context_governance.py",
    "scripts/gate_policy.py",
    "scripts/context_pack_quality.py",
    "scripts/record_brief_selection.py",
    "scripts/record_brief_landing.py",
    "scripts/new_chapter.py",
    "scripts/novel.py",
    "scripts/start_chapter.py",
    "scripts/append_event.py",
    "scripts/record_decision.py",
    "scripts/project_status.py",
    "scripts/workflow_state.py",
    "scripts/editor_desk.py",
    "scripts/idea_status.py",
    "scripts/deepseek_preflight.py",
    "scripts/workflow_map.py",
    "scripts/brief_diagnose.py",
    "scripts/workflow_errors.py",
    "scripts/schema_validate.py",
    "scripts/preview_plan.py",
    "scripts/context_diff.py",
    "scripts/candidate_compare.py",
    "scripts/gate_rehearsal.py",
    "scripts/stale_check.py",
    "scripts/workflow_smoke.py",
    "scripts/diff_scope_check.py",
    "scripts/continuity_check.py",
    "scripts/run_deepseek_generate.py",
    "scripts/run_deepseek_review.py",
    "scripts/compare_model_reviews.py",
    "scripts/gate_check.py",
    "scripts/chapter_evidence.py",
    "scripts/element_context.py",
    "scripts/record_gate_decision.py",
    "scripts/record_candidate_selection.py",
    "scripts/record_chapter_landing.py",
    "scripts/reader_test.py",
    "scripts/stop_check.py",
    "scripts/project_lock.py",
    "scripts/project_doctor.py",
    "scripts/next_prompt.py",
    "scripts/brief_contract.py",
    "scripts/brief_check.py",
    "scripts/pacing_check.py",
    "scripts/event_suggest.py",
    "scripts/canon_propose.py",
    "scripts/health_report.py",
    "scripts/review_manifest.py",
    "scripts/self_test.py",
    "tests/test_workflow_guards.py",
    "tests/test_governance_refactors.py",
]

SCHEMA_PATHS = [
    "schemas/event_ledger.schema.json",
    "schemas/character.schema.json",
    "schemas/thread.schema.json",
    "schemas/core_setting_freeze.schema.json",
    "schemas/agent_review_manifest.schema.json",
    "schemas/context_quality.schema.json",
    "schemas/selection.schema.json",
    "schemas/landing.schema.json",
]

RUNTIME_SCHEMA_GLOBS = [
    ("state/idea_lab/*/core_setting_freeze.json", "schemas/core_setting_freeze.schema.json"),
    ("state/idea_lab/*/agent_review_manifest.json", "schemas/agent_review_manifest.schema.json"),
    ("state/idea_lab/*/selection.json", "schemas/selection.schema.json"),
    ("state/derived/context_quality/*.json", "schemas/context_quality.schema.json"),
    ("state/selections/*.json", "schemas/selection.schema.json"),
    ("reviews/*/brief_landing.json", "schemas/landing.schema.json"),
    ("reviews/*/chapter_landing.json", "schemas/landing.schema.json"),
]


def check_scripts() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}: syntax error: {exc}")
    return errors


def check_source_log() -> list[str]:
    path = ROOT / "references" / "source_log.yaml"
    errors: list[str] = []
    if yaml is None:
        return ["source_log: PyYAML is required to validate references/source_log.yaml"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"source_log: invalid YAML: {exc}"]
    if data is None:
        return []
    if not isinstance(data, dict):
        return ["source_log: top-level value must be a mapping"]
    sources = data.get("sources", [])
    if sources in (None, []):
        return []
    if not isinstance(sources, list):
        return ["source_log: sources must be a list"]
    placeholders = {"待定", "待填", "TODO", "source_id", "寰呭畾"}
    for index, item in enumerate(sources, start=1):
        if not isinstance(item, dict):
            errors.append(f"source_log: source #{index} must be a mapping")
            continue
        for key, value in item.items():
            values = value if isinstance(value, list) else [value]
            for entry in values:
                if isinstance(entry, str) and any(marker in entry for marker in placeholders):
                    errors.append(f"source_log: source #{index} field {key} contains placeholder text")
    return errors


def check_roles_yaml() -> list[str]:
    path = ROOT / "ops" / "roles.yaml"
    if yaml is None:
        return ["roles: PyYAML is required to validate ops/roles.yaml"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"roles: invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return ["roles: top-level value must be a mapping"]
    required = {"brief", "draft", "candidate", "review", "continuity", "decision", "gate", "revision", "state", "chapter", "idea", "maintenance"}
    missing = sorted(required - set(data))
    errors = [f"roles: missing role {role}" for role in missing]
    for role, config in data.items():
        if not isinstance(config, dict) or not isinstance(config.get("allow"), list) or not config["allow"]:
            errors.append(f"roles: role {role} must define a non-empty allow list")
    return errors


def check_json_files(paths: list[str]) -> list[str]:
    errors: list[str] = []
    for path_text in paths:
        path = ROOT / path_text
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(format_issue("SCHEMA", f"invalid JSON: {exc}", path_text))
            continue
        if not isinstance(data, dict):
            errors.append(format_issue("SCHEMA", "top-level value must be an object", path_text))
            continue
        for error in validate_schema_document(data):
            errors.append(format_issue("SCHEMA", error, path_text))
    return errors


def check_runtime_json_against_schemas() -> list[str]:
    errors: list[str] = []
    for pattern, schema_text in RUNTIME_SCHEMA_GLOBS:
        schema = ROOT / schema_text
        for path in sorted(ROOT.glob(pattern)):
            for item in validate_json_file(path, schema):
                errors.append(format_issue(item["category"], item["message"], item.get("path")))
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if ledger.exists():
        for item in validate_jsonl_file(ledger, ROOT / "schemas" / "event_ledger.schema.json"):
            errors.append(format_issue(item["category"], item["message"], item.get("path")))
    return errors


def check_yaml_root(path_text: str, expected_key: str) -> list[str]:
    path = ROOT / path_text
    if yaml is None:
        return [f"{path_text}: PyYAML is required to validate YAML"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path_text}: invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return [f"{path_text}: top-level value must be a mapping"]
    if expected_key not in data or not isinstance(data[expected_key], list):
        return [f"{path_text}: must define `{expected_key}: []` or a list"]
    return []


def main() -> int:
    errors: list[str] = []
    for item in REQUIRED_PATHS:
        if not (ROOT / item).exists():
            errors.append(f"missing required path: {item}")

    errors.extend(check_scripts())
    errors.extend(check_source_log())
    errors.extend(check_roles_yaml())
    errors.extend(check_json_files(SCHEMA_PATHS))
    errors.extend(check_runtime_json_against_schemas())
    errors.extend(check_yaml_root("bible/objects.yaml", "objects"))
    errors.extend(check_yaml_root("bible/abilities.yaml", "abilities"))
    errors.extend(f"event ledger: {error}" for error in validate_ledger(ROOT / "state" / "event_ledger.jsonl"))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: template structure, scripts, and event ledger are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
