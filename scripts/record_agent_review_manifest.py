from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import ROOT, now_iso, read_json, read_text, write_text
from core_setting_freeze import sha256
from record_idea_selection import (
    AGENT_REVIEW_MANIFEST,
    AGENT_ROLES,
    IDEA_ID_RE,
    validate_agent_review_manifest,
)


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def input_item(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def valid_completed_at(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--completed-at must be ISO-8601") from exc
    return value


def validate_run_hash(path: Path, item: dict, label: str) -> list[str]:
    expected = item.get("sha256")
    if not isinstance(expected, str) or not expected.strip():
        return [f"{label} missing sha256"]
    if not path.exists():
        return [f"{label} missing file: {path.relative_to(ROOT)}"]
    if sha256(path) != expected:
        return [f"{label} hash mismatch: {path.relative_to(ROOT)}"]
    return []


def load_agent_runs(idea_id: str, lab: Path) -> tuple[dict[str, dict], list[str]]:
    path = lab / "agent_runs.json"
    if not path.exists():
        return {}, [f"missing idea-lab agent run metadata: {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    errors: list[str] = []
    if not isinstance(data, dict):
        return {}, ["agent_runs.json must be a JSON object"]
    if data.get("schema_version") != 1:
        errors.append("agent_runs.json schema_version must be 1")
    if data.get("idea_id") != idea_id:
        errors.append("agent_runs.json idea_id mismatch")
    runs = data.get("runs")
    if not isinstance(runs, dict):
        return {}, errors + ["agent_runs.json missing runs mapping"]

    validated: dict[str, dict] = {}
    expected_inputs = [lab / "original_idea.md", lab / "deepseek_idea.md"]
    expected_input_paths = {path.relative_to(ROOT).as_posix(): path for path in expected_inputs}
    for role, filename in AGENT_ROLES.items():
        run = runs.get(role)
        if not isinstance(run, dict):
            errors.append(f"agent_runs.json missing role {role}")
            continue
        if run.get("role") != role:
            errors.append(f"agent_runs.json role mismatch for {role}")
        if not str(run.get("agent_id", "")).strip():
            errors.append(f"agent_runs.json {role} missing agent_id")
        if not valid_iso(run.get("completed_at")):
            errors.append(f"agent_runs.json {role} missing valid completed_at")

        input_files = run.get("input_files")
        if not isinstance(input_files, list):
            errors.append(f"agent_runs.json {role} input_files must be a list")
            input_files = []
        input_by_path = {
            str(item.get("path")): item
            for item in input_files
            if isinstance(item, dict)
        }
        extra_inputs = sorted(set(input_by_path) - set(expected_input_paths))
        if extra_inputs:
            errors.append(f"agent_runs.json {role} has disallowed inputs: {', '.join(extra_inputs)}")
        for rel_path, source in expected_input_paths.items():
            item = input_by_path.get(rel_path)
            if not item:
                errors.append(f"agent_runs.json {role} missing input {rel_path}")
                continue
            errors.extend(validate_run_hash(source, item, f"{role} input {rel_path}"))

        output = run.get("output_file")
        expected_output = lab / filename
        if not isinstance(output, dict):
            errors.append(f"agent_runs.json {role} missing output_file")
        else:
            expected_output_rel = expected_output.relative_to(ROOT).as_posix()
            if output.get("path") != expected_output_rel:
                errors.append(f"agent_runs.json {role} output_file path must be {expected_output_rel}")
            errors.extend(validate_run_hash(expected_output, output, f"{role} output"))
        if role not in validated:
            validated[role] = run
    return validated, errors


def valid_iso(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Record idea-lab multi-agent review provenance.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--completed-at", default=None, type=valid_completed_at)
    args = parser.parse_args()

    lab = ROOT / "state" / "idea_lab" / args.id
    if not lab.exists():
        print(f"ERROR: missing idea lab: {lab.relative_to(ROOT)}", file=sys.stderr)
        return 1

    base_files = [lab / "original_idea.md", lab / "deepseek_idea.md", *(lab / name for name in AGENT_ROLES.values())]
    missing = [path.relative_to(ROOT).as_posix() for path in base_files if not path.exists() or not read_text(path).strip()]
    if missing:
        print(f"ERROR: missing idea-lab agent manifest inputs: {', '.join(missing)}", file=sys.stderr)
        return 1
    runs, run_errors = load_agent_runs(args.id, lab)
    if run_errors:
        for error in run_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    completed_at = args.completed_at or now_iso()
    manifest = {
        "schema_version": 1,
        "idea_id": args.id,
        "recorded_at": now_iso(),
        "inputs": [
            input_item(lab / "original_idea.md"),
            input_item(lab / "deepseek_idea.md"),
        ],
        "reviews": {
            role: {
                "role": role,
                "agent_id": str(runs[role]["agent_id"]),
                "path": (lab / filename).relative_to(ROOT).as_posix(),
                "sha256": sha256(lab / filename),
                "completed_at": runs[role].get("completed_at") or completed_at,
                "agent_run": runs[role],
            }
            for role, filename in AGENT_ROLES.items()
        },
    }
    out = lab / AGENT_REVIEW_MANIFEST
    write_text(out, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    errors = validate_agent_review_manifest(args.id, lab)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
