from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, write_json
from brief_contract import EFFECTIVE_PROGRESS_TYPES, concrete_value, is_none_body
from reader_reward_policy import POLICY_PATH, READER_PROMISE_PATH, file_ref, level_rules, sha256


CORE_SILENT_VALUES = {"silent", "intentionally_absent", "none", "absent", "未出现"}
HOOK_MARKERS = {
    "waiting": ("等待", "待", "追查", "即将", "next_chapter_must"),
    "mystery": ("谁", "为何", "为什么", "真相", "谜", "异常"),
    "cost": ("代价", "后果", "追责", "债"),
    "threat": ("危险", "威胁", "逼近", "敌"),
    "relationship": ("关系", "背叛", "信任", "家属", "亲密"),
}


def chapter_sort_key(path: Path) -> tuple[str, int]:
    chapter = path.parent.name
    try:
        return chapter[:3], int(chapter[-3:])
    except ValueError:
        return chapter, 0


def gate_files() -> list[Path]:
    return sorted((ROOT / "reviews").glob("v*_c*/reader_reward_gate.json"), key=chapter_sort_key)


def as_int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def gate_ref(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path) if path.exists() else ""}


def hook_type(value: str) -> str:
    text = str(value or "").lower()
    for name, markers in HOOK_MARKERS.items():
        if any(marker.lower() in text for marker in markers):
            return name
    return "unclear" if text.strip() else "missing"


