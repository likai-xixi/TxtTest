from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, read_text, write_json, write_text


REQUIRED_FIELDS = (
    "target_platform",
    "genre_lane",
    "target_reader",
    "reader_expectations",
    "common_hooks",
    "saturation_risks",
    "differentiation_angle",
    "copyright_risk",
    "no_imitation_attestation",
)
WRITE_FLAGS = ("writes_canon", "writes_event_ledger", "writes_context_pack", "writes_brief")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def idea_lab_ids() -> list[str]:
    root = ROOT / "state" / "idea_lab"
    if not root.exists():
        return []
    labs: list[tuple[float, str]] = []
    for item in root.iterdir():
        if not item.is_dir():
            continue
        latest = max((path.stat().st_mtime for path in item.glob("*") if path.is_file()), default=item.stat().st_mtime)
        labs.append((latest, item.name))
    return [name for _mtime, name in sorted(labs, reverse=True)]


def resolve_idea_id(value: str) -> str | None:
    if value != "latest":
        return value
    selected = ROOT / "state" / "idea_lab" / "selected.json"
    if selected.exists():
        data = read_json(selected, {})
        idea_id = data.get("idea_id")
        if isinstance(idea_id, str) and idea_id.strip():
            return idea_id
    ids = idea_lab_ids()
    return ids[0] if ids else None


def lab_path(idea_id: str) -> Path:
    return ROOT / "state" / "idea_lab" / idea_id


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def commercial_field(commercial: dict[str, Any], key: str, default: str = "") -> str:
    value = commercial.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def input_hashes(lab: Path) -> list[dict[str, str]]:
    paths = [
        lab / "original_idea.md",
        lab / "deepseek_idea.md",
        lab / "commercial_idea.json",
        lab / "codex_synthesis.md",
    ]
    return [{"path": rel(path), "sha256": sha256(path)} for path in paths if path.exists()]


def build_report(idea_id: str) -> dict[str, Any]:
    lab = lab_path(idea_id)
    commercial = read_json(lab / "commercial_idea.json", {})
    original = read_text(lab / "original_idea.md")
    summary = " ".join(line.strip() for line in original.splitlines() if line.strip())[:240]
    report = {
        "schema_version": 1,
        "idea_id": idea_id,
        "generated_at": now_iso(),
        "status": "WARNING",
        "target_platform": commercial_field(commercial, "target_platform", "unspecified"),
        "genre_lane": commercial_field(commercial, "genre_lane", "unspecified"),
        "target_reader": commercial_field(commercial, "target_reader", "unspecified"),
        "reader_expectations": commercial.get("reader_expectations") or [],
        "common_hooks": commercial.get("core_satisfactions") or [],
        "saturation_risks": ["Advisory only: compare against source_log and forbidden_similarity before drafting."],
        "differentiation_angle": commercial_field(commercial, "differentiation_one_liner", summary or "unspecified"),
        "copyright_risk": commercial_field(commercial, "copyright_similarity_risk_statement", "unreviewed"),
        "no_imitation_attestation": commercial_field(
            commercial,
            "no_imitation_attestation",
            "Advisory scan cannot authorize imitation; hard similarity review remains required per chapter.",
        ),
        "writes_canon": False,
        "writes_event_ledger": False,
        "writes_context_pack": False,
        "writes_brief": False,
        "input_hashes": input_hashes(lab),
    }
    if all(str(report[field]).strip() and str(report[field]) != "unspecified" for field in ("target_platform", "genre_lane", "target_reader")):
        report["status"] = "READY"
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Market Scan: {report['idea_id']}", "", f"status: {report['status']}", ""]
    for field in REQUIRED_FIELDS:
        value = report.get(field)
        lines.append(f"## {field}")
        lines.append("")
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value) if value else lines.append("- none")
        else:
            lines.append(str(value or ""))
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- advisory_only: true",
            "- writes_canon: false",
            "- writes_event_ledger: false",
            "- writes_context_pack: false",
            "- writes_brief: false",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def check_report(idea_id: str) -> tuple[str, list[str], list[str]]:
    path = lab_path(idea_id) / "market_scan.json"
    if not path.exists():
        return "WARNING", [], [f"missing state/idea_lab/{idea_id}/market_scan.json"]
    report = read_json(path, {})
    blockers: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        value = report.get(field)
        if value in (None, "", [], {}):
            warnings.append(f"missing field: {field}")
    for flag in WRITE_FLAGS:
        if report.get(flag) is not False:
            blockers.append(f"market scan must not set {flag}=true")
    risk = str(report.get("copyright_risk", "")).upper()
    if any(marker in risk for marker in ("HIGH", "BLOCKED")):
        warnings.append("market scan reports high similarity/copyright risk; treat as advisory until chapter evidence")
    if blockers:
        return "BLOCKED", blockers, warnings
    return "READY" if not warnings else "WARNING", blockers, warnings


def print_check(idea_id: str) -> int:
    status, blockers, warnings = check_report(idea_id)
    print(f"# Market Scan Check: {idea_id}")
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
    parser = argparse.ArgumentParser(description="Build or check advisory market scan evidence.")
    parser.add_argument("--id", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    idea_id = resolve_idea_id(args.id)
    if not idea_id:
        print("# Market Scan Check")
        print()
        print("status: WARNING")
        print("- no idea lab found")
        return 0
    if args.check:
        return print_check(idea_id)
    lab = lab_path(idea_id)
    if not lab.exists():
        print(f"ERROR: missing idea lab state/idea_lab/{idea_id}", file=sys.stderr)
        return 1
    report = build_report(idea_id)
    write_json(lab / "market_scan.json", report)
    write_text(lab / "market_scan.md", render_markdown(report))
    print(f"OK: wrote {rel(lab / 'market_scan.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
