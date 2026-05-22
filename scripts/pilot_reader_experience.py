from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, write_json, write_text
from artifact_integrity import file_ref, validate_chapter_shape, validate_current_ref, validate_reader_reward_gate
from health_report import load_events


def gate_chapters(gate: str, to_chapter: str | None = None) -> list[str]:
    if gate.upper() != "A":
        raise ValueError("pilot-reader-experience currently supports Gate A only")
    if not to_chapter:
        last = 3
    else:
        volume, _chapter_file = chapter_parts(to_chapter)
        last = chapter_number(to_chapter)
        if volume != "v01" or last > 3:
            raise ValueError("--to for pilot health must be within v01_c001..v01_c003")
    return [f"v01_c{number:03d}" for number in range(1, last + 1)]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def report_for(gate: str, to_chapter: str | None = None) -> dict[str, Any]:
    chapters = gate_chapters(gate, to_chapter)
    events = load_events(3)
    counts = Counter(event.get("type") for event in events if event.get("chapter") in chapters)
    blockers: list[str] = []
    warnings: list[str] = []
    chapter_items: list[dict[str, Any]] = []
    shape_keys: list[str] = []
    matched_chapters = 0
    action_chapters = 0
    world_rule_chapters = 0

    for chapter in chapters:
        gate_path = ROOT / "reviews" / chapter / "reader_reward_gate.json"
        shape_path = ROOT / "reviews" / chapter / "chapter_shape.json"
        reward, reward_failures = validate_reader_reward_gate(chapter)
        shape, shape_failures = validate_chapter_shape(chapter)
        blockers.extend(f"{chapter}: cannot trust reader reward evidence: {failure}" for failure in reward_failures)
        blockers.extend(f"{chapter}: cannot trust chapter shape evidence: {failure}" for failure in shape_failures)
        reward_status = str(reward.get("status", "MISSING")).upper() if isinstance(reward, dict) else "MALFORMED"
        matched = reward.get("matched_evidence_quotes") if isinstance(reward, dict) else []
        raw_contract = reward.get("contract") if isinstance(reward, dict) else None
        contract = raw_contract if isinstance(raw_contract, dict) else {}
        shape_key = str(shape.get("shape_key", "")) if isinstance(shape, dict) else ""
        if shape_key:
            shape_keys.append(shape_key)
        if matched:
            matched_chapters += 1
        if str(contract.get("protagonist_action", "")).strip():
            action_chapters += 1
        if str(contract.get("world_rule", "")).strip():
            world_rule_chapters += 1
        if reward_status not in {"READY", "WARNING", "ACCEPTED_BY_HUMAN"}:
            blockers.append(f"{chapter}: reader_reward_gate is {reward_status}")
        if not matched:
            blockers.append(f"{chapter}: missing matched reader reward evidence quote")
        if not str(contract.get("protagonist_action", "")).strip():
            blockers.append(f"{chapter}: missing protagonist active action in reward contract")
        if not str(contract.get("world_rule", "")).strip():
            warnings.append(f"{chapter}: missing Story Card world rule evidence in reward contract")
        chapter_items.append(
            {
                "chapter": chapter,
                "reader_reward_gate": {**file_ref(gate_path), "status": reward_status},
                "matched_evidence_count": len(matched) if isinstance(matched, list) else 0,
                "chapter_shape": {**file_ref(shape_path), "shape_key": shape_key},
            }
        )

    if counts["character_decision"] < 1:
        blockers.append("Gate A pilot lacks a character_decision event; protagonist agency is unproven")
    if counts["rule_reveal"] < 1 and counts["world_fact"] < 1:
        blockers.append("Gate A pilot lacks rule_reveal/world_fact event; world rule scene test is unproven")
    if counts["relationship_change"] < 1:
        warnings.append("Gate A pilot has no relationship_change event yet")
    if counts["thread_paid_off"] < 1 and counts["thread_advanced"] < 1:
        blockers.append("Gate A pilot opens suspense without a thread_advanced/thread_paid_off event")
    if len(chapters) >= 3 and len(shape_keys) == len(chapters) and len(set(shape_keys)) == 1:
        blockers.append("Gate A pilot repeats the same chapter shape across all checked chapters")

    sustainability_checks = {
        "protagonist_established": counts["character_decision"] >= 2 and action_chapters >= 2,
        "next_read_reason": matched_chapters >= 2 and counts["thread_advanced"] + counts["thread_paid_off"] >= 1,
        "world_anomaly_differentiated": counts["rule_reveal"] + counts["world_fact"] >= 1 and world_rule_chapters >= 1,
        "reader_promise_delivered": matched_chapters >= 2,
        "hundred_chapter_fun_potential": bool(shape_keys) and len(set(shape_keys)) >= 2,
    }
    failed = [key for key, ok in sustainability_checks.items() if not ok]
    for key in failed:
        blockers.append(f"Gate A cannot continue: {key} is not proven")
    if not failed and not blockers:
        recommendation = "continue"
    elif len(failed) >= 4:
        recommendation = "stop"
    elif len(failed) >= 2:
        recommendation = "reopen_direction"
    else:
        recommendation = "rework"

    status = "BLOCKED" if blockers else ("WARNING" if warnings else "READY")
    return {
        "schema_version": 1,
        "gate": gate.upper(),
        "through": chapters[-1] if chapters else "",
        "generated_at": now_iso(),
        "status": status,
        "chapters": chapter_items,
        "event_counts": dict(sorted(counts.items())),
        "source_event_ledger": file_ref(ROOT / "state" / "event_ledger.jsonl"),
        "sustainability_checks": sustainability_checks,
        "decision_recommendation": recommendation,
        "decision_reasons": failed or ["Gate A evidence supports continuing to chapter 4."],
        "blockers": blockers,
        "warnings": warnings,
        "writes_canon": False,
        "writes_event_ledger": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Pilot Reader Experience: Gate {report['gate']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        "",
        "## Chapters",
        "",
    ]
    for item in report.get("chapters", []):
        lines.append(
            f"- {item['chapter']}: reward={item['reader_reward_gate']['status']}, "
            f"quotes={item['matched_evidence_count']}, shape={item['chapter_shape']['shape_key'] or 'missing'}"
        )
    lines.extend(["", "## Event Counts", ""])
    counts = report.get("event_counts") or {}
    lines.extend(f"- {key}: {value}" for key, value in counts.items()) if counts else lines.append("- none")
    lines.extend(["", "## Gate A Decision Recommendation", ""])
    lines.append(f"- recommendation: {report.get('decision_recommendation', '')}")
    for key, value in (report.get("sustainability_checks") or {}).items():
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    lines.extend(["", "## Decision Reasons", ""])
    lines.extend(f"- {item}" for item in report.get("decision_reasons") or ["none"])
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {item}" for item in values) if values else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Gate A three-chapter reader experience evidence.")
    parser.add_argument("gate", choices=["A", "a"])
    parser.add_argument("--to", default=None, help="Check the pilot only through this chapter, max v01_c003.")
    parser.add_argument("--write", action="store_true", help="Write state/gates/gate_a_reader_experience.* evidence.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = report_for(args.gate, args.to)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    source_failures = validate_current_ref(report.get("source_event_ledger"), ROOT / "state" / "event_ledger.jsonl", "source_event_ledger")
    if source_failures:
        report["blockers"].extend(source_failures)
        report["status"] = "BLOCKED"
    if args.write:
        write_json(ROOT / "state" / "gates" / "gate_a_reader_experience.json", report)
        write_text(ROOT / "state" / "gates" / "gate_a_reader_experience.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
