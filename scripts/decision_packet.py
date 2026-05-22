from __future__ import annotations

import argparse
import json
from typing import Any

from candidate_compare import compare as compare_candidates
from gate_rehearsal import rehearse as rehearse_gate
from revision_closure import evaluate as evaluate_revision_closure
from stale_check import stale_summary
from workflow_state import dashboard


def add_issue(target: list[str], value: str | None) -> None:
    if value and value.strip():
        target.append(value.strip())


def build_packet(chapter: str | None, gate: str, brief: bool) -> dict[str, Any]:
    project = dashboard()
    stale = stale_summary(chapter)
    gate_report = rehearse_gate(gate)
    blockers: list[str] = []
    warnings: list[str] = []

    if project.get("story_status") != "STORY_READY":
        add_issue(blockers, str(project.get("blocker") or "story is not ready"))
    if stale.get("status") == "SCHEMA":
        add_issue(blockers, "stale-check has schema errors")
    elif stale.get("status") in {"STALE", "MISSING"}:
        add_issue(warnings, f"stale-check status is {stale.get('status')}")
    if gate_report.get("status") != "READY_FOR_HUMAN_DECISION":
        add_issue(warnings, f"Gate {gate.upper()} rehearsal is {gate_report.get('status')}")

    candidate_report: dict[str, Any] | None = None
    revision_report: dict[str, Any] | None = None
    if chapter:
        candidate_report = compare_candidates(chapter, brief)
        if candidate_report.get("status") != "READY":
            add_issue(warnings, f"{chapter} candidate comparison is {candidate_report.get('status')}")
        revision_report = evaluate_revision_closure(chapter)
        if revision_report.get("status") == "BLOCKED":
            blockers.extend(str(item) for item in revision_report.get("blockers", []))

    status = "BLOCKED" if blockers else ("WARNING" if warnings else "READY")
    next_actions = []
    if blockers:
        next_actions.extend(blockers[:3])
    if not next_actions and warnings:
        next_actions.extend(warnings[:3])
    if not next_actions:
        next_actions.append("Human editor can make the next decision with current evidence.")

    return {
        "schema_version": 1,
        "status": status,
        "chapter": chapter,
        "gate": gate.upper(),
        "mode": "brief" if brief else "chapter",
        "project": {
            "phase_id": project.get("phase_id"),
            "story_status": project.get("story_status"),
            "blocker": project.get("blocker"),
            "human_action": project.get("human_action"),
            "risk_flags": project.get("risk_flags", []),
        },
        "stale": stale,
        "gate_rehearsal": {
            "status": gate_report.get("status"),
            "shipped_count": gate_report.get("shipped_count"),
            "threshold_chapters": gate_report.get("threshold_chapters"),
            "issue_count": len(gate_report.get("issues", [])),
        },
        "candidate_compare": candidate_report,
        "revision_closure": revision_report,
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": next_actions,
        "writes_canon": False,
        "writes_event_ledger": False,
        "writes_selection": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Decision Packet",
        "",
        f"status: {report['status']}",
        f"gate: {report['gate']}",
        f"chapter: {report.get('chapter') or 'n/a'}",
        f"mode: {report.get('mode')}",
        "",
        "## Project",
        "",
    ]
    project = report.get("project") or {}
    for key in ("phase_id", "story_status", "blocker", "human_action"):
        lines.append(f"- {key}: {project.get(key)}")
    lines.extend(["", "## Evidence Snapshot", ""])
    lines.append(f"- stale: {(report.get('stale') or {}).get('status')}")
    gate = report.get("gate_rehearsal") or {}
    lines.append(
        "- gate_rehearsal: {status} ({shipped}/{needed})".format(
            status=gate.get("status"),
            shipped=gate.get("shipped_count"),
            needed=gate.get("threshold_chapters"),
        )
    )
    candidate = report.get("candidate_compare")
    if isinstance(candidate, dict):
        lines.append(f"- candidate_recommendation: {candidate.get('recommended_choice')}")
    revision = report.get("revision_closure")
    if isinstance(revision, dict):
        lines.append(f"- revision_closure: {revision.get('status')}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings"), ("next_actions", "Next Actions")):
        lines.extend(["", f"## {title}", ""])
        items = report.get(key) or []
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    lines.extend(["", "writes_canon: false", "writes_event_ledger: false", "writes_selection: false"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a no-write editor decision packet from current workflow evidence.")
    parser.add_argument("chapter", nargs="?")
    parser.add_argument("--gate", choices=["A", "B", "C", "E", "F", "G", "H"], default="A")
    parser.add_argument("--brief", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_packet(args.chapter, args.gate, args.brief)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
