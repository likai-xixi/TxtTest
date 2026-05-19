from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, read_text
from _common import chapter_number
from element_context import (
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    USABLE_OBJECT_ID_SECTIONS,
    declared_ids,
    markdown_sections,
    missing_section,
    section_body,
    yaml_id_index,
)
from brief_contract import (
    BASE_REQUIRED_SECTIONS,
    CONTINUITY_REQUIRED_SECTIONS,
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    EXTERNAL_PRESSURE_SECTIONS,
    HIGH_IMPACT_SCALES,
    HIGH_S_LEVELS,
    HIGH_W_LEVELS,
    IMPACT_SCALES,
    INHERITED_CHANGE_SECTIONS,
    LEDGER_EVENT_TYPES,
    LOW_IMPACT_SCALES,
    LOW_S_LEVELS,
    LOW_W_LEVELS,
    MAINLINE_TRACTION_SECTIONS,
    OPENING_SCENE_ANCHOR_SECTIONS,
    PACING_NOTE_SECTIONS,
    PACING_PURPOSE_SECTIONS,
    PACING_REQUIRED_SECTIONS,
    PLACEHOLDER_MARKERS,
    PREVIOUS_CHAPTER_ANCHOR_SECTIONS,
    PROGRESS_CONTRACT_SECTIONS,
    PROGRESS_IMPORTANCE_LEVELS,
    PROGRESS_REQUIRED_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
    SCENE_CONTINUITY_SECTIONS,
    SCENE_CONTINUITY_TYPES,
    anchor_location,
    anchor_value,
    concrete_value,
    digestion_window_chapters,
    has_placeholder,
    is_opening_chapter_anchor,
    is_yes,
    is_none_body,
    level_explanation_is_concrete,
    normalized_consequence_level,
    normalized_impact_scale,
    normalized_progress_mode,
    parse_pacing_level,
    progress_value,
    scene_continuity_note,
    scene_continuity_note_is_concrete,
    scene_continuity_type,
)


REQUIRED_SECTIONS = BASE_REQUIRED_SECTIONS
REQUIRED_ELEMENT_SECTIONS = (
    USABLE_OBJECT_ID_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
)


