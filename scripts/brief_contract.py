from __future__ import annotations

import re

from element_context import NONE_MARKERS
from reader_personality_contracts import READER_BRIEF_REQUIRED_SECTIONS


PLACEHOLDER_MARKERS = ("待定", "待填", "待人类确认", "TODO", "寰呭畾", "寰呭～")

BASE_REQUIRED_SECTIONS = (
    "本章功能",
    "开篇吸引点",
    "主角目标",
    "主要阻力",
    "主角主动选择",
    "章末问题",
    "本章可用人物状态",
    "本章可用道具 / 装备",
    "本章可用技能 / 能力",
    "能力限制 / 代价",
    "未解决伏笔",
    "本章禁止新增",
    "本章禁止解决",
)

MAINLINE_TRACTION_SECTIONS = ("主线牵引档位", "Mainline Traction Level")
EXTERNAL_PRESSURE_SECTIONS = ("外部压力档位", "External Pressure Level")
INHERITED_CHANGE_SECTIONS = ("本章继承变化", "Inherited Change")
PACING_PURPOSE_SECTIONS = ("本章节奏用途", "Pacing Purpose")
PACING_NOTE_SECTIONS = ("节奏说明", "Pacing Note")
PREVIOUS_CHAPTER_ANCHOR_SECTIONS = ("上章章末锚点", "Previous Chapter End Anchor")
OPENING_SCENE_ANCHOR_SECTIONS = ("本章开场落点", "Opening Scene Anchor")
SCENE_CONTINUITY_SECTIONS = ("场景承接说明", "场景转移说明", "Scene Continuity Note")
PROGRESS_CONTRACT_SECTIONS = ("本章进展契约", "Progress Contract")
COST_CONSEQUENCE_CONTRACT_SECTIONS = ("本章代价与后果契约", "Cost And Consequence Contract")
RESOLUTION_BOUNDARY_SECTIONS = ("本章解决边界", "Resolution Boundary")

PACING_REQUIRED_SECTIONS = (
    MAINLINE_TRACTION_SECTIONS,
    EXTERNAL_PRESSURE_SECTIONS,
    INHERITED_CHANGE_SECTIONS,
    PACING_PURPOSE_SECTIONS,
    PACING_NOTE_SECTIONS,
)

PACING_FIELD_LABELS = tuple(aliases[0] for aliases in PACING_REQUIRED_SECTIONS)
CONTINUITY_REQUIRED_SECTIONS = (
    PREVIOUS_CHAPTER_ANCHOR_SECTIONS,
    OPENING_SCENE_ANCHOR_SECTIONS,
    SCENE_CONTINUITY_SECTIONS,
)
CONTINUITY_FIELD_LABELS = tuple(aliases[0] for aliases in CONTINUITY_REQUIRED_SECTIONS)
PROGRESS_REQUIRED_SECTIONS = (
    PROGRESS_CONTRACT_SECTIONS,
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
)
PROGRESS_FIELD_LABELS = tuple(aliases[0] for aliases in PROGRESS_REQUIRED_SECTIONS)

REQUIRED_BRIEF_FIELDS = (
    "本章功能",
    "开篇吸引点",
    "主角目标",
    "主要阻力",
    "主角主动选择",
    "上章章末锚点",
    "本章开场落点",
    "场景承接说明",
    "本章进展契约",
    "本章代价与后果契约",
    "本章解决边界",
    "主线牵引档位",
    "外部压力档位",
    "本章继承变化",
    "本章节奏用途",
    "节奏说明",
    "本章推进",
    "信息增量",
    "章末问题",
    "本章使用设定",
    "本章可用人物状态",
    "本章可用道具 / 装备",
    "本章可用道具 IDs",
    "本章可用技能 / 能力",
    "本章可用技能 IDs",
    "能力限制 / 代价",
    "未解决伏笔",
    "新增设定",
    "本章允许新增元素",
    "本章禁止临场解决",
    "伏笔：新开 / 推进 / 回收",
    "本章禁止新增",
    "本章禁止解决",
    "禁止新增 / 禁止解决 / 禁止模仿",
    *[aliases[0] for aliases in READER_BRIEF_REQUIRED_SECTIONS],
)

S_LEVELS = {f"S{index}" for index in range(5)}
W_LEVELS = {f"W{index}" for index in range(5)}

