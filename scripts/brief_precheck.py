from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, read_json, read_text, unresolved_locks
from core_setting_freeze import freeze_markdown_path, validate_freeze
from element_context import yaml_id_index
from gate_policy import gate_errors_for_chapter
from pacing_check import analyze as analyze_pacing
from pacing_check import parse_entry


PLACEHOLDERS = ("待定", "待填", "待生成", "TODO", "TBD", "寰呭畾", "寰呭～")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def has_placeholder(path: Path) -> bool:
    return path.exists() and any(marker in read_text(path) for marker in PLACEHOLDERS)


def previous_chapter(chapter: str) -> str | None:
    number = chapter_number(chapter)
    if number <= 1:
        return None
    return f"{chapter[:3]}_c{number - 1:03d}"


def yaml_root_check(path: Path, root_key: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    info: list[str] = []
    if not path.exists():
        return [f"missing YAML index: {rel(path)}"], info
    text = read_text(path)
    if f"{root_key}:" not in text:
        return [f"YAML index missing root `{root_key}`: {rel(path)}"], info
    try:
        ids = yaml_id_index(path, root_key)
    except Exception as exc:  # pragma: no cover - defensive around malformed files
        return [f"YAML index unreadable: {rel(path)}: {exc}"], info
    info.append(f"{rel(path)} readable; ids={len(ids)}")
    return blockers, info


def load_aftermath() -> dict[str, Any]:
    return read_json(ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json", {})


def stale_derived_findings(chapter: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    info: list[str] = []
    current = ROOT / "state" / "derived" / "current_state.yaml"
    progress = ROOT / "state" / "derived" / "pacing" / "progress_index.json"
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not current.exists() or not progress.exists():
        blockers.append("derived state is missing; run build-derived-state before brief precheck")
        return blockers, info
    if ledger.exists() and ledger.stat().st_mtime > current.stat().st_mtime + 0.5:
        blockers.append("derived state is older than state/event_ledger.jsonl")
    brief_dir = ROOT / "outline" / "chapter_briefs"
    newer_briefs = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(brief_dir.glob("v*_c*.md"))
        if path.stat().st_mtime > progress.stat().st_mtime + 0.5
    ]
    if newer_briefs:
        blockers.append("derived pacing is older than chapter brief inputs: " + ", ".join(newer_briefs[:5]))
    if not blockers:
        info.append("derived state freshness: current")
    return blockers, info


def aftermath_findings(chapter: str) -> tuple[list[str], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    path = ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json"
    if not path.exists():
        warnings.append("missing derived aftermath obligations; brief-candidates will rebuild derived state before building the pack")
        return blockers, warnings, info
    data = load_aftermath()
    obligations = data.get("obligations", []) if isinstance(data, dict) else []
    if not isinstance(obligations, list):
        blockers.append("aftermath obligations JSON must contain an obligations list")
        return blockers, warnings, info
    target_number = chapter_number(chapter)
    for item in obligations:
        if not isinstance(item, dict):
            continue
        due = str(item.get("due_chapter") or "")
        status = str(item.get("status") or "")
        source = str(item.get("source_chapter") or "unknown")
        due_number = chapter_number(due) if due.startswith(chapter[:3]) else None
        label = f"{source} -> {due}: {item.get('aftermath_obligation', '')}"
        if status == "overdue":
            blockers.append(f"overdue aftermath obligation: {label}")
        elif status == "active" and due_number is not None and due_number <= target_number:
            blockers.append(f"aftermath obligation due before this brief: {label}")
        elif status == "active" and due_number is not None and due_number <= target_number + 1:
            warnings.append(f"aftermath obligation is due soon: {label}")
    active_count = sum(1 for item in obligations if isinstance(item, dict) and item.get("status") == "active")
    overdue_count = sum(1 for item in obligations if isinstance(item, dict) and item.get("status") == "overdue")
    info.append(f"aftermath obligations: active={active_count}, overdue={overdue_count}")
    return blockers, warnings, info


def pacing_history_findings(chapter: str) -> tuple[list[str], list[str]]:
    paths = [
        path
        for path in sorted((ROOT / "outline" / "chapter_briefs").glob("v*_c*.md"))
        if path.stem[:3] == chapter[:3] and chapter_number(path.stem) < chapter_number(chapter)
    ]
    entries = [parse_entry(path) for path in paths]
    if not entries:
        return [], []
    status, blockers, warnings = analyze_pacing(entries, 5)
    prefixed_blockers = [f"pacing history {status}: {item}" for item in blockers]
    prefixed_warnings = [f"pacing history warning: {item}" for item in warnings]
    return prefixed_blockers, prefixed_warnings


def evaluate(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    locks = unresolved_locks()
    blockers.extend(f"open stop lock: {item.get('id')}: {item.get('reason')}" for item in locks)
    blockers.extend(validate_freeze())
    blockers.extend(gate_errors_for_chapter(chapter, "preparing"))
    derived_blockers, derived_info = stale_derived_findings(chapter)
    blockers.extend(derived_blockers)
    info.extend(derived_info)

    previous = previous_chapter(chapter)
    if previous is None:
        info.append("opening chapter; no previous chapter anchor required")
    else:
        anchor = ROOT / "state" / "derived" / "chapter_anchors" / f"{previous}.json"
        if not anchor.exists():
            blockers.append(f"missing previous chapter anchor: {rel(anchor)}")
        else:
            info.append(f"previous chapter anchor found: {rel(anchor)}")

    rules = ROOT / "bible" / "rules.md"
    if has_placeholder(rules):
        blockers.append(f"critical source still has placeholder text: {rel(rules)}")
    freeze_md = freeze_markdown_path()
    if freeze_md is not None and has_placeholder(freeze_md):
        blockers.append(f"core freeze markdown still has placeholder text: {rel(freeze_md)}")
    for optional in (ROOT / "outline" / "premise.md", ROOT / "bible" / "style_guide.md"):
        if has_placeholder(optional):
            warnings.append(f"source still has placeholder text: {rel(optional)}")

    for path, root_key in ((ROOT / "bible" / "objects.yaml", "objects"), (ROOT / "bible" / "abilities.yaml", "abilities")):
        yaml_blockers, yaml_info = yaml_root_check(path, root_key)
        blockers.extend(yaml_blockers)
        info.extend(yaml_info)

    pacing_blockers, pacing_warnings = pacing_history_findings(chapter)
    blockers.extend(pacing_blockers)
    warnings.extend(pacing_warnings)
    aftermath_blockers, aftermath_warnings, aftermath_info = aftermath_findings(chapter)
    blockers.extend(aftermath_blockers)
    warnings.extend(aftermath_warnings)
    info.extend(aftermath_info)

    status = "BLOCKED" if blockers else "WARN" if warnings else "READY"
    if blockers:
        if any("core setting freeze" in item for item in blockers):
            next_action = "想法：... / 开书实验，然后定盘。"
        elif any("chapter anchor" in item for item in blockers):
            next_action = f"先为 {previous} 记录 chapter_anchor 事件，再重建 derived state。"
        elif any("aftermath" in item for item in blockers):
            next_action = "先改上一章或当前 brief，承接到期后果债务。"
        else:
            next_action = "修复 Blockers 后重跑 brief-precheck。"
    elif warnings:
        next_action = f"可继续生成 {chapter} brief 候选，但建议先处理 Warnings。"
    else:
        next_action = f"可运行 `python scripts/novel.py brief-candidates {chapter}`。"

    return {
        "schema_version": 1,
        "chapter": chapter,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "info": info,
        "next_action": next_action,
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"# Brief Precheck: {report['chapter']}")
    print()
    print(f"status: {report['status']}")
    print()
    for title, key in (("Blockers", "blockers"), ("Warnings", "warnings"), ("Info", "info")):
        print(f"## {title}")
        items = report.get(key) or []
        if items:
            for item in items:
                print(f"- {item}")
        else:
            print("- none")
        print()
    print("## Next Action")
    print(report["next_action"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run smart prechecks before building chapter brief candidates.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = evaluate(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
