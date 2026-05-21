from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, read_json, read_text
from brief_contract import PROGRESS_CONTRACT_SECTIONS, progress_value
from element_context import markdown_sections, section_body
from reader_personality_contracts import validate_reader_promise


RETENTION_SECTIONS = ("本章留存合同", "Reader Retention Contract")
TITLE_SECTIONS = ("章节标题", "Chapter Title")


def chapter_ids() -> list[str]:
    ids = {path.stem for path in (ROOT / "outline" / "chapter_briefs").glob("v*_c*.md")}
    ids.update(path.name for path in (ROOT / "reviews").glob("v*_c*"))
    for path in (ROOT / "chapters").glob("v*/c*.md"):
        ids.add(f"{path.parent.name}_{path.stem}")
    return sorted(ids)


def brief_gaps(chapter: str) -> list[str]:
    path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    if not path.exists():
        return ["missing official brief"]
    parsed = markdown_sections(read_text(path))
    progress = section_body(parsed, PROGRESS_CONTRACT_SECTIONS)
    retention = section_body(parsed, RETENTION_SECTIONS)
    gaps: list[str] = []
    if not section_body(parsed, TITLE_SECTIONS).strip():
        gaps.append("missing 章节标题")
    for key in ("effective_progress_type", "effective_progress_unit", "effective_progress_evidence_target"):
        if not progress_value(progress, key).strip():
            gaps.append(f"missing {key}")
    for key in (
        "reader_reward_intensity",
        "reader_reward_type",
        "reader_reward_delivery",
        "reader_reward_timing",
        "reward_evidence_requirement",
        "low_drama_carrier",
        "low_drama_progress_type",
        "core_mechanism_presence",
        "core_mechanism_silent_count",
        "waiting_ending_debt",
    ):
        if not progress_value(retention, key).strip():
            gaps.append(f"missing {key}")
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description="Report reader reward migration gaps without auto-accepting anything.")
    parser.parse_args()
    promise = read_json(ROOT / "state" / "project_reader_promise.json", {})
    promise_errors = validate_reader_promise(promise, require_ready=True)
    print("# Reader Reward Migration Report")
    print()
    if promise_errors:
        print("## Reader Promise Gaps")
        print()
        for error in promise_errors:
            print(f"- {error}")
        print()

    missing = False
    for chapter in chapter_ids():
        gaps = brief_gaps(chapter)
        gate_json = ROOT / "reviews" / chapter / "reader_reward_gate.json"
        gate_md = ROOT / "reviews" / chapter / "reader_reward_gate.md"
        if not gate_json.exists():
            gaps.append("missing reader_reward_gate.json")
        if not gate_md.exists():
            gaps.append("missing reader_reward_gate.md")
        if gaps:
            missing = True
            print(f"## {chapter}")
            print()
            for gap in gaps:
                print(f"- {gap}")
            print()
    if not promise_errors and not missing:
        print("status: READY")
    else:
        print("status: NOT_READY")
    return 1 if promise_errors or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
