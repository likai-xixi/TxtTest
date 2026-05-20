from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, gate_decision, read_text
from gate_config import load_gate_configs
from reader_personality_contracts import load_reader_promise, validate_reader_promise
from workflow_errors import issue


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def shipped_chapters(limit: int) -> list[str]:
    shipped: list[str] = []
    for idx in range(1, limit + 1):
        chapter = f"v01_c{idx:03d}"
        decision_path = ROOT / "reviews" / chapter / "decision.md"
        if decision_path.exists() and "decision: Ship" in read_text(decision_path):
            shipped.append(chapter)
    return shipped


def count_reader_responses(path_text: str | None) -> int:
    if not path_text:
        return 0
    path = ROOT / path_text
    if not path.exists():
        return 0
    return len([item for item in path.glob("*.json") if item.is_file()])


def context_quality_gaps(chapters: list[str]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for chapter in chapters:
        path = ROOT / "state" / "derived" / "context_quality" / f"{chapter}.json"
        if not path.exists():
            gaps.append(issue("MISSING", "context quality report is missing", rel(path)))
            continue
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            gaps.append(issue("SCHEMA", f"context quality JSON is invalid: {exc}", rel(path)))
            continue
        if data.get("status") != "READY":
            gaps.append(issue("BLOCKER", f"context quality status is {data.get('status')!r}", rel(path)))
    return gaps


def reader_experience_gaps(gate: str) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for error in validate_reader_promise(load_reader_promise(), require_ready=True):
        gaps.append(issue("BLOCKER", f"reader promise not ready: {error}", "state/project_reader_promise.json"))
    for rel_path in (
        "state/derived/personality/protagonist.json",
        "state/derived/protagonist_progression.json",
        "state/derived/world_reveal_ledger.json",
        "state/derived/suspense_ledger.json",
    ):
        path = ROOT / rel_path
        if not path.exists():
            gaps.append(issue("MISSING", "reader experience derived ledger is missing", rel_path))
            continue
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            gaps.append(issue("SCHEMA", f"reader experience ledger invalid JSON: {exc}", rel_path))
            continue
        blockers = data.get("blockers", []) if isinstance(data, dict) else ["malformed ledger"]
        if blockers:
            gaps.append(issue("BLOCKER", f"reader experience ledger blockers: {', '.join(map(str, blockers[:3]))}", rel_path))
    return gaps


def rehearse(gate: str) -> dict[str, Any]:
    gate = gate.upper()
    configs = load_gate_configs()
    config = configs[gate]
    needed = int(config["needed"])
    shipped = shipped_chapters(needed)
    issues: list[dict[str, Any]] = []

    if len(shipped) < needed:
        issues.append(issue("MISSING", f"shipped chapters {len(shipped)}/{needed}"))

    criteria_path = ROOT / str(config["criteria"])
    if not criteria_path.exists():
        issues.append(issue("MISSING", "gate criteria file is missing", rel(criteria_path)))

    synthesis = config.get("reader_synthesis")
    if synthesis:
        synthesis_path = ROOT / synthesis
        if not synthesis_path.exists() or not read_text(synthesis_path).strip():
            issues.append(issue("MISSING", "reader synthesis is missing or empty", rel(synthesis_path)))
    required_responses = int(config.get("min_reader_responses") or 0)
    responses = count_reader_responses(config.get("reader_response_dir"))
    if responses < required_responses:
        issues.append(issue("MISSING", f"reader responses {responses}/{required_responses}", str(config.get("reader_response_dir"))))

    assessment = config.get("assessment")
    if assessment:
        path = ROOT / str(assessment)
        if not path.exists() or not read_text(path).strip():
            issues.append(issue("MISSING", "required gate assessment is missing or empty", rel(path)))
        else:
            text = read_text(path)
            for section in config.get("assessment_sections") or []:
                if section and section not in text:
                    issues.append(issue("MISSING", f"assessment section missing: {section}", rel(path)))

    issues.extend(context_quality_gaps(shipped))
    issues.extend(reader_experience_gaps(gate))
    return {
        "gate": gate,
        "status": "READY_FOR_HUMAN_DECISION" if not issues else "REHEARSAL_NOT_READY",
        "threshold_chapters": needed,
        "shipped_chapters": shipped,
        "shipped_count": len(shipped),
        "reader_responses": responses,
        "required_reader_responses": required_responses,
        "recorded_gate_decision": gate_decision(gate.lower()) or None,
        "issues": issues,
        "writes_gate_decision": False,
    }


def print_text(result: dict[str, Any]) -> None:
    print(f"# Gate {result['gate']} Rehearsal")
    print(f"status: {result['status']}")
    print(f"shipped_chapters: {result['shipped_count']}/{result['threshold_chapters']}")
    print(f"reader_responses: {result['reader_responses']}/{result['required_reader_responses']}")
    print("writes_gate_decision: false")
    print()
    print("## Evidence Gaps")
    if not result["issues"]:
        print("- none")
    for item in result["issues"]:
        text = f"{item['category']}: {item['message']}"
        if item.get("path"):
            text += f" ({item['path']})"
        print(f"- {text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview gate readiness without recording a gate decision.")
    parser.add_argument("gate", choices=sorted(load_gate_configs()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = rehearse(args.gate)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