LOW_S_LEVELS = {"S0", "S1"}
LOW_W_LEVELS = {"W0", "W1"}
HIGH_S_LEVELS = {"S3", "S4"}
HIGH_W_LEVELS = {"W3", "W4"}
REST_NOTE_KEYWORDS = ("休整", "释压", "后果", "消化", "缓冲", "转场", "余韵", "关系")
LEDGER_EVENT_TYPES = {
    "character_decision",
    "character_state_change",
    "relationship_change",
    "world_fact",
    "rule_reveal",
    "thread_opened",
    "thread_advanced",
    "thread_paid_off",
    "location_change",
    "object_change",
    "chapter_anchor",
    "correction",
}
PROGRESS_MODE_ALIASES = {
    "setup": "setup",
    "铺垫": "setup",
    "reveal": "reveal",
    "揭示": "reveal",
    "decision": "decision",
    "选择": "decision",
    "thread_advance": "thread_advance",
    "线索推进": "thread_advance",
    "推进伏笔": "thread_advance",
    "payoff": "payoff",
    "兑现": "payoff",
    "digest": "digest",
    "消化": "digest",
    "cost_payment": "cost_payment",
    "付代价": "cost_payment",
    "transition": "transition",
    "转场": "transition",
}
PROGRESS_IMPORTANCE_LEVELS = {"P0", "P1", "P2", "P3"}
IMPACT_SCALES = {f"C{index}" for index in range(5)} | {f"I{index}" for index in range(5)}
HIGH_IMPACT_SCALES = {"C3", "C4", "I3", "I4"}
LOW_IMPACT_SCALES = {"C0", "C1", "I0", "I1"}
CONSEQUENCE_LEVEL_ALIASES = {
    "reversible": "reversible",
    "可逆": "reversible",
    "scar": "scar",
    "留疤": "scar",
    "structure_change": "structure_change",
    "结构改变": "structure_change",
    "结构性改变": "structure_change",
}
CONCRETE_YES_VALUES = {"是", "yes", "true", "需要", "Y", "y"}
ANCHOR_NONE_MARKERS = NONE_MARKERS | {"开篇章，无上章", "首章无上章", "开篇章：无上章", "首章：无上章"}
ANCHOR_KEY_ALIASES = {
    "time": ("时间", "章末时间", "开场时间", "end_time", "opening_time"),
    "location": ("地点", "章末地点", "开场地点", "end_location", "opening_location"),
    "present_characters": ("在场人物", "present_characters"),
    "protagonist_state": ("主角状态", "physical_state", "emotional_state", "protagonist_state"),
    "carried_items": ("携带物 / 证据", "携带物/证据", "携带物", "证据", "carried_items"),
    "unfinished_action": ("未完成动作", "open_action", "unfinished_action"),
    "first_action": ("第一动作", "first_action"),
    "type": ("类型", "承接类型", "转移类型", "type"),
    "note": ("说明", "承接说明", "转移说明", "note"),
}
PROGRESS_KEY_ALIASES = {
    "progress_mode": ("进展类型", "progress_mode"),
    "progress_target": ("推进对象", "progress_target"),
    "start_state_ref": ("起始状态依据", "start_state_ref"),
    "end_state_delta": ("结束状态变化", "end_state_delta"),
    "minimum_ledger_event": ("最低落账事件", "minimum_ledger_event"),
    "progress_importance": ("进展重要度", "progress_importance"),
    "buffer_function": ("低牵引功能", "buffer_function"),
    "impact_scale": ("推进重量", "impact_scale"),
    "consequence_level": ("后果等级", "consequence_level"),
    "cost_type": ("代价类型", "cost_type"),
    "cost_paid_now": ("已支付代价", "cost_paid_now"),
    "deferred_cost": ("延后代价", "deferred_cost"),
    "aftermath_obligation": ("后果承接义务", "aftermath_obligation"),
    "digestion_window": ("消化窗口", "digestion_window"),
    "cooldown_scope": ("冷却范围", "cooldown_scope"),
    "opened_threads": ("新开伏笔", "opened_threads"),
    "advanced_threads": ("推进伏笔", "advanced_threads"),
    "resolved_threads": ("解决伏笔", "resolved_threads"),
    "forbidden_resolution": ("禁止解决", "forbidden_resolution"),
    "resolution_requires_cost": ("解决是否需要代价", "resolution_requires_cost"),
}
SCENE_CONTINUITY_TYPES = {"原地承接", "明示跳切", "省略过桥", "开篇起始"}
GENERIC_SCENE_CONTINUITY_NOTES = {
    "承接上文",
    "自然过渡",
    "换个地方",
    "场景转移",
    "场景承接",
    "具体说明",
    "正常承接",
    "顺接",
}

