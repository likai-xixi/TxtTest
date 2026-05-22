from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, read_text, write_json, write_text
from artifact_integrity import file_ref, validate_chapter_shape, validate_reader_reward_gate
from health_report import infer_last_chapter, load_events
from reader_personality_contracts import load_reader_promise


CATEGORIES = (
    "pace",
    "repetition",
    "suspense",
    "protagonist",
    "worldview",
    "perspective",
    "language",
    "structural_efficiency",
)
HIGH_PRESSURE_MARKERS = ("H3", "H4", "W3", "W4", "高压", "强压", "爆发")
SUSPENSE_DEADLINES = {"P0": 2, "P1": 4, "P2": 8, "P3": 12}


def chapter_id(number: int) -> str:
    return f"v01_c{number:03d}"


def chapter_path(chapter: str) -> Path:
    return ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"


def int_policy(path: list[str], default: int) -> int:
    value: Any = load_reader_promise()
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def report_status(blockers: list[str], warnings: list[str]) -> str:
    return "BLOCKED" if blockers else "WARNING" if warnings else "READY"


def high_pressure(value: str) -> bool:
    return any(marker in str(value or "") for marker in HIGH_PRESSURE_MARKERS)


def suspense_importance(event: dict[str, Any]) -> str:
    value = str(event.get("importance") or event.get("priority") or "P2").upper()
    return value if value in SUSPENSE_DEADLINES else "P2"


def more_urgent(left: str, right: str) -> str:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return left if order.get(left, 2) <= order.get(right, 2) else right


def suspense_thread_id(event: dict[str, Any]) -> str:
    return str(event.get("thread_id") or event.get("fact") or event.get("event_id") or "unknown")


def suspense_age_budget(events: list[dict[str, Any]], target_number: int) -> dict[str, Any]:
    threads: dict[str, dict[str, Any]] = {}
    sequence: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("type") or "")
        if event_type not in {"thread_opened", "thread_advanced", "thread_paid_off"}:
            continue
        try:
            number = chapter_number(str(event.get("chapter")))
        except ValueError:
            continue
        key = suspense_thread_id(event)
        item = threads.setdefault(
            key,
            {
                "thread_id": key,
                "opened_at": number,
                "last_advanced_at": number,
                "paid_off_at": None,
                "importance": suspense_importance(event),
                "events": [],
            },
        )
        item["opened_at"] = min(int(item["opened_at"]), number)
        if event_type in {"thread_opened", "thread_advanced"}:
            item["last_advanced_at"] = max(int(item["last_advanced_at"]), number)
        if event_type == "thread_paid_off":
            item["paid_off_at"] = number
            item["last_advanced_at"] = max(int(item["last_advanced_at"]), number)
        item["importance"] = more_urgent(str(item.get("importance") or "P2"), suspense_importance(event))
        item["events"].append({"chapter": event.get("chapter"), "type": event_type})
        sequence.append({"chapter_number": number, "type": event_type, "thread_id": key, "fact": str(event.get("fact") or "")})

    blockers: list[str] = []
    warnings: list[str] = []
    open_threads: list[dict[str, Any]] = []
    for item in sorted(threads.values(), key=lambda value: (int(value["opened_at"]), str(value["thread_id"]))):
        if item.get("paid_off_at"):
            continue
        importance = str(item.get("importance") or "P2")
        deadline = SUSPENSE_DEADLINES.get(importance, SUSPENSE_DEADLINES["P2"])
        age = target_number - int(item.get("last_advanced_at") or item.get("opened_at") or target_number) + 1
        budget_item = {
            "thread_id": item["thread_id"],
            "importance": importance,
            "opened_at": f"v01_c{int(item['opened_at']):03d}",
            "last_advanced_at": f"v01_c{int(item['last_advanced_at']):03d}",
            "age_since_advance": age,
            "payoff_deadline_chapters": deadline,
            "status": "OVERDUE" if age > deadline else "OPEN",
        }
        open_threads.append(budget_item)
        if age > deadline and importance in {"P0", "P1"}:
            blockers.append(f"{budget_item['thread_id']}: {importance} suspense overdue {age}/{deadline} chapters")
        elif age > deadline:
            warnings.append(f"{budget_item['thread_id']}: suspense overdue {age}/{deadline} chapters")

    recent = [item for item in sorted(sequence, key=lambda value: value["chapter_number"]) if item["chapter_number"] >= max(1, target_number - 2)]
    recent_open_only = [item for item in recent if item["type"] == "thread_opened"]
    recent_progress = [item for item in recent if item["type"] in {"thread_advanced", "thread_paid_off"}]
    if len(recent_open_only) >= 3 and not recent_progress:
        blockers.append("recent 3-chapter window opens suspense threads without advancement or payoff")

    return {
        "deadlines": SUSPENSE_DEADLINES,
        "open_threads": open_threads,
        "blockers": blockers,
        "warnings": warnings,
    }


