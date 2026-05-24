from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, write_json, write_text
from market_scan import idea_lab_ids, resolve_idea_id


FIELDS = (
    "target_platform",
    "target_reader",
    "genre_lane",
    "ranking_goal",
    "three_day_retention_design",
    "paid_conversion_design",
    "update_cadence",
    "expected_length",
    "core_satisfactions",
    "emotional_hook",
    "first_three_chapter_validation_points",
    "differentiation_one_liner",
    "what_not_to_write",
    "copyright_similarity_risk_statement",
    "no_imitation_attestation",
)
WRITE_FLAGS = ("writes_canon", "writes_event_ledger", "writes_context_pack", "writes_brief")


def lab_path(idea_id: str) -> Path:
    return ROOT / "state" / "idea_lab" / idea_id


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def blank_report(idea_id: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "idea_id": idea_id,
        "generated_at": now_iso(),
        "status": "WARNING",
        "writes_canon": False,
        "writes_event_ledger": False,
        "writes_context_pack": False,
        "writes_brief": False,
    }
    for field in FIELDS:
        report[field] = [] if field in {"core_satisfactions", "first_three_chapter_validation_points", "what_not_to_write"} else ""
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Commercial Idea: {report['idea_id']}", "", f"status: {report.get('status', 'WARNING')}", ""]
    labels = {
        "target_platform": "目标平台",
        "target_reader": "目标读者",
        "genre_lane": "类型赛道",
        "ranking_goal": "榜单/推荐目标",
        "three_day_retention_design": "三日留存设计",
        "paid_conversion_design": "付费卡点设计",
        "update_cadence": "更新节奏",
        "expected_length": "预计字数/卷数",
        "core_satisfactions": "核心爽点",
        "emotional_hook": "情绪卖点",
        "first_three_chapter_validation_points": "前三章验证点",
        "differentiation_one_liner": "差异化一句话",
        "what_not_to_write": "不写什么",
        "copyright_similarity_risk_statement": "版权/相似风险声明",
        "no_imitation_attestation": "不模仿声明",
    }
    for field in FIELDS:
        lines.extend([f"## {labels[field]}", ""])
        value = report.get(field)
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value) if value else lines.append("- ")
        else:
            lines.append(str(value or ""))
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- commercial_mode_evidence: true",
            "- fact_source: false",
            "- writes_canon: false",
            "- writes_event_ledger: false",
            "- writes_context_pack: false",
            "- writes_brief: false",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def check_report(idea_id: str) -> tuple[str, list[str], list[str]]:
    path = lab_path(idea_id) / "commercial_idea.json"
    if not path.exists():
        return "WARNING", [], [f"missing state/idea_lab/{idea_id}/commercial_idea.json"]
    data = read_json(path, {})
    blockers: list[str] = []
    warnings: list[str] = []
    for flag in WRITE_FLAGS:
        if data.get(flag) is not False:
            blockers.append(f"commercial idea must not set {flag}=true")
    for field in FIELDS:
        value = data.get(field)
        if value in (None, "", [], {}):
            warnings.append(f"incomplete commercial idea field: {field}")
    if blockers:
        return "BLOCKED", blockers, warnings
    return "READY" if not warnings else "WARNING", blockers, warnings


def print_check(idea_id: str) -> int:
    status, blockers, warnings = check_report(idea_id)
    print(f"# Commercial Idea Check: {idea_id}")
    print()
    print(f"status: {status}")
    if blockers:
        print()
        print("## Blockers")
        for item in blockers:
            print(f"- {item}")
    if warnings:
        print()
        print("## Warnings")
        for item in warnings:
            print(f"- {item}")
    return 1 if blockers else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or check commercial-serial positioning evidence.")
    parser.add_argument("--id", default=None)
    parser.add_argument("--output", default="commercial_idea.md")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    idea_id = resolve_idea_id(args.id or "latest")
    if args.check:
        if not idea_id:
            print("# Commercial Idea Check")
            print()
            print("status: WARNING")
            print("- no idea lab found")
            return 0
        return print_check(idea_id)

    if args.id:
        lab = lab_path(args.id)
        lab.mkdir(parents=True, exist_ok=True)
        json_path = lab / "commercial_idea.json"
        md_path = lab / "commercial_idea.md"
        if (json_path.exists() or md_path.exists()) and not args.force:
            print(f"ERROR: commercial idea already exists for {args.id}; use --force", flush=True)
            return 1
        report = blank_report(args.id)
        write_json(json_path, report)
        write_text(md_path, render_markdown(report))
        write_json(ROOT / "state" / "derived" / "commercial" / f"{args.id}.json", report)
        print(f"OK: wrote {rel(json_path)}")
        return 0

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if output.exists() and not args.force:
        print(f"ERROR: {rel(output)} already exists; use --force")
        return 1
    idea = idea_id or (idea_lab_ids()[0] if idea_lab_ids() else "idea_xxx")
    write_text(output, render_markdown(blank_report(idea)))
    print(f"OK: wrote {rel(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
