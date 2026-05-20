from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, read_json, read_text, write_json, write_text
from context_governance import context_manifest_path, context_quality_path, sha256
from core_setting_freeze import freeze_markdown_path


REQUIRED_SECTIONS = {
    "core_freeze",
    "chapter_brief",
    "chapter_anchor_continuity",
    "active_aftermath_obligations",
    "book_outline_contract",
    "style_instruction",
    "reader_promise",
    "reader_experience_state",
    "authorized_elements_full",
    "rules_and_boundaries",
}
PLACEHOLDER_MARKERS = ("待定", "待填", "待生成", "TODO", "TBD", "寰呭畾", "寰呭～", "寰呯敓")
CRITICAL_CONTEXT_SOURCE_SUFFIXES = ("bible/rules.md",)
WARNING_CONTEXT_SOURCE_SUFFIXES = ("bible/style_guide.md", "bible/canon.md")
READER_DERIVED_SUFFIXES = (
    "state/project_reader_promise.json",
    "state/project_reader_promise.md",
    "state/derived/personality/protagonist.json",
    "state/derived/protagonist_progression.json",
    "state/derived/concept_index.json",
    "state/derived/world_reveal_ledger.json",
    "state/derived/suspense_ledger.json",
)


def has_placeholder(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def source_placeholder_findings(chapter: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    freeze_path = freeze_markdown_path()
    sources = [
        ROOT / "bible" / "rules.md",
        ROOT / "bible" / "style_guide.md",
        ROOT / "bible" / "canon.md",
        ROOT / "outline" / "chapter_briefs" / f"{chapter}.md",
    ]
    if freeze_path is not None:
        sources.append(freeze_path)
    for path in sources:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = read_text(path)
        if not has_placeholder(text):
            continue
        if rel.endswith(CRITICAL_CONTEXT_SOURCE_SUFFIXES) or rel == f"outline/chapter_briefs/{chapter}.md" or path == freeze_path:
            blockers.append(f"critical context source contains placeholder text: {rel}")
        elif rel.endswith(WARNING_CONTEXT_SOURCE_SUFFIXES):
            warnings.append(f"context source contains placeholder text: {rel}")
        else:
            warnings.append(f"context source contains placeholder text: {rel}")
    return blockers, warnings


def conflict_findings(pack_text: str) -> tuple[list[str], list[str]]:
    if "Core Setting Freeze" not in pack_text and "status: LOCKED" not in pack_text:
        return [], []
    rule_conflict_terms = ("核心异常 / 能力 / 技术是什么？\n\n待定", "规则：待定", "能力限制：待定", "TODO：写")
    if any(term in pack_text for term in rule_conflict_terms):
        return ["context pack mixes locked core freeze with pending rule/ability placeholders"], []
    if has_placeholder(pack_text):
        return [], ["context pack still contains placeholder text in non-critical source material"]
    return [], []


def load_events() -> list[dict[str, Any]]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_event_ids(manifest: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            continue
        for event_id in section.get("event_ids", []) or []:
            ids.add(str(event_id))
        for source in section.get("sources", []) or []:
            if isinstance(source, dict) and source.get("event_id"):
                ids.add(str(source["event_id"]))
    return ids


def prior_critical_events(chapter: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    number = chapter_number(chapter)
    return [
        event
        for event in events
        if chapter_number(event["chapter"]) < number and event.get("importance") in {"P0", "P1"}
    ]


def active_threads(chapter: str, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    number = chapter_number(chapter)
    threads: dict[str, dict[str, Any]] = {}
    for event in events:
        if chapter_number(event["chapter"]) >= number:
            continue
        if event["type"] not in {"thread_opened", "thread_advanced", "thread_paid_off", "correction"}:
            continue
        thread_id = str(event.get("thread_id") or event.get("fact") or event["event_id"])
        item = threads.setdefault(thread_id, {"id": thread_id, "status": "open", "event_ids": []})
        item["event_ids"].append(event["event_id"])
        rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        importance = str(event.get("importance") or item.get("importance") or "P2")
        current = str(item.get("importance") or importance)
        item["importance"] = importance if rank.get(importance, 2) < rank.get(current, 2) else current
        if event["type"] == "thread_advanced":
            item["status"] = "active"
        elif event["type"] == "thread_paid_off":
            item["status"] = "paid_off"
        elif event["type"] == "correction":
            item["status"] = "corrected"
    return {key: value for key, value in threads.items() if value["status"] != "paid_off"}


def source_trace_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            failures.append("manifest contains a non-object section entry")
            continue
        sources = section.get("sources")
        if not isinstance(sources, list) or not sources:
            failures.append(f"section {section.get('id', 'UNKNOWN')} has no source trace")
            continue
        for source in sources:
            if not isinstance(source, dict):
                failures.append(f"section {section.get('id', 'UNKNOWN')} has malformed source trace")
                continue
            if not source.get("path") and not source.get("event_id"):
                failures.append(f"section {section.get('id', 'UNKNOWN')} has source without path/event_id")
    return failures


def planning_source_role_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for section in manifest.get("sections", []):
        if not isinstance(section, dict):
            continue
        reason = str(section.get("included_reason", ""))
        for source in section.get("sources", []) or []:
            if not isinstance(source, dict):
                continue
            path = str(source.get("path", ""))
            note = str(source.get("note", ""))
            if path in {"outline/book_outline.json", "outline/book_outline.md"} and "strategic_plan_not_fact_source" not in reason + note:
                failures.append(f"book outline source is not marked strategic_plan_not_fact_source: {path}")
            if path in {"state/project_style_contract.json", "state/project_style_contract.md", "bible/style_guide.md", "state/derived/style_profile.json"} and "style" not in reason + note:
                failures.append(f"style source is not marked style_instruction_not_fact_source: {path}")
            if path in {"state/project_reader_promise.json", "state/project_reader_promise.md"} and "reader_promise_instruction_not_fact_source" not in reason + note:
                failures.append(f"reader promise source is not marked reader_promise_instruction_not_fact_source: {path}")
            if path in READER_DERIVED_SUFFIXES and not (ROOT / path).exists():
                failures.append(f"reader/personality derived source missing: {path}")
    return failures


def stale_input_failures(input_hashes: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for item in input_hashes:
        rel_path = str(item.get("path", ""))
        expected = str(item.get("sha256", ""))
        if not rel_path or not expected:
            failures.append("input_hashes contains an entry without path/sha256")
            continue
        path = ROOT / rel_path
        if not path.exists():
            failures.append(f"input hash path is missing: {rel_path}")
        elif sha256(path) != expected:
            failures.append(f"input hash changed: {rel_path}")
    return failures


def evaluate_context_pack(chapter: str) -> dict[str, Any]:
    pack_path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    manifest_path = context_manifest_path(chapter)
    blockers: list[str] = []
    warnings: list[str] = []

    if not pack_path.exists():
        blockers.append(f"missing context pack: {pack_path.relative_to(ROOT)}")
    if not manifest_path.exists():
        blockers.append(f"missing context manifest: {manifest_path.relative_to(ROOT)}")
    if blockers:
        return {
            "schema_version": 1,
            "chapter": chapter,
            "status": "NOT_READY",
            "blockers": blockers,
            "warnings": warnings,
        }

    pack_text = read_text(pack_path)
    manifest = read_json(manifest_path, {})
    sections = manifest.get("sections", [])
    section_ids = {str(section.get("id")) for section in sections if isinstance(section, dict)}
    missing_required = sorted(REQUIRED_SECTIONS - section_ids)
    blockers.extend(f"required context section missing: {section_id}" for section_id in missing_required)

    budget = int(manifest.get("budget_chars", 0) or 0)
    hard_max = int(manifest.get("hard_max_chars", 0) or 0)
    pack_chars = len(pack_text)
    if budget and pack_chars > budget:
        blockers.append(f"context pack exceeds budget: {pack_chars} > {budget}")
    if hard_max and pack_chars > hard_max:
        blockers.append(f"context pack exceeds hard max: {pack_chars} > {hard_max}")
    if manifest.get("allow_truncated") is True or manifest.get("pack_truncated") is True:
        blockers.append("context pack was built with --allow-truncated or pack-level truncation")

    input_hashes = manifest.get("input_hashes", [])
    if not isinstance(input_hashes, list):
        blockers.append("manifest input_hashes must be a list")
        input_hashes = []
    blockers.extend(stale_input_failures(input_hashes))
    blockers.extend(source_trace_failures(manifest))
    blockers.extend(planning_source_role_failures(manifest))
    source_blockers, source_warnings = source_placeholder_findings(chapter)
    blockers.extend(source_blockers)
    warnings.extend(source_warnings)
    conflict_blockers, conflict_warnings = conflict_findings(pack_text)
    blockers.extend(conflict_blockers)
    warnings.extend(conflict_warnings)

    events = load_events()
    included_event_ids = manifest_event_ids(manifest) | {event["event_id"] for event in events if event["event_id"] in pack_text}
    critical = prior_critical_events(chapter, events)
    missing_critical = [event["event_id"] for event in critical if event["event_id"] not in included_event_ids]
    blockers.extend(f"P0/P1 required fact missing from context pack: {event_id}" for event_id in missing_critical)

    threads = active_threads(chapter, events)
    included_threads = 0
    thread_coverage_items: list[dict[str, Any]] = []
    for thread_id, thread in threads.items():
        included = thread_id in pack_text or any(event_id in included_event_ids for event_id in thread["event_ids"])
        if included:
            included_threads += 1
        thread_coverage_items.append(
            {
                "thread_id": thread_id,
                "importance": thread.get("importance", "P2"),
                "status": thread.get("status", "open"),
                "covered": included,
                "event_ids": thread.get("event_ids", []),
            }
        )
    active_thread_coverage = 1.0 if not threads else included_threads / len(threads)
    critical_missing = [
        item for item in thread_coverage_items if not item["covered"] and item.get("importance") in {"P0", "P1"}
    ]
    deferred_threads = [
        item for item in thread_coverage_items if not item["covered"] and item.get("importance") not in {"P0", "P1"}
    ]
    if critical_missing:
        blockers.append(
            "critical active/open thread coverage incomplete: "
            + ", ".join(str(item["thread_id"]) for item in critical_missing)
        )
    if deferred_threads:
        warnings.append(
            "lower-priority active/open threads not explicitly included: "
            + ", ".join(str(item["thread_id"]) for item in deferred_threads[:10])
        )

    truncation_count = sum(1 for section in sections if isinstance(section, dict) and section.get("truncated"))
    empty_sections = sum(
        1
        for section in sections
        if isinstance(section, dict) and int(section.get("body_chars", 0) or 0) <= 4
    )
    section_count = len(sections) if isinstance(sections, list) else 0
    irrelevant_section_ratio = 0.0 if section_count == 0 else empty_sections / section_count
    if irrelevant_section_ratio > 0.5:
        warnings.append(f"high irrelevant/empty section ratio: {irrelevant_section_ratio:.2f}")

    manifest_sha = sha256(manifest_path)
    pack_sha = sha256(pack_path)
    context_item = manifest.get("context_pack", {}) if isinstance(manifest.get("context_pack"), dict) else {}
    if context_item.get("sha256") and context_item["sha256"] != pack_sha:
        blockers.append("manifest context_pack sha256 does not match pack on disk")

    required_fact_coverage = 1.0 if not critical else (len(critical) - len(missing_critical)) / len(critical)
    source_failures = source_trace_failures(manifest)
    report = {
        "schema_version": 1,
        "chapter": chapter,
        "status": "READY" if not blockers else "NOT_READY",
        "pack_path": f"state/context_pack/{chapter}.md",
        "manifest_path": f"state/context_pack/{chapter}.manifest.json",
        "context_pack_sha256": pack_sha,
        "manifest_sha256": manifest_sha,
        "budget_chars": budget,
        "pack_chars": pack_chars,
        "pack_chars_over_budget": pack_chars / budget if budget else None,
        "required_fact_coverage": required_fact_coverage,
        "unsupported_key_fact_count": len(missing_critical) + len(source_failures),
        "active_thread_coverage": active_thread_coverage,
        "thread_coverage": {
            "total": len(thread_coverage_items),
            "covered": included_threads,
            "critical_missing": critical_missing,
            "summarized_covered": [item for item in thread_coverage_items if item["covered"]],
            "budget_deferred": deferred_threads,
        },
        "irrelevant_section_ratio": irrelevant_section_ratio,
        "truncation_count": truncation_count,
        "source_traceability": {
            "ok": not source_failures,
            "failure_count": len(source_failures),
        },
        "input_hashes": {str(item.get("path")): str(item.get("sha256")) for item in input_hashes if isinstance(item, dict)},
        "object_ids": manifest.get("object_ids", []),
        "ability_ids": manifest.get("ability_ids", []),
        "blockers": blockers,
        "warnings": warnings,
    }
    return report


def render_markdown_report(report: dict[str, Any]) -> str:
    chapter = report.get("chapter", "unknown")
    lines = [
        f"# Context Quality Report: {chapter}",
        "",
        f"status: {report.get('status', 'UNKNOWN')}",
        f"pack: {report.get('pack_path', 'missing')}",
        f"manifest: {report.get('manifest_path', 'missing')}",
        "",
        "## Verdict",
        "",
    ]
    if report.get("status") == "READY":
        lines.append("- 可以继续：context pack 通过机器门禁。")
    else:
        lines.append("- 不能继续：context pack 仍有阻断项，不能进入正式写作。")
    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    blockers = report.get("blockers") or []
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines.extend(
        [
            "",
            "## Budget / Trace",
            "",
            f"- pack_chars: {report.get('pack_chars', 'unknown')}",
            f"- budget_chars: {report.get('budget_chars', 'unknown')}",
            f"- truncation_count: {report.get('truncation_count', 'unknown')}",
            f"- required_fact_coverage: {report.get('required_fact_coverage', 'unknown')}",
            f"- active_thread_coverage: {report.get('active_thread_coverage', 'unknown')}",
            f"- source_traceability: {report.get('source_traceability', {}).get('ok', 'unknown')}",
            f"- critical_missing_threads: {len(report.get('thread_coverage', {}).get('critical_missing', []))}",
            f"- budget_deferred_threads: {len(report.get('thread_coverage', {}).get('budget_deferred', []))}",
            "",
            "## Authorized IDs",
            "",
            "- object_ids: " + (", ".join(str(item) for item in report.get("object_ids", [])) or "none"),
            "- ability_ids: " + (", ".join(str(item) for item in report.get("ability_ids", [])) or "none"),
            "",
            "## Input Hashes",
            "",
        ]
    )
    hashes = report.get("input_hashes", {})
    if isinstance(hashes, dict) and hashes:
        lines.extend(f"- {path}: {value}" for path, value in sorted(hashes.items()))
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def write_quality_report(chapter: str) -> dict[str, Any]:
    report = evaluate_context_pack(chapter)
    write_json(context_quality_path(chapter), report)
    write_text(context_quality_path(chapter).with_suffix(".md"), render_markdown_report(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check context pack quality before drafting.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    report = write_quality_report(args.chapter)
    markdown_path = context_quality_path(args.chapter).with_suffix(".md")
    print(f"# Context Pack Quality: {args.chapter}")
    print()
    print(f"status: {report['status']}")
    if report.get("blockers"):
        print()
        print("## Blockers")
        print()
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    if report.get("warnings"):
        print()
        print("## Warnings")
        print()
        for warning in report["warnings"]:
            print(f"- {warning}")
    print()
    print(f"report: {markdown_path.relative_to(ROOT).as_posix()}")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
