from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import ROOT


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def seed(repo: Path, chapters: int) -> str:
    events = []
    for number in range(1, chapters + 1):
        chapter = f"v01_c{number:03d}"
        chapter_path = Path(repo) / "chapters" / "v01" / f"c{number:03d}.md"
        brief_path = Path(repo) / "outline" / "chapter_briefs" / f"{chapter}.md"
        write(chapter_path, f"Synthetic chapter {chapter}: tracked decision and anchor.\n")
        write(brief_path, "# Brief\n\nsynthetic brief for longrun smoke\n")
        carrier = ("investigation", "dialogue", "procedure")[number % 3]
        hook = ("mystery", "cost", "relationship")[number % 3]
        write(
            Path(repo) / "reviews" / chapter / "reader_reward_gate.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "chapter": chapter,
                    "generated_at": "2000-01-01T00:00:00+00:00",
                    "status": "READY",
                    "reader_reward_intensity": "R2",
                    "official_chapter": {"path": f"chapters/v01/c{number:03d}.md", "sha256": sha(chapter_path)},
                    "official_brief": {"path": f"outline/chapter_briefs/{chapter}.md", "sha256": sha(brief_path)},
                    "contract": {
                        "reader_reward_intensity": "R2",
                        "reader_reward_delivery": "tracked decision",
                        "reward_evidence_requirement": "tracked decision",
                        "pressure_level": "H2",
                        "release_valve": "tracked decision payoff",
                        "core_mechanism_presence": "used",
                        "low_drama_carrier": carrier,
                        "small_payoff": "tracked decision",
                        "next_click_reason": f"next cost {number}",
                        "effective_progress_unit": f"before {number} -> after {number}",
                        "protagonist_action": "tracked decision",
                        "world_rule": "tracked decision changes the rule pressure",
                    },
                    "evidence_quotes": ["tracked decision"],
                    "matched_evidence_quotes": ["tracked decision"],
                    "blockers": [],
                    "warnings": [],
                    "human_acceptance": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        write(
            Path(repo) / "reviews" / chapter / "chapter_shape.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "chapter": chapter,
                    "generated_at": "2000-01-01T00:00:00+00:00",
                    "status": "READY",
                    "official_chapter": {"path": f"chapters/v01/c{number:03d}.md", "sha256": sha(chapter_path)},
                    "shape": {
                        "opening": "arrival",
                        "obstacle": carrier,
                        "resolution": "choice",
                        "hook": hook,
                        "protagonist_position": "active",
                        "protagonist_solution": "active_choice",
                        "side_character_function": "ally",
                        "exposition_load": "scene_first",
                    },
                    "shape_key": f"arrival|{carrier}|choice|{hook}|active|active_choice|ally|scene_first",
                    "repeat_count": 0,
                    "blockers": [],
                    "warnings": [],
                    "human_acceptance": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        events.append(
            {
                "event_id": f"{chapter}_e001",
                "chapter": chapter,
                "type": "character_decision",
                "fact": f"{chapter} protagonist makes a tracked decision",
                "evidence_quote": "tracked decision",
                "consequence": "state changes",
                "verified_by": "human",
                "importance": "P1",
            }
        )
        events.append(
            {
                "event_id": f"{chapter}_e002",
                "chapter": chapter,
                "type": "chapter_anchor",
                "fact": f"{chapter} anchor is confirmed",
                "evidence_quote": "anchor",
                "consequence": "next chapter inherits visible state",
                "verified_by": "human",
                "importance": "P1",
                "anchor": {
                    "end_time": f"night {number}",
                    "end_location": "test location",
                    "present_characters": ["protagonist"],
                    "protagonist_state": "alert",
                    "carried_items": ["none"],
                    "unfinished_action": "continue investigation",
                    "next_required_continuity": "start from the anchor",
                },
            }
        )
    write(repo / "state/event_ledger.jsonl", "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n")
    write(repo / "bible/rules.md", "# Rules\n\nNo placeholders in synthetic longrun smoke.\n")
    reader_promise = {
        "schema_version": 1,
        "status": "READY",
        "updated_at": "2000-01-01T00:00:00+00:00",
        "primary_genre": "悬疑",
        "secondary_genre": "成长",
        "target_reader": "喜欢强钩子和角色推进的读者",
        "platform_expectation": "前三章明确追读问题",
        "genre_profile": "悬疑成长，低动作高信息压力",
        "core_hook": "每章用异常推进主角选择",
        "core_sell_point": "异常推进主角主动选择",
        "core_mechanism_name": "异常证据",
        "allowed_low_drama_carriers": ["investigation", "dialogue", "procedure"],
        "main_reader_rewards": ["悬念推进", "主角主动改变局面"],
        "non_promises": ["不承诺纯设定百科"],
        "first_chapter_must_deliver": "异常和主角选择",
        "second_chapter_must_escalate": "第一章问题升级",
        "third_chapter_must_hook": "小兑现和更大问题",
        "three_chapter_main_question": "异常从何而来",
        "three_chapter_protagonist_specialness": "主角用独特策略改变局面",
        "per_chapter_must_have": ["主动选择", "章末点击理由"],
        "per_chapter_must_not_only_have": ["流程记录"],
        "ending_hook_priority": ["新问题", "代价"],
        "reward_mix": {"爽点": "中", "悬念": "高", "笑点": "低", "情绪点": "中"},
        "positive_promises": ["每章有主角主动改变局面的证据", "三章内有悬念推进和小兑现"],
        "negative_failure_modes": {
            "red_lines": ["不得连续高压无释放", "不得只开不合", "不得主角工具化", "不得设定百科化"],
            "no_release_max_run": 2,
            "no_payoff_max_run": 2,
            "open_without_payoff_max_run": 2,
            "passive_protagonist_max_run": 1,
            "explanation_only_max_run": 1,
            "repeated_shape_max_run": 2,
            "low_efficiency_window_chapters": 5,
            "low_efficiency_max_count": 2,
        },
        "release_valve_policy": {
            "max_high_pressure_without_release": 2,
            "minimum_release_types": ["小胜", "真相兑现", "关系推进"],
            "per_three_chapters_must_include_release": True,
            "rationale": "synthetic smoke requires visible payoff cadence.",
        },
        "protagonist_agency_policy": {
            "requires_active_goal": True,
            "requires_active_action": True,
            "requires_cost_or_consequence": True,
            "requires_state_change": True,
            "requires_desire_or_principle": True,
            "rationale": "synthetic smoke keeps protagonist agency visible.",
        },
        "information_clarity_policy": {
            "max_consecutive_setup_only_chapters": 2,
            "require_scene_test_for_world_rule": True,
            "forbid_explanation_only_worldbuilding": True,
            "rationale": "synthetic smoke avoids explanation-only worldbuilding.",
        },
        "language_experience_policy": {
            "forbid_summary_voice": True,
            "require_memorable_line_or_detail": True,
            "max_explanation_paragraphs_without_scene": 2,
            "rationale": "synthetic smoke keeps language checks enabled.",
        },
        "structural_efficiency_policy": {
            "min_effective_progress_per_chapter": "before -> after",
            "max_words_without_state_change": 6000,
            "max_low_progress_window_count": 2,
            "window_chapters": 5,
            "rationale": "synthetic smoke requires efficient state movement.",
        },
        "reader_reward_intensity_policy": {
            "opening_chapter_count": 3,
            "opening_intensity_by_chapter": {"v01_c001": "R2", "v01_c002": "R2", "v01_c003": "R2"},
            "default_chapter_intensity": "R2",
            "allowed_chapter_overrides": {},
            "rationale": "longrun smoke 使用固定中爽节奏，只验证治理链路。",
        },
        "genre_mismatch_red_lines": ["不得只有设定说明"],
        "source_boundary": "instruction_only_not_fact_source",
    }
    write(repo / "state/project_reader_promise.json", json.dumps(reader_promise, ensure_ascii=False, indent=2) + "\n")
    write(repo / "state/project_reader_promise.md", "# Project Reader Promise\n\nstatus: READY\nsource_boundary: instruction_only_not_fact_source\n")
    target = f"v01_c{chapters:03d}"
    pack = "# Context Pack\n\n" + "\n".join(item["event_id"] for item in events[:-2]) + "\n"
    pack_rel = f"state/context_pack/{target}.md"
    manifest_rel = f"state/context_pack/{target}.manifest.json"
    write(repo / pack_rel, pack)
    sections = [
        {"id": "core_freeze", "body_chars": 20, "sources": [{"path": "bible/rules.md"}]},
        {"id": "chapter_brief", "body_chars": 20, "sources": [{"path": f"outline/chapter_briefs/{target}.md"}]},
        {"id": "chapter_anchor_continuity", "body_chars": 20, "sources": [{"event_id": events[-3]["event_id"]}]},
        {"id": "active_aftermath_obligations", "body_chars": 20, "sources": [{"path": "state/derived/pacing/aftermath_obligations.json"}]},
        {
            "id": "book_outline_contract",
            "body_chars": 20,
            "included_reason": "strategic_plan_not_fact_source",
            "sources": [
                {"path": "outline/book_outline.json", "note": "strategic_plan_not_fact_source"},
                {"path": "outline/book_outline.md", "note": "strategic_plan_not_fact_source"},
            ],
        },
        {
            "id": "style_instruction",
            "body_chars": 20,
            "included_reason": "style_instruction_not_fact_source",
            "sources": [
                {"path": "state/project_style_contract.json", "note": "style_instruction_not_fact_source"},
                {"path": "state/project_style_contract.md", "note": "style_instruction_not_fact_source"},
                {"path": "bible/style_guide.md", "note": "style_instruction_not_fact_source"},
            ],
        },
        {"id": "authorized_elements_full", "body_chars": 20, "sources": [{"path": f"outline/chapter_briefs/{target}.md"}]},
        {"id": "rules_and_boundaries", "body_chars": 20, "sources": [{"path": "bible/rules.md"}]},
        {
            "id": "reader_promise",
            "body_chars": 20,
            "included_reason": "reader_promise_instruction_not_fact_source",
            "sources": [
                {"path": "state/project_reader_promise.json", "note": "instruction_not_fact_source"},
                {"path": "state/project_reader_promise.md", "note": "instruction_not_fact_source"},
            ],
        },
        {
            "id": "reader_experience_state",
            "body_chars": 20,
            "sources": [
                {"path": "state/derived/personality/protagonist.json"},
                {"path": "state/derived/protagonist_progression.json"},
                {"path": "state/derived/world_reveal_ledger.json"},
                {"path": "state/derived/suspense_ledger.json"},
            ],
        },
        {"id": "recent_events", "body_chars": len(pack), "sources": [{"event_id": item["event_id"]} for item in events[:-2]]},
    ]
    manifest = {
        "schema_version": 2,
        "chapter": target,
        "generated_at": "2000-01-01T00:00:00+00:00",
        "budget_chars": 200000,
        "hard_max_chars": 300000,
        "allow_truncated": False,
        "pack_truncated": False,
        "pack_chars": len(pack),
        "object_ids": [],
        "ability_ids": [],
        "sections": sections,
        "input_hashes": [
            {"path": "state/event_ledger.jsonl", "sha256": sha(repo / "state/event_ledger.jsonl")},
            {"path": "bible/rules.md", "sha256": sha(repo / "bible/rules.md")},
        ],
        "context_pack": {"path": pack_rel, "sha256": sha(repo / pack_rel), "chars": len(pack)},
    }
    write(repo / manifest_rel, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic long-run governance smoke in a temporary copy.")
    parser.add_argument("--chapters", type=int, default=10)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()
    if args.chapters < 1:
        print("ERROR: --chapters must be >= 1", file=sys.stderr)
        return 1
    temp = tempfile.mkdtemp(prefix="novel_longrun_")
    repo = Path(temp) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "backups", "exports"))
    target = seed(repo, args.chapters)
    steps = [
        ("derive", ("scripts/novel.py", "derive")),
        ("context-quality", ("scripts/novel.py", "context-quality", target)),
        ("pacing-dashboard", ("scripts/novel.py", "pacing-dashboard", target)),
        ("long-health", ("scripts/novel.py", "long-health", "--to", target)),
        ("reader-risk-index", ("scripts/novel.py", "reader-risk-index", "--to", target)),
        ("gate-rehearsal", ("scripts/novel.py", "gate-rehearsal", "A")),
    ]
    ok = True
    for name, command in steps:
        result = run(repo, *command)
        status = "OK" if result.returncode == 0 else "FAIL"
        print(f"# {name}: {status}")
        if result.returncode != 0:
            ok = False
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
    if args.keep_temp:
        print(f"temp_repo: {repo}")
    else:
        shutil.rmtree(temp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
