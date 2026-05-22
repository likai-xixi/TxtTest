from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, write_json, write_text
from artifact_integrity import file_ref, validate_chapter_shape, validate_reader_reward_gate
from health_report import gate_risks, infer_last_chapter, load_events


def evaluate(to_chapter: str | None = None) -> dict[str, Any]:
    target = to_chapter or infer_last_chapter()
    max_chapter = chapter_number(target)
    events = load_events(max_chapter)
    counts = Counter(event.get("type") for event in events)
    threads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("type") in {"thread_opened", "thread_advanced", "thread_paid_off"}:
            thread_id = str(event.get("thread_id") or event.get("fact") or event.get("event_id"))
            threads[thread_id].append(event)
    unresolved_ages: list[int] = []
    payoff_intervals: list[int] = []
    for items in threads.values():
        ordered = sorted(items, key=lambda item: chapter_number(str(item["chapter"])))
        opened = chapter_number(str(ordered[0]["chapter"]))
        paid = [chapter_number(str(item["chapter"])) for item in ordered if item.get("type") == "thread_paid_off"]
        if paid:
            payoff_intervals.append(max(paid) - opened)
        else:
            unresolved_ages.append(max_chapter - opened + 1)
    agency_density = 0.0 if max_chapter == 0 else counts["character_decision"] / max_chapter
    setting_debt = counts["rule_reveal"] + counts["object_change"] - counts["thread_paid_off"]
    risks: list[str] = []
    if unresolved_ages and max(unresolved_ages) >= 10:
        risks.append("old_unresolved_thread")
    if agency_density < 0.5 and max_chapter >= 3:
        risks.append("low_agency_density")
    if setting_debt > max(5, max_chapter // 2):
        risks.append("setting_debt_growing")
    if counts["thread_opened"] > counts["thread_paid_off"] + 8:
        risks.append("payoff_backlog")
    reader_ledgers: dict[str, Any] = {}
    for key, rel_path in {
        "protagonist_progression": "state/derived/protagonist_progression.json",
        "world_reveal": "state/derived/world_reveal_ledger.json",
        "suspense": "state/derived/suspense_ledger.json",
    }.items():
        path = ROOT / rel_path
        data = read_json(path, {}) if path.exists() else {}
        blockers = data.get("blockers", []) if isinstance(data, dict) else []
        reader_ledgers[key] = {"path": rel_path, "exists": path.exists(), "blockers": blockers}
        if blockers:
            risks.append(f"{key}_blocker")
    rolling_blockers: list[str] = []
    rolling_warnings: list[str] = []
    if max_chapter >= 10:
        volume = target[:3]
        start = max(1, max_chapter - 4)
        window_chapters = [f"{volume}_c{number:03d}" for number in range(start, max_chapter + 1)]
        gate_items = [validate_reader_reward_gate(chapter) for chapter in window_chapters]
        shape_items = [validate_chapter_shape(chapter) for chapter in window_chapters]
        for chapter, (_, failures) in zip(window_chapters, gate_items):
            rolling_blockers.extend(f"{chapter}: cannot trust reader_reward_gate: {failure}" for failure in failures)
        for chapter, (_, failures) in zip(window_chapters, shape_items):
            rolling_blockers.extend(f"{chapter}: cannot trust chapter_shape: {failure}" for failure in failures)
        gates = [data for data, failures in gate_items if not failures]
        shapes = [data for data, failures in shape_items if not failures]
        no_payoff = sum(
            1
            for gate in gates
            if not (isinstance(gate, dict) and gate.get("matched_evidence_quotes"))
        ) + (len(window_chapters) - len(gates))
        passive = sum(
            1
            for event_chapter in window_chapters
            if not any(event.get("chapter") == event_chapter and event.get("type") == "character_decision" for event in events)
        )
        low_carriers = [str((gate.get("contract") or {}).get("low_drama_carrier", "")).strip().lower() for gate in gates]
        low_drama_repeat = max((low_carriers.count(item) for item in set(low_carriers) if item and item not in {"none", "无"}), default=0)
        high_pressure_no_release = sum(
            1
            for gate in gates
            if any(marker in str((gate.get("contract") or {}).get("pressure_level", "")) for marker in ("H3", "H4", "W3", "W4", "高压", "强压", "爆发"))
            and not str((gate.get("contract") or {}).get("release_valve", "")).strip()
        )
        shape_bodies = [shape.get("shape") if isinstance(shape.get("shape"), dict) else {} for shape in shapes]
        hook_types = [str(shape.get("hook", "")).strip() for shape in shape_bodies]
        hook_repeat = max((hook_types.count(item) for item in set(hook_types) if item and item != "unclear"), default=0)
        shape_keys = [str(shape.get("shape_key", "")).strip() for shape in shapes]
        shape_repeat = max((shape_keys.count(item) for item in set(shape_keys) if item), default=0)
        reactive_shapes = sum(1 for shape in shape_bodies if shape.get("protagonist_position") == "reactive")
        explanation_only = sum(1 for shape in shape_bodies if shape.get("exposition_load") == "explanation_only")
        opened = sum(1 for event in events if event.get("chapter") in window_chapters and event.get("type") == "thread_opened")
        advanced_or_paid = sum(1 for event in events if event.get("chapter") in window_chapters and event.get("type") in {"thread_advanced", "thread_paid_off"})
        world_test = sum(1 for event in events if event.get("chapter") in window_chapters and event.get("type") == "rule_reveal")
        if high_pressure_no_release >= 3:
            rolling_blockers.append("recent 5-chapter window has 3+ high-pressure chapters without release valves")
        if passive >= 3:
            rolling_blockers.append(f"recent 5-chapter window has {passive} chapters without character_decision")
        if reactive_shapes >= 2:
            rolling_blockers.append("recent 5-chapter window has 2+ reactive protagonist chapter shapes")
        if no_payoff >= 3:
            rolling_blockers.append(f"recent 5-chapter window has {no_payoff} chapters without matched reader payoff evidence")
        if low_drama_repeat >= 3:
            rolling_blockers.append("recent 5-chapter window repeats the same low-drama carrier 3+ times")
        if hook_repeat >= 3:
            rolling_blockers.append("recent 5-chapter window repeats the same chapter-hook type 3+ times")
        if shape_repeat >= 3:
            rolling_blockers.append("recent 5-chapter window repeats the same full chapter shape 3+ times")
        if explanation_only >= 2:
            rolling_blockers.append("recent 5-chapter window has 2+ explanation-only chapter shapes")
        if opened >= 3 and advanced_or_paid == 0:
            rolling_blockers.append("recent 5-chapter window opens suspense threads without advancement or payoff")
        if world_test == 0:
            rolling_warnings.append("recent 5-chapter window has no rule_reveal event; world rules may be explanation-only")
    status = "BLOCKED" if rolling_blockers else ("WARNING" if risks or rolling_warnings else "READY")
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "through": target,
        "chapters": max_chapter,
        "source_event_ledger": file_ref(ROOT / "state" / "event_ledger.jsonl"),
        "source_reader_promise": file_ref(ROOT / "state" / "project_reader_promise.json"),
        "rolling_input_refs": [
            {
                "chapter": f"{target[:3]}_c{number:03d}",
                "reader_reward_gate": file_ref(ROOT / "reviews" / f"{target[:3]}_c{number:03d}" / "reader_reward_gate.json"),
                "chapter_shape": file_ref(ROOT / "reviews" / f"{target[:3]}_c{number:03d}" / "chapter_shape.json"),
            }
            for number in range(max(1, max_chapter - 4), max_chapter + 1)
        ] if max_chapter >= 10 else [],
        "events": len(events),
        "counts_by_type": dict(sorted(counts.items())),
        "unresolved_thread_count": len(unresolved_ages),
        "oldest_unresolved_thread_age": max(unresolved_ages) if unresolved_ages else 0,
        "average_payoff_interval": mean(payoff_intervals) if payoff_intervals else None,
        "agency_density": agency_density,
        "setting_debt_index": setting_debt,
        "gate_risks": gate_risks(max_chapter),
        "reader_experience_ledgers": reader_ledgers,
        "rolling_blockers": rolling_blockers,
        "rolling_warnings": rolling_warnings,
        "risk_flags": risks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Long Health: through {report['through']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"chapters: {report['chapters']}",
        f"events: {report['events']}",
        f"agency_density: {report['agency_density']:.2f}",
        f"oldest_unresolved_thread_age: {report['oldest_unresolved_thread_age']}",
        f"average_payoff_interval: {report['average_payoff_interval']}",
        f"setting_debt_index: {report['setting_debt_index']}",
        "",
        "## Risk Flags",
        "",
    ]
    lines.extend(f"- {item}" for item in report["risk_flags"]) if report["risk_flags"] else lines.append("- none")
    lines.extend(["", "## Rolling Blockers", ""])
    lines.extend(f"- {item}" for item in report.get("rolling_blockers", [])) if report.get("rolling_blockers") else lines.append("- none")
    lines.extend(["", "## Rolling Warnings", ""])
    lines.extend(f"- {item}" for item in report.get("rolling_warnings", [])) if report.get("rolling_warnings") else lines.append("- none")
    lines.extend(["", "## Gate Risks", ""])
    lines.extend(f"- {item}" for item in report["gate_risks"]) if report["gate_risks"] else lines.append("- none")
    lines.extend(["", "## Reader Experience Ledgers", ""])
    for key, item in report.get("reader_experience_ledgers", {}).items():
        blockers = item.get("blockers") or []
        lines.append(f"- {key}: {'blockers=' + str(len(blockers)) if blockers else 'clear'} ({item.get('path')})")
    lines.extend(["", "## Counts", ""])
    lines.extend(f"- {key}: {value}" for key, value in report["counts_by_type"].items()) if report["counts_by_type"] else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show long-form health signals for a long novel run.")
    parser.add_argument("--to", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        out_dir = ROOT / "state" / "derived" / "long_health"
        write_json(out_dir / "latest.json", report)
        write_text(out_dir / "latest.md", render_markdown(report))
        print(f"wrote: {(out_dir / 'latest.md').relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