def feedback_current(chapter: str) -> dict[str, Any]:
    path = ROOT / "reviews" / chapter / "reader_feedback.json"
    data = read_json(path, {}) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def feedback_accepted(data: dict[str, Any]) -> bool:
    acceptance = data.get("human_acceptance")
    if not isinstance(acceptance, dict):
        return False
    risk_items = acceptance.get("risk_acceptance_items")
    return (
        all(str(acceptance.get(key, "")).strip() for key in ("accepted_by", "accepted_at", "reason", "report_sha256"))
        and acceptance.get("accepted_by") == "human"
        and isinstance(risk_items, list)
        and any(str(item).strip() for item in risk_items)
    )


def evaluate(to_chapter: str | None = None) -> dict[str, Any]:
    target = to_chapter or infer_last_chapter()
    target_number = chapter_number(target)
    events = load_events(target_number)
    events_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_chapter.setdefault(str(event.get("chapter", "")), []).append(event)

    thresholds = {
        "no_release_max_run": int_policy(["negative_failure_modes", "no_release_max_run"], 2),
        "no_payoff_max_run": int_policy(["negative_failure_modes", "no_payoff_max_run"], 2),
        "open_without_payoff_max_run": int_policy(["negative_failure_modes", "open_without_payoff_max_run"], 2),
        "passive_protagonist_max_run": int_policy(["negative_failure_modes", "passive_protagonist_max_run"], 1),
        "explanation_only_max_run": int_policy(["negative_failure_modes", "explanation_only_max_run"], 1),
        "repeated_shape_max_run": int_policy(["negative_failure_modes", "repeated_shape_max_run"], 2),
        "low_efficiency_window_chapters": int_policy(["negative_failure_modes", "low_efficiency_window_chapters"], 5),
        "low_efficiency_max_count": int_policy(["negative_failure_modes", "low_efficiency_max_count"], 2),
    }

    blockers: list[str] = []
    warnings: list[str] = []
    category_blockers: dict[str, list[str]] = {key: [] for key in CATEGORIES}
    category_warnings: dict[str, list[str]] = {key: [] for key in CATEGORIES}
    chapters: list[dict[str, Any]] = []
    no_release_run = 0
    no_payoff_run = 0
    open_only_run = 0
    passive_run = 0
    explanation_run = 0
    low_efficiency_window: list[str] = []
    previous_shape_key = ""
    shape_repeat_run = 0

    for number in range(1, target_number + 1):
        chapter = chapter_id(number)
        reward, reward_failures = validate_reader_reward_gate(chapter)
        shape, shape_failures = validate_chapter_shape(chapter)
        feedback = feedback_current(chapter)
        chapter_events = events_by_chapter.get(chapter, [])
        event_counts = Counter(event.get("type") for event in chapter_events)

        chapter_blockers: list[str] = []
        chapter_warnings: list[str] = []
        for failure in reward_failures:
            chapter_blockers.append(f"cannot trust reader reward gate: {failure}")
        for failure in shape_failures:
            chapter_blockers.append(f"cannot trust chapter shape: {failure}")

        contract = reward.get("contract") if isinstance(reward, dict) and isinstance(reward.get("contract"), dict) else {}
        shape_body = shape.get("shape") if isinstance(shape, dict) and isinstance(shape.get("shape"), dict) else {}
        matched = reward.get("matched_evidence_quotes") if isinstance(reward, dict) else []
        has_payoff = isinstance(matched, list) and bool(matched)
        pressure = str(contract.get("pressure_level", ""))
        release = str(contract.get("release_valve", "")).strip()
        if high_pressure(pressure) and not release:
            no_release_run += 1
        elif release or not high_pressure(pressure):
            no_release_run = 0
        if no_release_run > thresholds["no_release_max_run"]:
            category_blockers["pace"].append(f"{chapter}: 连续高压无释放 {no_release_run} 章")

        if has_payoff:
            no_payoff_run = 0
        else:
            no_payoff_run += 1
        if no_payoff_run > thresholds["no_payoff_max_run"]:
            category_blockers["pace"].append(f"{chapter}: 连续无正文回报证据 {no_payoff_run} 章")

        opened = event_counts["thread_opened"]
        advanced = event_counts["thread_advanced"] + event_counts["thread_paid_off"]
        if opened and not advanced:
            open_only_run += 1
        else:
            open_only_run = 0
        if open_only_run > thresholds["open_without_payoff_max_run"]:
            category_blockers["suspense"].append(f"{chapter}: 连续只开悬念不推进/兑现 {open_only_run} 章")

        position = str(shape_body.get("protagonist_position", ""))
        has_decision = event_counts["character_decision"] > 0
        if position == "reactive" or not has_decision:
            passive_run += 1
        else:
            passive_run = 0
        if passive_run > thresholds["passive_protagonist_max_run"]:
            category_blockers["protagonist"].append(f"{chapter}: 主角主动性不足连续 {passive_run} 章")

        if str(shape_body.get("exposition_load", "")) == "explanation_only":
            explanation_run += 1
        else:
            explanation_run = 0
        if explanation_run > thresholds["explanation_only_max_run"]:
            category_blockers["worldview"].append(f"{chapter}: 世界观/信息解释负载连续过高 {explanation_run} 章")

        shape_key = str(shape.get("shape_key", "")) if isinstance(shape, dict) else ""
        if shape_key and shape_key == previous_shape_key:
            shape_repeat_run += 1
        elif shape_key:
            shape_repeat_run = 1
        previous_shape_key = shape_key or previous_shape_key
        if number >= 6 and shape_repeat_run > thresholds["repeated_shape_max_run"]:
            category_blockers["repetition"].append(f"{chapter}: 章节形状重复 {shape_repeat_run} 章")

        if event_counts["rule_reveal"] == 0 and number >= 6:
            category_warnings["worldview"].append(f"{chapter}: 本章没有 human-verified rule_reveal")
        if feedback:
            if feedback.get("response_count", 0) == 0 and not feedback_accepted(feedback):
                category_blockers["perspective"].append(f"{chapter}: reader feedback 没有真实读者回答，也没有人工接受说明")
            if feedback.get("author_explanation_flags"):
                category_blockers["language"].append(f"{chapter}: 读者反馈指出作者解释感")
            if feedback.get("suspense_fatigue_flags"):
                category_warnings["suspense"].append(f"{chapter}: 读者反馈存在悬念疲劳信号")
            if feedback.get("protagonist_charm_notes") == [] and feedback.get("response_count", 0) > 0:
                category_warnings["protagonist"].append(f"{chapter}: 真实读者反馈缺主角魅力记录")
        elif number >= 3:
            category_warnings["perspective"].append(f"{chapter}: 缺 reader_feedback summary")

        progress_unit = str(contract.get("effective_progress_unit", ""))
        text = read_text(chapter_path(chapter))
        inefficient = ("->" not in progress_unit and "→" not in progress_unit) or len(text) > int_policy(["structural_efficiency_policy", "max_words_without_state_change"], 6000) and not has_decision
        low_efficiency_window.append(chapter if inefficient else "")
        low_efficiency_window = low_efficiency_window[-thresholds["low_efficiency_window_chapters"] :]
        if sum(1 for item in low_efficiency_window if item) > thresholds["low_efficiency_max_count"]:
            category_blockers["structural_efficiency"].append(f"{chapter}: 最近窗口大字数低推进或缺 before -> after 过多")

        chapters.append(
            {
                "chapter": chapter,
                "reader_reward_gate": file_ref(ROOT / "reviews" / chapter / "reader_reward_gate.json"),
                "chapter_shape": file_ref(ROOT / "reviews" / chapter / "chapter_shape.json"),
                "reader_feedback": file_ref(ROOT / "reviews" / chapter / "reader_feedback.json"),
                "event_counts": dict(sorted(event_counts.items())),
                "no_release_run": no_release_run,
                "no_payoff_run": no_payoff_run,
                "open_only_run": open_only_run,
                "passive_run": passive_run,
                "explanation_run": explanation_run,
                "shape_repeat_run": shape_repeat_run,
                "blockers": chapter_blockers,
                "warnings": chapter_warnings,
            }
        )
        blockers.extend(f"{chapter}: {item}" for item in chapter_blockers)
        warnings.extend(f"{chapter}: {item}" for item in chapter_warnings)

    suspense_budget = suspense_age_budget(events, target_number)
    category_blockers["suspense"].extend(suspense_budget["blockers"])
    category_warnings["suspense"].extend(suspense_budget["warnings"])

    for category, items in category_blockers.items():
        blockers.extend(f"{category}: {item}" for item in items)
    for category, items in category_warnings.items():
        warnings.extend(f"{category}: {item}" for item in items)

    category_statuses = {
        key: report_status(category_blockers[key], category_warnings[key])
        for key in CATEGORIES
    }
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": report_status(blockers, warnings),
        "through": target,
        "chapters_checked": target_number,
        "thresholds": thresholds,
        "category_statuses": category_statuses,
        "category_blockers": category_blockers,
        "category_warnings": category_warnings,
        "chapters": chapters,
        "suspense_age_budget": suspense_budget,
        "source_reader_promise": file_ref(ROOT / "state" / "project_reader_promise.json"),
        "source_event_ledger": file_ref(ROOT / "state" / "event_ledger.jsonl"),
        "blockers": blockers,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Reader Risk Index: through {report['through']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"chapters_checked: {report['chapters_checked']}",
        "",
        "## Category Statuses",
        "",
    ]
    for key, value in report.get("category_statuses", {}).items():
        lines.append(f"- {key}: {value}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        items = report.get(key) or []
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    lines.extend(["", "## Suspense Age Budget", ""])
    budget = report.get("suspense_age_budget") or {}
    open_threads = budget.get("open_threads") or []
    if not open_threads:
        lines.append("- none")
    for item in open_threads:
        lines.append(
            "- {thread_id}: {status} importance={importance} age={age}/{deadline} last_advanced={last}".format(
                thread_id=item.get("thread_id"),
                status=item.get("status"),
                importance=item.get("importance"),
                age=item.get("age_since_advance"),
                deadline=item.get("payoff_deadline_chapters"),
                last=item.get("last_advanced_at"),
            )
        )
    lines.extend(["", "## Recent Chapters", ""])
    for item in report.get("chapters", [])[-10:]:
        lines.append(
            "- {chapter}: payoff_gap={payoff} passive_run={passive} shape_repeat={shape} explanation_run={explain}".format(
                chapter=item.get("chapter"),
                payoff=item.get("no_payoff_run"),
                passive=item.get("passive_run"),
                shape=item.get("shape_repeat_run"),
                explain=item.get("explanation_run"),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the cross-chapter reader risk index.")
    parser.add_argument("--to", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        out_dir = ROOT / "state" / "derived" / "reader_risk"
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
