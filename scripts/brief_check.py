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
    brief_schema_version,
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
    EFFECTIVE_PROGRESS_TYPES,
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
    READER_REWARD_INTENSITIES,
    READER_REWARD_TIMINGS,
    RESOLUTION_BOUNDARY_SECTIONS,
    SCENE_CONTINUITY_SECTIONS,
    SCENE_CONTINUITY_TYPES,
    anchor_location,
    anchor_value,
    concrete_value,
    digestion_window_chapters,
    extract_labeled_value,
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
from reader_personality_contracts import READER_BRIEF_REQUIRED_LABELS, READER_BRIEF_REQUIRED_SECTIONS, metadata_value


REQUIRED_SECTIONS = BASE_REQUIRED_SECTIONS
REQUIRED_ELEMENT_SECTIONS = (
    USABLE_OBJECT_ID_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
)
TITLE_SECTIONS = ("章节标题", "Chapter Title")
INTRO_SECTIONS = ("章节简介", "Chapter Intro")
STRUCTURE_HINT_SECTIONS = ("本章结构提示", "Structure Hint")
END_STATE_CHANGE_SECTIONS = ("章末状态变化", "End State Change")
END_STATE_CHANGE_TYPES = {"关系改变", "代价落地", "认知更新", "选择完成", "风险显形", "旧问题变形", "新线索出现", "后果承接"}
READER_RETENTION_SECTIONS = ("本章留存合同", "Reader Retention Contract")
PLACEHOLDER_TITLES = {"标题", "章节标题", "chapter title", "todo", "tbd", "待定", "待填", "无题"}
V2_STORY_CARD_SECTIONS = ("Story Card",)
V2_MACHINE_APPENDIX_SECTIONS = ("Machine Contract Appendix",)
V2_STORY_FIELDS = (
    "第一屏扰动",
    "主角本章想要",
    "主角主动动作",
    "最大阻力",
    "中段变化点",
    "本章小兑现",
    "before -> after",
    "章末点击理由",
    "本章只讲懂的一条世界规则",
    "禁止临场破局",
)
V2_MACHINE_FIELDS = (
    "上章章末锚点",
    "本章开场落点",
    "场景承接说明",
    "主线牵引档位",
    "外部压力档位",
    "本章继承变化",
    "本章节奏用途",
    "节奏说明",
    "本章进展契约",
    "本章代价与后果契约",
    "本章解决边界",
    "reader_reward_intensity",
    "reader_reward_type",
    "reader_reward_delivery",
    "reader_reward_timing",
    "reward_evidence_requirement",
    "pressure_level",
    "release_valve",
    "protagonist_desire_or_principle",
    "低戏剧载体",
    "低戏剧载体承载的推进类型",
    "核心机制是否出现",
    "若未出现，当前沉默计数",
    "等待结尾债务",
    "可用人物状态",
    "可用道具 / 装备",
    "可用道具 IDs",
    "可用技能 / 能力",
    "可用技能 IDs",
    "能力限制 / 代价",
    "未解决伏笔",
    "新增设定",
    "允许新增元素",
    "最低落账事件",
    "禁止新增",
    "禁止解决",
    "主角弱点 / 误判",
    "普通人 / 外部视角对照",
    "旧问题",
    "悬念状态",
)
V2_MACHINE_ALLOW_NONE = {
    "低戏剧载体",
    "低戏剧载体承载的推进类型",
    "等待结尾债务",
    "可用道具 / 装备",
    "可用道具 IDs",
    "可用技能 / 能力",
    "可用技能 IDs",
    "未解决伏笔",
    "新增设定",
    "允许新增元素",
    "旧问题",
}


def title_is_ready(title: str) -> bool:
    value = title.strip().strip("#").strip()
    if not value:
        return False
    if value.lower() in PLACEHOLDER_TITLES or value in PLACEHOLDER_TITLES:
        return False
    return not has_placeholder(value)


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