def build_index() -> dict[str, Any]:
    chapters: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    waiting_run = 0
    core_silence_run = 0
    small_payoff_gap = 0
    low_drama_run = 0
    previous_low_carrier = ""
    no_payoff_run = 0
    hook_repeat_run = 0
    previous_hook = ""

    for path in gate_files():
        data = read_json(path, {})
        if not isinstance(data, dict):
            blockers.append(f"{path.parent.name}: reader_reward_gate.json is malformed")
            continue
        chapter = str(data.get("chapter") or path.parent.name)
        intensity = str(data.get("reader_reward_intensity", "")).strip().upper()
        rules = level_rules(intensity)
        contract = data.get("contract") if isinstance(data.get("contract"), dict) else {}
        source_status = str(data.get("status", "MISSING")).strip().upper()
        source_gate_blockers = data.get("blockers") if isinstance(data.get("blockers"), list) else []
        cross_blockers: list[str] = []
        cross_warnings: list[str] = []
        source_blockers: list[str] = []

        if source_status == "BLOCKED":
            if source_gate_blockers:
                source_blockers.extend(f"source gate BLOCKED: {item}" for item in source_gate_blockers)
            else:
                source_blockers.append("source gate status is BLOCKED")
        elif source_status not in {"READY", "WARNING", "ACCEPTED_BY_HUMAN"}:
            source_blockers.append(f"source gate status is {source_status or 'MISSING'}")
        elif source_status == "WARNING":
            cross_warnings.append("source gate status is WARNING")

        debt = str(contract.get("waiting_ending_debt", "")).strip().lower()
        if debt and debt not in {"none", "无"} and "waiting" in debt:
            waiting_run += 1
        else:
            waiting_run = 0
        waiting_limit = int(rules.get("waiting_ending_max_run") or 999)
        if waiting_run > waiting_limit:
            cross_blockers.append(f"连续等待结尾 {waiting_run} 章，超过 {intensity} 阈值 {waiting_limit}")

        presence = str(contract.get("core_mechanism_presence", "")).strip().lower().strip("。；;,.，")
        silent_count = as_int(contract.get("core_mechanism_silent_count"))
        if presence in CORE_SILENT_VALUES:
            core_silence_run += 1
        else:
            core_silence_run = 0
        effective_silence = max(core_silence_run, silent_count or 0)
        core_limit = int(rules.get("core_mechanism_max_silent_chapters") or 999)
        if effective_silence > core_limit:
            cross_blockers.append(f"核心机制沉默 {effective_silence} 章，超过 {intensity} 阈值 {core_limit}")

        small_payoff = str(contract.get("small_payoff", "")).strip()
        matched = data.get("matched_evidence_quotes")
        has_payoff = concrete_value(small_payoff, min_chars=2) and isinstance(matched, list) and bool(matched)
        if has_payoff:
            small_payoff_gap = 0
            no_payoff_run = 0
        else:
            small_payoff_gap += 1
            no_payoff_run += 1
        payoff_limit = int(rules.get("max_small_payoff_gap") or 999)
        if small_payoff_gap > payoff_limit:
            cross_blockers.append(f"小兑现间隔 {small_payoff_gap} 章，超过 {intensity} 阈值 {payoff_limit}")
        if no_payoff_run >= 3:
            cross_blockers.append(f"连续 {no_payoff_run} 章无正文可匹配小兑现")

        low_carrier = str(contract.get("low_drama_carrier", "")).strip().lower()
        low_progress = str(contract.get("low_drama_progress_type", "")).strip()
        active_low = bool(low_carrier and low_carrier not in {"none", "无"})
        ineffective_low = active_low and low_progress not in EFFECTIVE_PROGRESS_TYPES
        if active_low and low_carrier == previous_low_carrier:
            low_drama_run += 1
        elif active_low:
            low_drama_run = 1
        else:
            low_drama_run = 0
        previous_low_carrier = low_carrier if active_low else ""
        low_limit = int(rules.get("low_drama_repeat_max_run") or 999)
        if ineffective_low and low_drama_run > low_limit:
            cross_blockers.append(f"低戏剧载体 {low_carrier} 连续 {low_drama_run} 章且无有效变化，超过 {intensity} 阈值 {low_limit}")
        if low_drama_run >= 3 and chapter_number(chapter) >= 6:
            cross_blockers.append(f"第 6 章后低戏剧载体 {low_carrier} 连续 {low_drama_run} 章")
        elif low_carrier and low_carrier not in {"none", "无"}:
            cross_warnings.append(f"低戏剧载体 {low_carrier} 已记录；若连续使用必须承载有效变化")

        current_hook = hook_type(str(contract.get("next_click_reason", "")))
        if current_hook == previous_hook and current_hook not in {"missing", "unclear"}:
            hook_repeat_run += 1
        else:
            hook_repeat_run = 1
        previous_hook = current_hook
        if hook_repeat_run >= 3 and chapter_number(chapter) >= 6:
            cross_blockers.append(f"第 6 章后章末钩子类型 {current_hook} 连续 {hook_repeat_run} 章")

        item = {
            "chapter": chapter,
            "reader_reward_intensity": intensity,
            "gate": gate_ref(path),
            "status": data.get("status"),
            "source_blockers": source_blockers,
            "waiting_ending_run": waiting_run,
            "core_mechanism_silent_run": effective_silence,
            "small_payoff_gap": small_payoff_gap,
            "low_drama_repeat_run": low_drama_run,
            "no_payoff_run": no_payoff_run,
            "hook_type": current_hook,
            "hook_repeat_run": hook_repeat_run,
            "cross_blockers": cross_blockers,
            "cross_warnings": cross_warnings,
        }
        chapters.append(item)
        blockers.extend(f"{chapter}: {message}" for message in source_blockers)
        blockers.extend(f"{chapter}: {message}" for message in cross_blockers)
        warnings.extend(f"{chapter}: {message}" for message in cross_warnings)

    status = "BLOCKED" if blockers else ("WARNING" if warnings else "READY")
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "source_policy": file_ref(POLICY_PATH),
        "source_reader_promise": file_ref(READER_PROMISE_PATH),
        "chapters": chapters,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the cross-chapter reader reward index.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = build_index()
    if args.write:
        write_json(ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json", data)
    print("# Reader Reward Index")
    print()
    print(f"status: {data['status']}")
    for item in data["blockers"]:
        print(f"- {item}")
    for item in data["warnings"]:
        print(f"- WARNING: {item}")
    return 1 if data["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