GENERIC_EXPLANATIONS = {"推动剧情", "推进剧情", "承接上文", "节奏说明", "具体说明"}
GENERIC_PROGRESS_VALUES = {
    "推进剧情",
    "推动剧情",
    "有所推进",
    "小幅推进",
    "具体变化",
    "留下悬念",
    "继续调查",
    "自然发展",
}


def has_placeholder(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def is_none_body(text: str) -> bool:
    value = text.strip().strip("。；;,.，")
    return not value or value.lower() in NONE_MARKERS or value in NONE_MARKERS


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def normalized_field_name(text: str) -> str:
    return compact_text(text).strip("`*#-：:")


def extract_labeled_value(body: str, aliases: tuple[str, ...]) -> str:
    normalized_aliases = {normalized_field_name(alias) for alias in aliases}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        line = re.sub(r"^\d+[.)]\s+", "", line).strip()
        if "：" in line:
            key, value = line.split("：", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        if normalized_field_name(key) in normalized_aliases:
            return value.strip()
    return ""


def anchor_value(body: str, key: str) -> str:
    return extract_labeled_value(body, ANCHOR_KEY_ALIASES[key])


def progress_value(body: str, key: str) -> str:
    return extract_labeled_value(body, PROGRESS_KEY_ALIASES[key])


def anchor_location(body: str) -> str:
    return anchor_value(body, "location")


def is_opening_chapter_anchor(body: str) -> bool:
    compact = compact_text(body)
    return any(compact_text(marker) in compact for marker in ANCHOR_NONE_MARKERS) or (
        "开篇章" in compact and "无上章" in compact
    ) or ("首章" in compact and "无上章" in compact)


def scene_continuity_type(body: str) -> str:
    value = anchor_value(body, "type").strip("。；;,.，")
    return value


def scene_continuity_note(body: str) -> str:
    return anchor_value(body, "note")


def scene_continuity_note_is_concrete(note: str) -> bool:
    compact = compact_text(note)
    if len(compact) < 8:
        return False
    return compact not in {compact_text(item) for item in GENERIC_SCENE_CONTINUITY_NOTES}


def concrete_value(value: str, min_chars: int = 4) -> bool:
    compact = compact_text(value)
    if len(compact) < min_chars:
        return False
    if has_placeholder(value) or is_none_body(value):
        return False
    return compact not in {compact_text(item) for item in GENERIC_PROGRESS_VALUES}


def normalized_progress_mode(value: str) -> str:
    normalized = value.strip().strip("`*。；;,.，")
    return PROGRESS_MODE_ALIASES.get(normalized, "")


def normalized_consequence_level(value: str) -> str:
    normalized = value.strip().strip("`*。；;,.，")
    return CONSEQUENCE_LEVEL_ALIASES.get(normalized, "")


def normalized_impact_scale(value: str) -> str:
    value = value.strip().strip("`*。；;,.，").upper()
    if value.startswith("I") and value[1:].isdigit():
        return f"I{value[1:]}"
    if value.startswith("C") and value[1:].isdigit():
        return f"C{value[1:]}"
    return ""


def is_concrete_list(value: str) -> bool:
    return concrete_value(value, min_chars=2)


def is_yes(value: str) -> bool:
    normalized = value.strip().strip("`*。；;,.，")
    return normalized in CONCRETE_YES_VALUES


def digestion_window_chapters(value: str) -> int | None:
    text = compact_text(value)
    if not text or is_none_body(value):
        return None
    if "本章" in text:
        return 0
    if "下一章" in text or "下章" in text:
        return 1
    digit = re.search(r"(\d+)", text)
    if digit:
        return int(digit.group(1))
    chinese = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5}
    for marker, count in chinese.items():
        if marker in text:
            return count
    return None


def parse_pacing_level(body: str, prefix: str) -> tuple[str | None, str]:
    match = re.match(rf"^\s*`?({prefix}[0-4])`?\s*(.*)$", body.strip(), flags=re.S)
    if not match:
        return None, ""
    level = match.group(1)
    explanation = match.group(2).strip(" \t\r\n:：-—,，.。")
    return level, explanation


def level_explanation_is_concrete(explanation: str) -> bool:
    compact = compact_text(explanation)
    if len(compact) < 6:
        return False
    return not any(item == compact for item in GENERIC_EXPLANATIONS)