def check_reader_contract_sections(parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for aliases in READER_BRIEF_REQUIRED_SECTIONS:
        label = aliases[0]
        if missing_section(parsed, aliases):
            failures.append(f"missing required reader contract section: {label}")
            continue
        body = section_body(parsed, aliases)
        if not body:
            failures.append(f"empty required reader contract section: {label}")
        elif has_placeholder(body):
            failures.append(f"reader contract section still has placeholder text: {label}")
        for field in READER_BRIEF_REQUIRED_LABELS.get(label, ()):
            value = metadata_value(body, field)
            if not value:
                failures.append(f"reader contract section {label} missing field: {field}")
            elif has_placeholder(value):
                failures.append(f"reader contract section {label} field is not ready: {field}")
    return failures


def check_v2_story_and_machine_sections(parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    story = section_body(parsed, V2_STORY_CARD_SECTIONS)
    machine = section_body(parsed, V2_MACHINE_APPENDIX_SECTIONS)
    if not story:
        failures.append("missing required section: Story Card")
    if not machine:
        failures.append("missing required section: Machine Contract Appendix")
    for field in V2_STORY_FIELDS:
        value = labeled_value(story, field)
        if not value:
            failures.append(f"Story Card missing field: {field}")
        elif has_placeholder(value) or is_none_body(value):
            failures.append(f"Story Card field is not ready: {field}")
    for field in V2_MACHINE_FIELDS:
        value = labeled_value(machine, field)
        if not value:
            failures.append(f"Machine Contract Appendix missing field: {field}")
        elif has_placeholder(value) or (field not in V2_MACHINE_ALLOW_NONE and is_none_body(value)):
            failures.append(f"Machine Contract Appendix field is not ready: {field}")
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

    effective_type = progress_value(progress, "effective_progress_type").strip()
    if effective_type not in EFFECTIVE_PROGRESS_TYPES:
        failures.append("本章进展契约 有效推进类型 must be a valid effective progress type")
    if "->" not in progress_value(progress, "effective_progress_unit") and "→" not in progress_value(progress, "effective_progress_unit"):
        failures.append("本章进展契约 有效推进单位 must use before -> after")
    if not concrete_value(progress_value(progress, "effective_progress_evidence_target")):
        failures.append("本章进展契约 field must be concrete: 有效推进证据目标")

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

    retention = section_body(parsed, READER_RETENTION_SECTIONS)
    machine = section_body(parsed, V2_MACHINE_APPENDIX_SECTIONS)
    intensity = progress_value(retention, "reader_reward_intensity").strip().upper()
    if intensity not in READER_REWARD_INTENSITIES:
        failures.append("本章留存合同 reader_reward_intensity must be R0-R4")
    if not concrete_value(progress_value(retention, "reader_reward_type"), min_chars=1):
        failures.append("本章留存合同 field must be concrete: reader_reward_type")
    if not concrete_value(progress_value(retention, "reader_reward_delivery")):
        failures.append("本章留存合同 field must be concrete: reader_reward_delivery")
    timing = progress_value(retention, "reader_reward_timing").strip()
    if timing not in READER_REWARD_TIMINGS:
        failures.append("本章留存合同 reader_reward_timing must be opening/midpoint/ending/full_chapter/next_chapter_setup")
    evidence_requirement = progress_value(retention, "reward_evidence_requirement")
    if intensity in {"R2", "R3", "R4"} and not concrete_value(evidence_requirement):
        failures.append("R2+ 本章留存合同 reward_evidence_requirement must be concrete")
    if intensity == "R4":
        if not concrete_value(progress_value(cost, "cost_paid_now")):
            failures.append("R4 本章代价与后果契约必须填写 已支付代价")
        if not concrete_value(obligation):
            failures.append("R4 本章代价与后果契约必须填写 后果承接义务")
    pressure = progress_value(retention, "pressure_level") or progress_value(machine, "pressure_level") or progress_value(cost, "pressure_level")
    release = progress_value(retention, "release_valve") or progress_value(machine, "release_valve")
    if not concrete_value(pressure, min_chars=1):
        failures.append("本章留存合同 pressure_level must be concrete")
    if any(marker in pressure for marker in ("H3", "H4", "W3", "W4", "高压", "强压", "爆发")) and not concrete_value(release):
        failures.append("高压章节必须填写 release_valve")
    protagonist_desire = progress_value(retention, "protagonist_desire_or_principle") or progress_value(machine, "protagonist_desire_or_principle")
    if not concrete_value(protagonist_desire):
        failures.append("本章留存合同 protagonist_desire_or_principle must be concrete")

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
    schema_version = brief_schema_version(text)
    parsed = markdown_sections(text)
    title = section_body(parsed, TITLE_SECTIONS).strip()
    if missing_section(parsed, TITLE_SECTIONS):
        failures.append("missing required section: 章节标题")
    elif not title_is_ready(title):
        failures.append("章节标题 must be non-placeholder")
    if schema_version == 2:
        failures.extend(check_v2_story_and_machine_sections(parsed))
    else:
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
    if schema_version != 2:
        failures.extend(check_reader_contract_sections(parsed))

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
    failures.extend(check_catalog_sections(parsed))
    return failures


def labeled_value(body: str, key: str) -> str:
    return extract_labeled_value(body, (key,))


def check_catalog_sections(parsed: dict[str, str]) -> list[str]:
    failures: list[str] = []
    intro = section_body(parsed, INTRO_SECTIONS)
    if intro and has_placeholder(intro):
        failures.append("章节简介 must not contain TODO or placeholder text")
    end_state = section_body(parsed, END_STATE_CHANGE_SECTIONS)
    if end_state and has_placeholder(end_state):
        failures.append("章末状态变化 must not contain TODO or placeholder text")
    return failures


def brief_warnings(path: Path) -> list[str]:
    if not path.exists():
        return []
    parsed = markdown_sections(read_text(path))
    warnings: list[str] = []
    title = section_body(parsed, TITLE_SECTIONS).strip()
    intro = section_body(parsed, INTRO_SECTIONS).strip()
    end_state = section_body(parsed, END_STATE_CHANGE_SECTIONS).strip()
    if not title:
        warnings.append("章节标题 is missing or empty")
    compact_intro_len = len("".join(intro.split()))
    if not intro:
        warnings.append("章节简介 is missing or empty")
    elif compact_intro_len < 80 or compact_intro_len > 180:
        warnings.append("章节简介 should be 80-180 non-space characters")
    if missing_section(parsed, STRUCTURE_HINT_SECTIONS):
        warnings.append("本章结构提示 is missing")
    if not end_state:
        warnings.append("章末状态变化 is missing")
    else:
        change_type = labeled_value(end_state, "type")
        if change_type and change_type not in END_STATE_CHANGE_TYPES:
            warnings.append(f"章末状态变化 type is advisory but unknown: {change_type}")
    return warnings


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
    warnings = brief_warnings(path)
    print(f"# Brief Check: {args.chapter}")
    print()
    if failures:
        print("status: NOT_READY")
        print()
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("status: READY")
    if warnings:
        print()
        print("## Warnings")
        print()
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
