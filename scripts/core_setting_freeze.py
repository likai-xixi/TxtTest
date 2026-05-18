from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from _common import ROOT, read_json, read_text


FREEZE_JSON = "core_setting_freeze.json"
FREEZE_MD = "core_setting_freeze.md"
SELECTED_POINTER = ROOT / "state" / "idea_lab" / "selected.json"
PLACEHOLDERS = (
    "待定",
    "待填",
    "待评",
    "待生成",
    "待人类确认",
    "TODO",
    "TBD",
    "寰呭畾",
    "寰呭～",
)
REQUIRED_FIELDS = {
    "worldview_core": "世界观核心规则",
    "worldview_hard_limits": "世界观硬边界",
    "protagonist_anomaly_cause": "主角异常原因",
    "protagonist_family": "主角家属/亲密关系",
    "family_stakes": "家属剧情功能与风险",
    "first_three_chapter_constraints": "前三章约束",
    "forbidden_changes": "不可违背红线",
    "open_questions_allowed": "仍可开放的问题",
}
REQUIRED_EVIDENCE_KEYS = (
    "original_idea",
    "deepseek_idea",
    "deepseek_raw",
    "product_founder_review",
    "technical_lead_review",
    "qa_release_review",
    "codex_synthesis",
    "selection",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def has_placeholder(value: object) -> bool:
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    text = str(value or "").strip()
    return not text or any(marker in text for marker in PLACEHOLDERS)


def selected_idea_id() -> str | None:
    if SELECTED_POINTER.exists():
        data = read_json(SELECTED_POINTER, {})
        idea_id = data.get("idea_id")
        return str(idea_id) if idea_id else None

    candidates: list[str] = []
    root = ROOT / "state" / "idea_lab"
    if root.exists():
        for lab in root.iterdir():
            if lab.is_dir() and (lab / FREEZE_JSON).exists():
                candidates.append(lab.name)
    return candidates[0] if len(candidates) == 1 else None


def freeze_path(idea_id: str | None = None) -> Path | None:
    idea = idea_id or selected_idea_id()
    if not idea:
        return None
    return ROOT / "state" / "idea_lab" / idea / FREEZE_JSON


def freeze_markdown_path(idea_id: str | None = None) -> Path | None:
    idea = idea_id or selected_idea_id()
    if not idea:
        return None
    return ROOT / "state" / "idea_lab" / idea / FREEZE_MD


def validate_freeze(idea_id: str | None = None) -> list[str]:
    path = freeze_path(idea_id)
    if path is None:
        return ["core setting freeze is missing; run idea lab and idea-select before opening chapters"]
    if not path.exists():
        return [f"core setting freeze is missing: {path.relative_to(ROOT)}"]

    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"core setting freeze is invalid JSON: {exc}"]

    idea = str(data.get("idea_id") or "")
    if not idea:
        errors.append("core setting freeze missing idea_id")
    if data.get("status") != "LOCKED":
        errors.append("core setting freeze status must be LOCKED")
    if data.get("human_approved") is not True:
        errors.append("core setting freeze must be human_approved")
    for key in ("writes_canon", "writes_chapters", "writes_event_ledger"):
        if data.get(key) is not False:
            errors.append(f"core setting freeze {key} must be false")

    fields = data.get("fields")
    if not isinstance(fields, dict):
        errors.append("core setting freeze missing fields")
        fields = {}
    for key, label in REQUIRED_FIELDS.items():
        if has_placeholder(fields.get(key)):
            errors.append(f"core setting freeze field `{key}` ({label}) is empty or has placeholder text")

    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("core setting freeze missing evidence")
        evidence = {}
    for key in REQUIRED_EVIDENCE_KEYS:
        item = evidence.get(key)
        if not isinstance(item, dict):
            errors.append(f"core setting freeze missing evidence `{key}`")
            continue
        rel = item.get("path")
        expected_sha = item.get("sha256")
        if not rel or not expected_sha:
            errors.append(f"core setting freeze evidence `{key}` must include path and sha256")
            continue
        evidence_path = ROOT / str(rel)
        if not evidence_path.exists():
            errors.append(f"core setting freeze evidence `{key}` missing file: {rel}")
            continue
        actual_sha = sha256(evidence_path)
        if actual_sha != expected_sha:
            errors.append(f"core setting freeze evidence `{key}` changed after freeze: {rel}")

    md = freeze_markdown_path(idea)
    if md is None or not md.exists():
        errors.append("core setting freeze markdown summary is missing")

    return errors


def ensure_ready(idea_id: str | None = None, *, stream=sys.stderr) -> bool:
    errors = validate_freeze(idea_id)
    if not errors:
        return True
    for error in errors:
        print(f"ERROR: {error}", file=stream)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the pre-opening core setting freeze.")
    parser.add_argument("--idea-id", default=None)
    args = parser.parse_args()

    errors = validate_freeze(args.idea_id)
    print("# Core Setting Freeze")
    print()
    if errors:
        print("status: NOT_READY")
        print()
        for error in errors:
            print(f"- {error}")
        return 1
    print("status: READY")
    path = freeze_path(args.idea_id)
    if path:
        print(f"path: {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