def check_pacing_sections(parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for aliases in PACING_REQUIRED_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required section: {label}")
        elif has_placeholder(body):
            failures.append(f"section still has placeholder text: {label}")

    mainline = section_body(parsed, MAINLINE_TRACTION_SECTIONS)
    if mainline:
        level, explanation = parse_pacing_level(mainline, "S")
        if level is None:
            failures.append("invalid 主线牵引档位: must start with S0-S4")
        elif not level_explanation_is_concrete(explanation):
            failures.append("主线牵引档位 must include a concrete explanation after the level")

    external = section_body(parsed, EXTERNAL_PRESSURE_SECTIONS)
    if external:
        level, explanation = parse_pacing_level(external, "W")
        if level is None:
            failures.append("invalid 外部压力档位: must start with W0-W4")
        elif not level_explanation_is_concrete(explanation):
            failures.append("外部压力档位 must include a concrete explanation after the level")

    inherited = section_body(parsed, INHERITED_CHANGE_SECTIONS)
    if inherited and is_none_body(inherited):
        failures.append("本章继承变化 must describe a concrete carried-forward change")

    purpose = section_body(parsed, PACING_PURPOSE_SECTIONS)
    if purpose and is_none_body(purpose):
        failures.append("本章节奏用途 must not be none")

    note = section_body(parsed, PACING_NOTE_SECTIONS)
    if note and is_none_body(note):
        failures.append("节奏说明 must not be none")
    return failures


def check_required_anchor_fields(body: str, fields: tuple[str, ...], label: str) -> list[str]:
    failures: list[str] = []
    for field in fields:
        value = anchor_value(body, field)
        if not value:
            failures.append(f"{label} missing field: {field}")
        elif has_placeholder(value) or is_none_body(value):
            failures.append(f"{label} field is not ready: {field}")
    return failures


def check_scene_continuity_sections(chapter: str, parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for aliases in CONTINUITY_REQUIRED_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required section: {label}")
        elif has_placeholder(body):
            failures.append(f"section still has placeholder text: {label}")

    previous = section_body(parsed, PREVIOUS_CHAPTER_ANCHOR_SECTIONS)
    opening = section_body(parsed, OPENING_SCENE_ANCHOR_SECTIONS)
    continuity = section_body(parsed, SCENE_CONTINUITY_SECTIONS)
    first_chapter = chapter_number(chapter) == 1

    if previous:
        if first_chapter and is_opening_chapter_anchor(previous):
            pass
        elif is_none_body(previous):
            failures.append("上章章末锚点 must describe the previous chapter end state")
        else:
            failures.extend(
                check_required_anchor_fields(
                    previous,
                    ("time", "location", "present_characters", "protagonist_state", "carried_items", "unfinished_action"),
                    "上章章末锚点",
                )
            )

    if opening:
        failures.extend(
            check_required_anchor_fields(
                opening,
                ("time", "location", "present_characters", "protagonist_state", "first_action"),
                "本章开场落点",
            )
        )

    if continuity:
        kind = scene_continuity_type(continuity)
        note = scene_continuity_note(continuity)
        if not kind:
            failures.append("场景承接说明 missing field: 类型")
        elif kind not in SCENE_CONTINUITY_TYPES:
            failures.append(f"场景承接说明 has invalid 类型: {kind}")
        if not note:
            failures.append("场景承接说明 missing field: 说明")
        elif has_placeholder(note) or is_none_body(note) or not scene_continuity_note_is_concrete(note):
            failures.append("场景承接说明 must include a concrete transition explanation")

        previous_location = anchor_location(previous)
        opening_location = anchor_location(opening)
        if previous_location and opening_location and previous_location != opening_location:
            if kind == "原地承接":
                failures.append("场景承接说明 cannot use 原地承接 when location changes")
            if not scene_continuity_note_is_concrete(note):
                failures.append("location changes require concrete 场景承接说明")
    return failures


def check_progress_contract_sections(parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for aliases in PROGRESS_REQUIRED_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required section: {label}")
        elif has_placeholder(body):
            failures.append(f"section still has placeholder text: {label}")

    progress = section_body(parsed, PROGRESS_CONTRACT_SECTIONS)
    cost = section_body(parsed, COST_CONSEQUENCE_CONTRACT_SECTIONS)
    boundary = section_body(parsed, RESOLUTION_BOUNDARY_SECTIONS)
    if not progress or not cost or not boundary:
        return failures

    mainline_level, _ = parse_pacing_level(section_body(parsed, MAINLINE_TRACTION_SECTIONS), "S")
    external_level, _ = parse_pacing_level(section_body(parsed, EXTERNAL_PRESSURE_SECTIONS), "W")

    progress_mode = normalized_progress_mode(progress_value(progress, "progress_mode"))
    if not progress_mode:
        failures.append("本章进展契约 has invalid 进展类型")

    for key, label in (
        ("progress_target", "推进对象"),
        ("start_state_ref", "起始状态依据"),
        ("end_state_delta", "结束状态变化"),
    ):
        value = progress_value(progress, key)
        if not concrete_value(value):
            failures.append(f"本章进展契约 field must be concrete: {label}")

    minimum_event = progress_value(progress, "minimum_ledger_event").strip()
    if minimum_event not in LEDGER_EVENT_TYPES:
        failures.append("本章进展契约 最低落账事件 must be an existing event ledger type")

    importance = progress_value(progress, "progress_importance").strip()
    if importance not in PROGRESS_IMPORTANCE_LEVELS:
        failures.append("本章进展契约 进展重要度 must be P0-P3")

    impact_scale = normalized_impact_scale(progress_value(cost, "impact_scale"))
    if impact_scale not in IMPACT_SCALES:
        failures.append("本章代价与后果契约 推进重量 must be C0-C4 or I0-I4")

    consequence_level = normalized_consequence_level(progress_value(cost, "consequence_level"))
    if not consequence_level:
        failures.append("本章代价与后果契约 后果等级 must be reversible/scar/structure_change")

    paid_now = progress_value(cost, "cost_paid_now")
    deferred = progress_value(cost, "deferred_cost")
    obligation = progress_value(cost, "aftermath_obligation")
    if not any(concrete_value(value) for value in (paid_now, deferred, obligation)):
        failures.append("本章代价与后果契约 must include 已支付代价、延后代价 or 后果承接义务")

    low_pacing = mainline_level in LOW_S_LEVELS and external_level in LOW_W_LEVELS
    if low_pacing or impact_scale in LOW_IMPACT_SCALES:
        buffer_function = progress_value(progress, "buffer_function")
        if not concrete_value(buffer_function):
            failures.append("低牵引/低推进章必须填写具体 低牵引功能")
        if not concrete_value(progress_value(progress, "end_state_delta")):
            failures.append("低牵引/低推进章必须留下 结束状态变化")

    high_pacing = mainline_level in HIGH_S_LEVELS or external_level in HIGH_W_LEVELS or impact_scale in HIGH_IMPACT_SCALES
    if high_pacing:
        if not concrete_value(progress_value(cost, "cost_type"), min_chars=2):
            failures.append("高牵引/高推进章必须填写 代价类型")
        if not concrete_value(obligation):
            failures.append("高牵引/高推进章必须填写 后果承接义务")
        if digestion_window_chapters(progress_value(cost, "digestion_window")) is None:
            failures.append("高牵引/高推进章必须填写可解析的 消化窗口")
        if not concrete_value(progress_value(cost, "cooldown_scope")):
            failures.append("高牵引/高推进章必须填写 冷却范围")

    resolved_threads = progress_value(boundary, "resolved_threads")
    if not is_none_body(resolved_threads):
        if not is_yes(progress_value(boundary, "resolution_requires_cost")):
            failures.append("解决伏笔非空时，解决是否需要代价必须为 是")
        if not concrete_value(progress_value(cost, "cost_type"), min_chars=2):
            failures.append("解决伏笔非空时必须填写 代价类型")
        if not concrete_value(obligation):
            failures.append("解决伏笔非空时必须填写 后果承接义务")

    forbidden = progress_value(boundary, "forbidden_resolution")
    if not concrete_value(forbidden):
        failures.append("本章解决边界 field must be concrete: 禁止解决")

    return failures


def check_brief(path: Path) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"missing brief: {path.relative_to(ROOT)}"]
    text = read_text(path)
    parsed = markdown_sections(text)
    for name in REQUIRED_SECTIONS:
        if name not in parsed:
            failures.append(f"missing required section: {name}")
            continue
        body = parsed[name]
        if not body:
            failures.append(f"empty required section: {name}")
        elif any(marker in body for marker in PLACEHOLDER_MARKERS):
            failures.append(f"section still has placeholder text: {name}")
    for aliases in REQUIRED_ELEMENT_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required section: {label}")
        elif has_placeholder(body):
            failures.append(f"section still has placeholder text: {label}")
    failures.extend(check_pacing_sections(parsed))
    failures.extend(check_scene_continuity_sections(path.stem, parsed))
    failures.extend(check_progress_contract_sections(parsed))

    object_ids = declared_ids(section_body(parsed, USABLE_OBJECT_ID_SECTIONS))
    ability_ids = declared_ids(section_body(parsed, USABLE_ABILITY_ID_SECTIONS))
    known_objects = set(yaml_id_index(ROOT / "bible" / "objects.yaml", "objects"))
    known_abilities = set(yaml_id_index(ROOT / "bible" / "abilities.yaml", "abilities"))
    for item in object_ids:
        if item not in known_objects:
            failures.append(f"unknown object id in brief: {item}")
    for item in ability_ids:
        if item not in known_abilities:
            failures.append(f"unknown ability id in brief: {item}")
    if any(marker in text for marker in PLACEHOLDER_MARKERS):
        failures.append("brief still contains placeholder text")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a chapter brief for long-form anti-drift requirements.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    failures = check_brief(path)
    print(f"# Brief Check: {args.chapter}")
    print()
    if failures:
        print("status: NOT_READY")
        print()
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
