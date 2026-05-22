from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from brief_contract import (
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    PROGRESS_CONTRACT_SECTIONS,
    concrete_value,
    extract_labeled_value,
    has_placeholder,
    is_none_body,
    progress_value,
)
from element_context import brief_schema_version, markdown_sections, section_body
from reader_reward_policy import (
    POLICY_PATH,
    READER_PROMISE_PATH,
    configured_intensity_for_chapter,
    file_ref,
    level_rules,
    load_policy,
    load_reader_promise,
    normalize_intensity,
    sha256,
)
from review_binding import official_chapter_path, quote_matches_text


BRIEF_SECTIONS = ("章节标题", "Chapter Title")
RETENTION_SECTIONS = ("本章留存合同", "Reader Retention Contract")
END_STATE_CHANGE_SECTIONS = ("章末状态变化", "End State Change")
STORY_CARD_SECTIONS = ("Story Card",)
PLACEHOLDER_TITLES = {"标题", "章节标题", "chapter title", "todo", "tbd", "待定", "待填", "无题"}
CORE_PRESENT = {"used", "limited", "backfired", "upgraded", "misled", "revealed"}
CORE_ABSENT = {"silent", "intentionally_absent", "none", "absent", "未出现"}
ALTERNATIVE_REWARD_MARKERS = ("替代", "关系", "信息", "代价", "反转", "兑现", "权力", "情绪", "悬念")
COUNTER_TURN_MARKERS = ("反制", "转折", "反转", "payoff", "兑现", "压迫", "counter", "turn")
WORLD_RULE_SCENE_TEST_MARKERS = (
    "选择",
    "拒绝",
    "误用",
    "代价",
    "后果",
    "反应",
    "发现",
    "看见",
    "删除",
    "覆盖",
    "催促",
    "承担",
    "伤",
    "怕",
)
HIGH_PRESSURE_VALUES = {"H3", "H4", "W3", "W4", "HIGH", "高", "强压", "爆发"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def title_is_ready(title: str) -> bool:
    value = title.strip().lstrip("#").strip()
    if not value:
        return False
    if value.lower() in PLACEHOLDER_TITLES or value in PLACEHOLDER_TITLES:
        return False
    return not has_placeholder(value)


def official_title_failure(chapter: str) -> str:
    path = official_chapter_path(chapter)
    if not path.exists():
        return f"{chapter}: missing official chapter {rel(path)}"
    first_line = read_text(path).splitlines()[0].lstrip("\ufeff") if read_text(path).splitlines() else ""
    if not first_line.startswith("# "):
        return f"{chapter}: official chapter first line must be a non-placeholder H1 title"
    if not title_is_ready(first_line[2:]):
        return f"{chapter}: official chapter H1 title must be non-placeholder"
    return ""


def brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def labeled_value(body: str, key: str) -> str:
    return extract_labeled_value(body, (key,))


def labeled_values(chapter: str) -> tuple[dict[str, str], list[str]]:
    path = brief_path(chapter)
    if not path.exists():
        return {}, [f"{chapter}: missing official brief {rel(path)}"]
    brief_text = read_text(path)
    schema_version = brief_schema_version(brief_text)
    parsed = markdown_sections(brief_text)
    progress = section_body(parsed, PROGRESS_CONTRACT_SECTIONS)
    retention = section_body(parsed, RETENTION_SECTIONS)
    cost = section_body(parsed, COST_CONSEQUENCE_CONTRACT_SECTIONS)
    end_state = section_body(parsed, END_STATE_CHANGE_SECTIONS)
    story = section_body(parsed, STORY_CARD_SECTIONS)
    title = section_body(parsed, BRIEF_SECTIONS).strip()
    values = {
        "title": title,
        "brief_schema_version": str(schema_version),
        "effective_progress_type": progress_value(progress, "effective_progress_type"),
        "effective_progress_unit": progress_value(progress, "effective_progress_unit"),
        "effective_progress_evidence_target": progress_value(progress, "effective_progress_evidence_target"),
        "reader_reward_intensity": normalize_intensity(progress_value(retention, "reader_reward_intensity")),
        "reader_reward_type": progress_value(retention, "reader_reward_type"),
        "reader_reward_delivery": progress_value(retention, "reader_reward_delivery"),
        "reader_reward_timing": progress_value(retention, "reader_reward_timing"),
        "reward_evidence_requirement": progress_value(retention, "reward_evidence_requirement"),
        "pressure_level": progress_value(retention, "pressure_level") or progress_value(cost, "pressure_level"),
        "release_valve": progress_value(retention, "release_valve"),
        "low_drama_carrier": progress_value(retention, "low_drama_carrier"),
        "low_drama_progress_type": progress_value(retention, "low_drama_progress_type"),
        "core_mechanism_presence": progress_value(retention, "core_mechanism_presence").strip(),
        "core_mechanism_silent_count": progress_value(retention, "core_mechanism_silent_count").strip(),
        "waiting_ending_debt": progress_value(retention, "waiting_ending_debt").strip(),
        "small_payoff": progress_value(retention, "chapter_small_payoff"),
        "next_click_reason": progress_value(retention, "next_click_reason"),
        "protagonist_goal": labeled_value(story, "主角本章想要"),
        "protagonist_action": labeled_value(story, "主角主动动作") or section_body(parsed, ("主角主动选择",)).strip(),
        "protagonist_cost_or_consequence": progress_value(cost, "cost_paid_now") or progress_value(cost, "aftermath_obligation"),
        "protagonist_state_change": labeled_value(story, "before -> after") or progress_value(progress, "effective_progress_unit"),
        "protagonist_desire_or_principle": labeled_value(story, "主角本章想要") or progress_value(retention, "protagonist_desire_or_principle"),
        "world_rule": labeled_value(story, "本章只讲懂的一条世界规则"),
        "cost_paid_now": progress_value(cost, "cost_paid_now"),
        "aftermath_obligation": progress_value(cost, "aftermath_obligation"),
        "end_state_change": end_state,
    }
    blockers: list[str] = []
    if not title_is_ready(title):
        blockers.append(f"{chapter}: official brief 章节标题 must be non-placeholder")
    return values, blockers


def extract_quote_candidates(*values: str) -> list[str]:
    candidates: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or has_placeholder(text) or is_none_body(text):
            continue
        quoted = re.findall(r"[“\"'「『](.{4,160}?)[”\"'」』]", text)
        for item in quoted:
            candidates.append(item.strip())
        if quoted:
            continue
        for part in re.split(r"[；;|\n]", text):
            item = part.strip().strip("。")
            item = re.sub(r"^(正文中?应?该?能?匹配到?的?|证据句|场面描述|必须出现)[:：]", "", item).strip()
            if 6 <= len("".join(item.split())) <= 160:
                candidates.append(item)
    deduped: list[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def matched_quotes(candidates: list[str], source_text: str) -> list[str]:
    return [quote for quote in candidates if quote_matches_text(quote, source_text)]


def has_world_rule_scene_test(source_text: str) -> bool:
    return any(marker in source_text for marker in WORLD_RULE_SCENE_TEST_MARKERS)


def high_pressure(value: str) -> bool:
    text = str(value or "").strip().upper()
    return text in HIGH_PRESSURE_VALUES or any(marker in str(value or "") for marker in ("高压", "强压", "爆发", "H3", "H4", "W3", "W4"))


def review_body_hash(data: dict[str, Any]) -> str:
    clean = dict(data)
    clean.pop("human_acceptance", None)
    clean.pop("status", None)
    body = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def acceptance_current(data: dict[str, Any]) -> bool:
    acceptance = data.get("human_acceptance")
    if not isinstance(acceptance, dict):
        return False
    required = (
        "accepted_by",
        "accepted_at",
        "reason",
        "compensation_evidence_quote",
        "next_chapter_obligation",
        "official_chapter_sha256",
        "official_brief_sha256",
        "reader_promise_sha256",
        "policy_sha256",
        "review_sha256",
    )
    if any(not str(acceptance.get(field, "")).strip() for field in required):
        return False
    if acceptance.get("accepted_by") != "human":
        return False
    official = data.get("official_chapter", {})
    brief = data.get("official_brief", {})
    hashes = {item.get("path"): item.get("sha256") for item in data.get("input_hashes", []) if isinstance(item, dict)}
    if acceptance.get("official_chapter_sha256") != official.get("sha256"):
        return False
    if acceptance.get("official_brief_sha256") != brief.get("sha256"):
        return False
    if acceptance.get("reader_promise_sha256") != hashes.get("state/project_reader_promise.json"):
        return False
    if acceptance.get("policy_sha256") != hashes.get("ops/reader_reward_policy.json"):
        return False
    return acceptance.get("review_sha256") == review_body_hash(data)


def build_gate(chapter: str) -> dict[str, Any]:
    volume, chapter_file = chapter_parts(chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    brief = brief_path(chapter)
    existing = read_json(ROOT / "reviews" / chapter / "reader_reward_gate.json", {})
    existing_acceptance = existing.get("human_acceptance") if isinstance(existing, dict) else None

    policy = load_policy()
    promise = load_reader_promise()
    values, blockers = labeled_values(chapter)
    title_failure = official_title_failure(chapter)
    if title_failure:
        blockers.append(title_failure)

    configured_intensity, intensity_errors, intensity_source = configured_intensity_for_chapter(chapter, promise)
    blockers.extend(f"{chapter}: {item}" for item in intensity_errors)
    brief_intensity = values.get("reader_reward_intensity", "")
    if not brief_intensity:
        blockers.append(f"{chapter}: brief missing reader_reward_intensity")
    elif configured_intensity and brief_intensity != configured_intensity:
        blockers.append(
            f"{chapter}: reader_reward_intensity {brief_intensity} conflicts with reader promise {configured_intensity} ({intensity_source})"
        )

    source_text = read_text(chapter_path)
    quote_candidates = extract_quote_candidates(
        values.get("reward_evidence_requirement", ""),
        values.get("effective_progress_evidence_target", ""),
        values.get("reader_reward_delivery", ""),
        values.get("protagonist_action", ""),
        values.get("world_rule", ""),
    )
    matched = matched_quotes(quote_candidates, source_text)

    rules = level_rules(brief_intensity, policy)
    if rules.get("reward_evidence_required") and not matched:
        blockers.append(f"{chapter}: R2+ 缺正文 reward evidence")
    if not concrete_value(values.get("effective_progress_unit", "")) or (
        "->" not in values.get("effective_progress_unit", "") and "→" not in values.get("effective_progress_unit", "")
    ):
        blockers.append(f"{chapter}: 缺有效推进单位 before -> after")
    if not concrete_value(values.get("reader_reward_delivery", "")):
        blockers.append(f"{chapter}: 缺读者回报说明 reader_reward_delivery")
    if not concrete_value(values.get("next_click_reason", "")):
        blockers.append(f"{chapter}: 缺章末继续阅读理由")
    if values.get("brief_schema_version") == "2":
        action_quotes = matched_quotes(extract_quote_candidates(values.get("protagonist_action", "")), source_text)
        if not action_quotes:
            blockers.append(f"{chapter}: 缺正文主角主动动作 evidence")
        for key, label in (
            ("protagonist_goal", "主角主动目标"),
            ("protagonist_cost_or_consequence", "主角承担代价或后果"),
            ("protagonist_state_change", "主角改变局面或状态"),
            ("protagonist_desire_or_principle", "主角欲望、私心或原则"),
        ):
            if not concrete_value(values.get(key, "")):
                blockers.append(f"{chapter}: 缺{label} evidence")
        world_rule = values.get("world_rule", "")
        if concrete_value(world_rule, min_chars=2):
            world_quotes = matched_quotes(extract_quote_candidates(world_rule), source_text)
            if not world_quotes:
                blockers.append(f"{chapter}: 世界规则未在正文场景中形成可匹配 evidence")
            elif not has_world_rule_scene_test(source_text):
                blockers.append(f"{chapter}: 世界规则只有解释，缺少选择、误用、代价或人物反应的场景测试")
        else:
            blockers.append(f"{chapter}: 缺本章世界规则场景测试")
        pressure = values.get("pressure_level", "")
        release = values.get("release_valve", "")
        if not concrete_value(pressure, min_chars=1):
            blockers.append(f"{chapter}: 缺释放阀预算 pressure_level")
        if high_pressure(pressure) and not concrete_value(release, min_chars=2):
            blockers.append(f"{chapter}: 高压章节缺释放阀 release_valve")

    presence = values.get("core_mechanism_presence", "").strip()
    presence_normalized = presence.lower().strip("。；;,.，")
    core_touched = presence_normalized in CORE_PRESENT
    delivery = values.get("reader_reward_delivery", "")
    alternative_reward = any(marker in delivery for marker in ALTERNATIVE_REWARD_MARKERS)
    if rules.get("core_touch_required") and not core_touched and not alternative_reward:
        blockers.append(f"{chapter}: R3/R4 缺核心卖点触达或替代回报证据")

    if brief_intensity == "R4":
        counter_text = " ".join(
            [
                values.get("effective_progress_type", ""),
                values.get("reader_reward_type", ""),
                values.get("reader_reward_delivery", ""),
                values.get("small_payoff", ""),
            ]
        )
        if not any(marker in counter_text for marker in COUNTER_TURN_MARKERS):
            blockers.append(f"{chapter}: R4 缺转折、反制或兑现")
        if not concrete_value(values.get("cost_paid_now", "")) and not concrete_value(values.get("aftermath_obligation", "")):
            blockers.append(f"{chapter}: R4 缺代价或后果承接")

    warnings: list[str] = []
    if presence_normalized in CORE_ABSENT and brief_intensity in {"R0", "R1", "R2"}:
        warnings.append(f"{chapter}: 核心机制本章未出现，需由 index 跟踪沉默计数")
    if values.get("low_drama_carrier", "").strip().lower() not in {"", "none", "无"}:
        if not concrete_value(values.get("low_drama_progress_type", ""), min_chars=2):
            blockers.append(f"{chapter}: 低戏剧载体存在但未声明承载的推进类型")

    official_ref = {"path": rel(chapter_path), "sha256": sha256(chapter_path) if chapter_path.exists() else ""}
    brief_ref = {"path": rel(brief), "sha256": sha256(brief) if brief.exists() else ""}
    gate = {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "BLOCKED" if blockers else ("WARNING" if warnings else "READY"),
        "reader_reward_intensity": brief_intensity or configured_intensity or "R0",
        "configured_intensity": configured_intensity,
        "intensity_source": intensity_source,
        "official_chapter": official_ref,
        "official_brief": brief_ref,
        "input_hashes": [brief_ref, file_ref(READER_PROMISE_PATH), file_ref(POLICY_PATH)],
        "policy_rules": rules,
        "contract": values,
        "evidence_quotes": quote_candidates,
        "matched_evidence_quotes": matched,
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": existing_acceptance if isinstance(existing_acceptance, dict) else None,
    }
    if gate["human_acceptance"] and acceptance_current(gate):
        gate["status"] = "ACCEPTED_BY_HUMAN"
    return gate


def render_markdown(gate: dict[str, Any]) -> str:
    official = gate.get("official_chapter", {})
    brief = gate.get("official_brief", {})
    input_hashes = {item.get("path"): item.get("sha256") for item in gate.get("input_hashes", []) if isinstance(item, dict)}
    lines = [
        f"# Reader Reward Gate: {gate.get('chapter', '')}",
        "",
        f"status: {gate.get('status', '')}",
        f"official_chapter_sha256: {official.get('sha256', '')}",
        f"official_brief_sha256: {brief.get('sha256', '')}",
        f"reader_promise_sha256: {input_hashes.get('state/project_reader_promise.json', '')}",
        f"policy_sha256: {input_hashes.get('ops/reader_reward_policy.json', '')}",
        "",
        "## Contract Checked",
        "",
        f"- reader_reward_intensity: {gate.get('reader_reward_intensity', '')}",
        f"- configured_intensity: {gate.get('configured_intensity', '')}",
        f"- intensity_source: {gate.get('intensity_source', '')}",
        "",
        "## Evidence Quotes",
        "",
    ]
    quotes = gate.get("matched_evidence_quotes") or gate.get("evidence_quotes") or []
    lines.extend(f"- {quote}" for quote in quotes)
    if not quotes:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    blockers = gate.get("blockers") or []
    lines.extend(f"- {item}" for item in blockers)
    if not blockers:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = gate.get("warnings") or []
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- none")
    acceptance = gate.get("human_acceptance")
    lines.extend(["", "## Human Acceptance", ""])
    if isinstance(acceptance, dict):
        for key in (
            "accepted_by",
            "accepted_at",
            "reason",
            "compensation_evidence_quote",
            "next_chapter_obligation",
        ):
            lines.append(f"- {key}: {acceptance.get(key, '')}")
    else:
        lines.extend(["- accepted_by:", "- accepted_at:", "- reason:", "- compensation_evidence_quote:", "- next_chapter_obligation:"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a chapter's reader reward contract and evidence.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    gate = build_gate(args.chapter)
    if args.write:
        target_dir = ROOT / "reviews" / args.chapter
        target_dir.mkdir(parents=True, exist_ok=True)
        write_json(target_dir / "reader_reward_gate.json", gate)
        write_text(target_dir / "reader_reward_gate.md", render_markdown(gate))

    print(f"# Reader Reward Gate: {args.chapter}")
    print()
    print(f"status: {gate['status']}")
    for item in gate.get("blockers", []):
        print(f"- {item}")
    for item in gate.get("warnings", []):
        print(f"- WARNING: {item}")
    return 1 if gate["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
