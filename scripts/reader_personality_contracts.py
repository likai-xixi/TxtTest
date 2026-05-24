from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, read_text, write_json, write_text

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


PLACEHOLDER_MARKERS = ("待定", "待填", "待评", "待生成", "待人类裁决", "TODO", "TBD", "placeholder")

INITIAL_PERSONALITY_REQUIRED_FIELDS = (
    "essence",
    "opening_mask",
    "true_inner_state",
    "visible_traits",
    "hidden_traits",
    "default_strategy",
    "stress_response",
    "emotional_leak",
    "speech_profile",
    "relationship_modes",
    "opening_flaw",
    "opening_misbelief",
    "opening_desire",
    "opening_fear",
    "first_three_chapter_limits",
    "change_seeds",
)

INITIAL_PERSONALITY_LIST_FIELDS = (
    "visible_traits",
    "hidden_traits",
    "first_three_chapter_limits",
    "change_seeds",
)
INITIAL_PERSONALITY_OBJECT_FIELDS = ("speech_profile", "relationship_modes")

READER_PROMISE_JSON = ROOT / "state" / "project_reader_promise.json"
READER_PROMISE_MD = ROOT / "state" / "project_reader_promise.md"
READER_PROMISE_TEMPLATE = ROOT / "templates" / "reader_promise.md"

READER_PROMISE_REQUIRED_FIELDS = (
    "primary_genre",
    "secondary_genre",
    "target_reader",
    "platform_expectation",
    "genre_profile",
    "core_hook",
    "core_sell_point",
    "core_mechanism_name",
    "allowed_low_drama_carriers",
    "main_reader_rewards",
    "non_promises",
    "first_chapter_must_deliver",
    "second_chapter_must_escalate",
    "third_chapter_must_hook",
    "three_chapter_main_question",
    "three_chapter_protagonist_specialness",
    "per_chapter_must_have",
    "per_chapter_must_not_only_have",
    "ending_hook_priority",
    "reward_mix",
    "positive_promises",
    "negative_failure_modes",
    "release_valve_policy",
    "protagonist_agency_policy",
    "information_clarity_policy",
    "language_experience_policy",
    "structural_efficiency_policy",
    "reader_reward_intensity_policy",
    "genre_mismatch_red_lines",
)

READER_BRIEF_REQUIRED_SECTIONS = (
    ("本章留存合同", "Reader Retention Contract"),
    ("本章主角魅力合同", "Protagonist Charm Contract"),
    ("本章初始人格挑战合同", "Initial Personality Challenge Contract"),
    ("本章世界观展示合同", "World Reveal Contract"),
    ("本章名词预算", "Concept Budget"),
    ("本章悬念推进合同", "Suspense Progression Contract"),
    ("本章语言记忆点", "Language Memorability Contract"),
    ("本章防 AI 味合同", "Anti AI Taste Contract"),
    ("本章情绪越界合同", "Emotional Risk Contract"),
    ("本章角色私心与使坏合同", "Gray Motive Contract"),
    ("本章对白功能合同", "Dialogue Function Contract"),
    ("本章句式破整合同", "Sentence Rhythm Break Contract"),
    ("本章细节经济合同", "Detail Economy Contract"),
)
READER_BRIEF_REQUIRED_LABELS = {
    "本章留存合同": (
        "第一屏钩子",
        "本章核心问题",
        "本章读者期待",
        "reader_reward_intensity",
        "reader_reward_type",
        "reader_reward_delivery",
        "reader_reward_timing",
        "reward_evidence_requirement",
        "低戏剧载体",
        "低戏剧载体承载的推进类型",
        "核心机制是否出现",
        "若未出现，当前沉默计数",
        "等待结尾债务",
        "本章中段反转 / 加压",
        "本章小兑现",
        "本章章末钩子",
        "下一章点击理由",
    ),
    "本章主角魅力合同": (
        "主角本章主动目标",
        "主角本章过人之处",
        "主角本章弱点 / 误判 / 上头点",
        "金手指 / 特殊资源本章表现",
        "能力、地位、认知或关系的刻度变化",
        "本章让读者喜欢主角的瞬间",
    ),
    "本章初始人格挑战合同": (
        "是否挑战初始人格",
        "被挑战字段",
        "挑战方式",
        "本章是否形成人格变化",
        "若 durable，最低落账事件",
        "前三章限制确认",
    ),
    "本章世界观展示合同": (
        "本章允许新增核心名词",
        "本章允许新增次要名词",
        "必须通过场景展示的设定",
        "禁止集中说明的设定",
        "普通人 / 外部视角对照",
        "读者本章必须理解的一条规则",
    ),
    "本章名词预算": (
        "新核心名词上限",
        "新次要名词上限",
        "必须复用的旧名词",
        "本章不解释、只露面的名词",
        "本章必须让读者看懂的规则",
    ),
    "本章悬念推进合同": (
        "旧问题",
        "本章给出的新线索",
        "本章打碎的错误希望",
        "本章部分解答",
        "本章新问题",
        "悬念状态",
    ),
    "本章语言记忆点": (
        "本章金句",
        "本章梗 / 反差笑点",
        "角色口头禅或标志动作",
        "可截图传播的句子",
        "禁止使用的平铺语气",
    ),
    "本章防 AI 味合同": (
        "场景压力",
        "具体细节锚点",
        "解释预算",
        "禁止总结腔",
        "必须用场景证明的判断",
        "允许读者暂时误解的点",
    ),
    "本章情绪越界合同": (
        "不体面的真实冲动",
        "对外表现与内在冲动的错位",
        "本章允许出现的负面情绪",
        "不允许被旁白洗白的位置",
    ),
    "本章角色私心与使坏合同": (
        "谁有私心",
        "私心目标",
        "使用手段",
        "伤害或牺牲了谁",
        "本章即时后果",
        "后续追讨窗口",
    ),
    "本章对白功能合同": (
        "关键对白场景",
        "角色目标冲突",
        "对话信息增量",
        "潜台词 / 权力变化",
        "哪一句不能像作者总结",
        "对话后果",
    ),
    "本章句式破整合同": (
        "叙述节奏",
        "禁止连续使用的句式",
        "必须保留的毛边",
        "禁止排比总结的位置",
    ),
    "本章细节经济合同": (
        "必写细节及功能",
        "删除型细节",
        "细节密度上限",
        "细节必须回收或转化的位置",
    ),
}

OPENING_RETENTION_REVIEW = "opening_retention.md"
READER_EXPERIENCE_REVIEWS = (
    "personality_drift.md",
    "hook_retention.md",
    "protagonist_charm.md",
    "world_reveal.md",
    "suspense_ladder.md",
    "language_memorability.md",
    "genre_fit.md",
)
ALL_READER_REVIEWS = (OPENING_RETENTION_REVIEW, *READER_EXPERIENCE_REVIEWS)
ALLOWED_REVIEW_STATUSES = {"CLEAR", "BLOCKED", "ACCEPTED_BY_HUMAN"}

PERSONALITY_DELTA_FIELDS = {
    "opening_misbelief",
    "default_strategy",
    "stress_response",
    "relationship_modes",
    "visible_traits",
    "hidden_traits",
    "change_seeds",
    "other",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path, role: str) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "role": role, "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def has_placeholder(value: object) -> bool:
    if isinstance(value, list):
        return not value or any(has_placeholder(item) for item in value)
    if isinstance(value, dict):
        return not value or any(has_placeholder(item) for item in value.values())
    text = str(value or "").strip()
    return not text or any(marker.lower() in text.lower() for marker in PLACEHOLDER_MARKERS)


def validate_initial_personality(value: object, *, prefix: str = "initial_personality") -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{prefix} must be an object"]
    for field in INITIAL_PERSONALITY_REQUIRED_FIELDS:
        if field not in value:
            errors.append(f"{prefix}.{field} is missing")
            continue
        field_value = value.get(field)
        if field in INITIAL_PERSONALITY_LIST_FIELDS:
            if not isinstance(field_value, list) or not field_value:
                errors.append(f"{prefix}.{field} must be a non-empty list")
            elif any(has_placeholder(item) for item in field_value):
                errors.append(f"{prefix}.{field} has placeholder or empty items")
        elif field in INITIAL_PERSONALITY_OBJECT_FIELDS:
            if not isinstance(field_value, dict) or not field_value:
                errors.append(f"{prefix}.{field} must be a non-empty object")
            elif has_placeholder(field_value):
                errors.append(f"{prefix}.{field} has placeholder text")
        elif has_placeholder(field_value):
            errors.append(f"{prefix}.{field} is empty or has placeholder text")
    return errors


def default_initial_personality() -> dict[str, Any]:
    return {
        "essence": "待定：用一句话说明主角人格本质。",
        "opening_mask": "待定：主角开局给外界看的样子。",
        "true_inner_state": "待定：主角真实内在状态。",
        "visible_traits": ["待定：外显性格 1", "待定：外显性格 2"],
        "hidden_traits": ["待定：被压住的欲望", "待定：不愿承认的恐惧"],
        "default_strategy": "待定：遇事第一反应。",
        "stress_response": "待定：压力下会怎么变形。",
        "emotional_leak": "待定：情绪藏不住时会露在哪里。",
        "speech_profile": {
            "rhythm": "待定：说话节奏。",
            "sharpness": "待定：毒舌 / 克制 / 绕弯 / 直给。",
            "favorite_words": ["待定：常用词"],
            "forbidden_tone": ["待定：不该突然出现的语气"],
        },
        "relationship_modes": {
            "stranger": "待定：面对陌生人。",
            "ally": "待定：面对同伴。",
            "authority": "待定：面对强者或上级。",
            "intimate": "待定：面对亲密关系。",
        },
        "opening_flaw": "待定：开局缺陷。",
        "opening_misbelief": "待定：开局错误认知。",
        "opening_desire": "待定：开局最想要什么。",
        "opening_fear": "待定：开局最怕什么。",
        "first_three_chapter_limits": [
            "前三章不能突然完成核心成长。",
            "前三章不能无事件推翻初始误信。",
        ],
        "change_seeds": ["待定：后续可能被事件撬动的性格点。"],
    }


def selected_freeze_path() -> Path | None:
    selected = ROOT / "state" / "idea_lab" / "selected.json"
    if not selected.exists():
        return None
    data = read_json(selected, {})
    idea_id = data.get("idea_id")
    if not idea_id:
        return None
    return ROOT / "state" / "idea_lab" / str(idea_id) / "core_setting_freeze.json"


def initial_personality_from_freeze() -> tuple[dict[str, Any], Path | None]:
    path = selected_freeze_path()
    if path is None or not path.exists():
        return {}, path
    data = read_json(path, {})
    fields = data.get("fields") if isinstance(data, dict) else {}
    value = fields.get("initial_personality") if isinstance(fields, dict) else {}
    return value if isinstance(value, dict) else {}, path


def load_characters() -> list[dict[str, Any]]:
    path = ROOT / "bible" / "characters.yaml"
    if not path.exists() or yaml is None:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    items = data.get("characters", [])
    return [item for item in items if isinstance(item, dict)]


def known_character_ids() -> set[str]:
    return {str(item.get("id")) for item in load_characters() if str(item.get("id", "")).strip()}


def protagonist_initial_personality() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    refs: list[dict[str, Any]] = []
    freeze_personality, freeze_path = initial_personality_from_freeze()
    if freeze_path is not None:
        refs.append(file_ref(freeze_path, "core_setting_freeze"))
    if freeze_personality:
        return freeze_personality, refs
    characters_path = ROOT / "bible" / "characters.yaml"
    refs.append(file_ref(characters_path, "characters_yaml"))
    for item in load_characters():
        if item.get("id") == "protagonist" and isinstance(item.get("initial_personality"), dict):
            return item["initial_personality"], refs
    return {}, refs


def default_reader_promise() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "DRAFT",
        "updated_at": now_iso(),
        "primary_genre": "待定",
        "secondary_genre": "待定",
        "target_reader": "待定",
        "platform_expectation": "商业连载发布，需声明目标平台、追读目标、付费转化节奏和平台合规边界",
        "genre_profile": "待定",
        "core_hook": "待定",
        "core_sell_point": "待定",
        "core_mechanism_name": "待定",
        "allowed_low_drama_carriers": ["待定"],
        "main_reader_rewards": ["待定"],
        "non_promises": ["待定"],
        "first_chapter_must_deliver": "待定",
        "second_chapter_must_escalate": "待定",
        "third_chapter_must_hook": "待定",
        "three_chapter_main_question": "待定",
        "three_chapter_protagonist_specialness": "待定",
        "per_chapter_must_have": ["待定"],
        "per_chapter_must_not_only_have": ["待定"],
        "ending_hook_priority": ["待定"],
        "reward_mix": {
            "爽点": "待定",
            "悬念": "待定",
            "笑点": "待定",
            "情绪点": "待定",
        },
        "positive_promises": [
            "待定：读者每章至少应获得的可感回报。",
            "待定：读者三章内必须确认的追读理由。",
        ],
        "negative_failure_modes": {
            "red_lines": [
                "待定：不得连续压抑无释放。",
                "待定：不得连续只开悬念不推进或兑现。",
                "待定：不得让主角只承担工具功能。",
                "待定：不得用设定解释替代戏剧冲突。",
            ],
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
            "minimum_release_types": ["小胜", "真相兑现", "关系推进", "情绪缓冲", "反制"],
            "per_three_chapters_must_include_release": True,
            "rationale": "待定：说明本书如何避免长期压抑无释放。",
        },
        "protagonist_agency_policy": {
            "requires_active_goal": True,
            "requires_active_action": True,
            "requires_cost_or_consequence": True,
            "requires_state_change": True,
            "requires_desire_or_principle": True,
            "rationale": "待定：说明主角如何持续改变局面，而不是被流程推着走。",
        },
        "information_clarity_policy": {
            "max_consecutive_setup_only_chapters": 2,
            "require_scene_test_for_world_rule": True,
            "forbid_explanation_only_worldbuilding": True,
            "rationale": "待定：说明世界观如何通过场景让读者看懂。",
        },
        "language_experience_policy": {
            "forbid_summary_voice": True,
            "require_memorable_line_or_detail": True,
            "max_explanation_paragraphs_without_scene": 2,
            "rationale": "待定：说明如何避免公文腔和作者总结腔。",
        },
        "structural_efficiency_policy": {
            "min_effective_progress_per_chapter": "before -> after",
            "max_words_without_state_change": 6000,
            "max_low_progress_window_count": 2,
            "window_chapters": 5,
            "rationale": "待定：说明如何防止大字数低推进。",
        },
        "reader_reward_intensity_policy": {
            "opening_chapter_count": 0,
            "opening_intensity_by_chapter": {},
            "default_chapter_intensity": "待定",
            "allowed_chapter_overrides": {},
            "rationale": "待定",
        },
        "genre_mismatch_red_lines": ["待定"],
        "source_boundary": "instruction_only_not_fact_source",
}


def _validate_required_object(value: object, name: str, required: tuple[str, ...], *, require_ready: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"reader promise {name} must be an object"]
    for field in required:
        if field not in value:
            errors.append(f"reader promise {name} missing field: {field}")
            continue
        if require_ready and has_placeholder(value.get(field)):
            errors.append(f"reader promise {name}.{field} is empty or placeholder")
    return errors


def _require_bool(value: dict[str, Any], name: str, field: str, errors: list[str]) -> None:
    if not isinstance(value.get(field), bool):
        errors.append(f"reader promise {name}.{field} must be boolean")


def _require_non_negative_int(value: dict[str, Any], name: str, field: str, errors: list[str]) -> None:
    raw = value.get(field)
    if not isinstance(raw, int) or raw < 0:
        errors.append(f"reader promise {name}.{field} must be a non-negative integer")


def validate_reader_experience_policies(data: dict[str, Any], *, require_ready: bool) -> list[str]:
    errors: list[str] = []
    if has_placeholder(data.get("positive_promises")) and require_ready:
        errors.append("reader promise positive_promises must be concrete")

    negative = data.get("negative_failure_modes")
    errors.extend(
        _validate_required_object(
            negative,
            "negative_failure_modes",
            (
                "red_lines",
                "no_release_max_run",
                "no_payoff_max_run",
                "open_without_payoff_max_run",
                "passive_protagonist_max_run",
                "explanation_only_max_run",
                "repeated_shape_max_run",
                "low_efficiency_window_chapters",
                "low_efficiency_max_count",
            ),
            require_ready=False,
        )
    )
    if isinstance(negative, dict):
        if require_ready and has_placeholder(negative.get("red_lines")):
            errors.append("reader promise negative_failure_modes.red_lines must be concrete")
        for field in (
            "no_release_max_run",
            "no_payoff_max_run",
            "open_without_payoff_max_run",
            "passive_protagonist_max_run",
            "explanation_only_max_run",
            "repeated_shape_max_run",
            "low_efficiency_window_chapters",
            "low_efficiency_max_count",
        ):
            _require_non_negative_int(negative, "negative_failure_modes", field, errors)

    release = data.get("release_valve_policy")
    errors.extend(
        _validate_required_object(
            release,
            "release_valve_policy",
            ("max_high_pressure_without_release", "minimum_release_types", "per_three_chapters_must_include_release", "rationale"),
            require_ready=False,
        )
    )
    if isinstance(release, dict):
        _require_non_negative_int(release, "release_valve_policy", "max_high_pressure_without_release", errors)
        _require_bool(release, "release_valve_policy", "per_three_chapters_must_include_release", errors)
        if require_ready and has_placeholder(release.get("minimum_release_types")):
            errors.append("reader promise release_valve_policy.minimum_release_types must be concrete")
        if require_ready and has_placeholder(release.get("rationale")):
            errors.append("reader promise release_valve_policy.rationale must be concrete")

    agency = data.get("protagonist_agency_policy")
    agency_fields = (
        "requires_active_goal",
        "requires_active_action",
        "requires_cost_or_consequence",
        "requires_state_change",
        "requires_desire_or_principle",
        "rationale",
    )
    errors.extend(_validate_required_object(agency, "protagonist_agency_policy", agency_fields, require_ready=False))
    if isinstance(agency, dict):
        for field in agency_fields[:-1]:
            _require_bool(agency, "protagonist_agency_policy", field, errors)
        if require_ready and has_placeholder(agency.get("rationale")):
            errors.append("reader promise protagonist_agency_policy.rationale must be concrete")

    clarity = data.get("information_clarity_policy")
    clarity_fields = (
        "max_consecutive_setup_only_chapters",
        "require_scene_test_for_world_rule",
        "forbid_explanation_only_worldbuilding",
        "rationale",
    )
    errors.extend(_validate_required_object(clarity, "information_clarity_policy", clarity_fields, require_ready=False))
    if isinstance(clarity, dict):
        _require_non_negative_int(clarity, "information_clarity_policy", "max_consecutive_setup_only_chapters", errors)
        for field in clarity_fields[1:3]:
            _require_bool(clarity, "information_clarity_policy", field, errors)
        if require_ready and has_placeholder(clarity.get("rationale")):
            errors.append("reader promise information_clarity_policy.rationale must be concrete")

    language = data.get("language_experience_policy")
    language_fields = (
        "forbid_summary_voice",
        "require_memorable_line_or_detail",
        "max_explanation_paragraphs_without_scene",
        "rationale",
    )
    errors.extend(_validate_required_object(language, "language_experience_policy", language_fields, require_ready=False))
    if isinstance(language, dict):
        for field in language_fields[:2]:
            _require_bool(language, "language_experience_policy", field, errors)
        _require_non_negative_int(language, "language_experience_policy", "max_explanation_paragraphs_without_scene", errors)
        if require_ready and has_placeholder(language.get("rationale")):
            errors.append("reader promise language_experience_policy.rationale must be concrete")

    efficiency = data.get("structural_efficiency_policy")
    efficiency_fields = (
        "min_effective_progress_per_chapter",
        "max_words_without_state_change",
        "max_low_progress_window_count",
        "window_chapters",
        "rationale",
    )
    errors.extend(_validate_required_object(efficiency, "structural_efficiency_policy", efficiency_fields, require_ready=False))
    if isinstance(efficiency, dict):
        for field in ("max_words_without_state_change", "max_low_progress_window_count", "window_chapters"):
            _require_non_negative_int(efficiency, "structural_efficiency_policy", field, errors)
        if require_ready and has_placeholder(efficiency.get("min_effective_progress_per_chapter")):
            errors.append("reader promise structural_efficiency_policy.min_effective_progress_per_chapter must be concrete")
        if require_ready and has_placeholder(efficiency.get("rationale")):
            errors.append("reader promise structural_efficiency_policy.rationale must be concrete")
    return errors


def validate_reader_reward_intensity_policy(value: object, *, require_ready: bool) -> list[str]:
    errors: list[str] = []
    allowed = {"R0", "R1", "R2", "R3", "R4"}
    if not isinstance(value, dict):
        return ["reader promise reader_reward_intensity_policy must be an object"]
    for field in (
        "opening_chapter_count",
        "opening_intensity_by_chapter",
        "default_chapter_intensity",
        "allowed_chapter_overrides",
        "rationale",
    ):
        if field not in value:
            errors.append(f"reader promise reader_reward_intensity_policy missing field: {field}")
        elif require_ready and field in {"default_chapter_intensity", "rationale"} and has_placeholder(value.get(field)):
            errors.append(f"reader promise reader_reward_intensity_policy field is placeholder: {field}")
    count = value.get("opening_chapter_count")
    if not isinstance(count, int) or count < 0:
        errors.append("reader promise reader_reward_intensity_policy.opening_chapter_count must be a non-negative integer")
    opening = value.get("opening_intensity_by_chapter")
    if not isinstance(opening, dict):
        errors.append("reader promise reader_reward_intensity_policy.opening_intensity_by_chapter must be an object")
    else:
        for chapter, intensity in opening.items():
            if str(intensity) not in allowed:
                errors.append(f"reader promise opening intensity for {chapter} must be R0-R4")
    default = str(value.get("default_chapter_intensity", "")).strip()
    if default not in allowed:
        errors.append("reader promise reader_reward_intensity_policy.default_chapter_intensity must be R0-R4")
    overrides = value.get("allowed_chapter_overrides")
    if not isinstance(overrides, (dict, list)):
        errors.append("reader promise reader_reward_intensity_policy.allowed_chapter_overrides must be an object or list")
    elif isinstance(overrides, dict):
        for chapter, item in overrides.items():
            intensity = item.get("intensity") if isinstance(item, dict) else item
            if str(intensity) not in allowed and str(chapter).lower() not in {"none", "无"}:
                errors.append(f"reader promise override intensity for {chapter} must be R0-R4")
    elif isinstance(overrides, list):
        for index, item in enumerate(overrides, start=1):
            if not isinstance(item, dict):
                errors.append(f"reader promise override #{index} must be an object")
                continue
            if str(item.get("intensity", "")) not in allowed:
                errors.append(f"reader promise override #{index} intensity must be R0-R4")
            if not str(item.get("chapter", "")).strip():
                errors.append(f"reader promise override #{index} chapter is missing")
    if require_ready and not str(value.get("rationale", "")).strip():
        errors.append("reader promise reader_reward_intensity_policy.rationale is required")
    return errors


def validate_reader_promise(data: object, *, require_ready: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["reader promise must be a JSON object"]
    if data.get("status") not in {"DRAFT", "READY"}:
        errors.append("reader promise status must be DRAFT or READY")
    if require_ready and data.get("status") != "READY":
        errors.append(f"reader promise status must be READY, got {data.get('status', 'MISSING')}")
    for field in READER_PROMISE_REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"reader promise missing field: {field}")
        elif field != "reader_reward_intensity_policy" and data.get("status") == "READY" and has_placeholder(data.get(field)):
            errors.append(f"reader promise field is empty or placeholder: {field}")
    if data.get("source_boundary") != "instruction_only_not_fact_source":
        errors.append("reader promise source_boundary must be instruction_only_not_fact_source")
    errors.extend(
        validate_reader_reward_intensity_policy(
            data.get("reader_reward_intensity_policy"),
            require_ready=require_ready or data.get("status") == "READY",
        )
    )
    errors.extend(validate_reader_experience_policies(data, require_ready=require_ready or data.get("status") == "READY"))
    return errors


def ensure_reader_promise_file() -> None:
    if not READER_PROMISE_JSON.exists():
        write_json(READER_PROMISE_JSON, default_reader_promise())
    if not READER_PROMISE_MD.exists():
        write_text(READER_PROMISE_MD, render_reader_promise_markdown(default_reader_promise()))


def load_reader_promise() -> dict[str, Any]:
    ensure_reader_promise_file()
    return read_json(READER_PROMISE_JSON, default_reader_promise())


def render_reader_promise_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Project Reader Promise",
        "",
        f"status: {data.get('status', 'DRAFT')}",
        "source_boundary: instruction_only_not_fact_source",
        "",
        "## 类型定位",
        "",
        f"- 主类型：{data.get('primary_genre', '')}",
        f"- 副类型：{data.get('secondary_genre', '')}",
        f"- 目标读者：{data.get('target_reader', '')}",
        f"- 写作场景：{data.get('platform_expectation', '')}",
        f"- genre_profile：{data.get('genre_profile', '')}",
        f"- 本书核心卖点：{data.get('core_hook', '')}",
        f"- core_sell_point：{data.get('core_sell_point', '')}",
        f"- core_mechanism_name：{data.get('core_mechanism_name', '')}",
        "- allowed_low_drama_carriers：" + "、".join(map(str, data.get("allowed_low_drama_carriers", []))),
        "- 本书主要快感来源：" + "、".join(map(str, data.get("main_reader_rewards", []))),
        "- 本书不承诺什么：" + "、".join(map(str, data.get("non_promises", []))),
        "",
        "## 前三章承诺",
        "",
        f"- 第一章必须兑现：{data.get('first_chapter_must_deliver', '')}",
        f"- 第二章必须升级：{data.get('second_chapter_must_escalate', '')}",
        f"- 第三章必须给出的上头点：{data.get('third_chapter_must_hook', '')}",
        f"- 三章内必须让读者确认的主线问题：{data.get('three_chapter_main_question', '')}",
        f"- 三章内必须展示的主角特殊性：{data.get('three_chapter_protagonist_specialness', '')}",
        "",
        "## 单章阅读承诺",
        "",
        "- 每章必须有：" + "、".join(map(str, data.get("per_chapter_must_have", []))),
        "- 每章禁止只有：" + "、".join(map(str, data.get("per_chapter_must_not_only_have", []))),
        "- 章末钩子类型优先级：" + "、".join(map(str, data.get("ending_hook_priority", []))),
        "- 爽点 / 悬念 / 笑点 / 情绪点比例：" + json.dumps(data.get("reward_mix", {}), ensure_ascii=False),
        "- 类型错位红线：" + "、".join(map(str, data.get("genre_mismatch_red_lines", []))),
        "",
        "## 正向承诺与反向禁区",
        "",
        "- positive_promises：" + "、".join(map(str, data.get("positive_promises", []))),
        "- negative_failure_modes：" + json.dumps(data.get("negative_failure_modes", {}), ensure_ascii=False),
        "",
        "## 释放阀与主角主动性",
        "",
        "- release_valve_policy：" + json.dumps(data.get("release_valve_policy", {}), ensure_ascii=False),
        "- protagonist_agency_policy：" + json.dumps(data.get("protagonist_agency_policy", {}), ensure_ascii=False),
        "",
        "## 信息、语言与结构效率",
        "",
        "- information_clarity_policy：" + json.dumps(data.get("information_clarity_policy", {}), ensure_ascii=False),
        "- language_experience_policy：" + json.dumps(data.get("language_experience_policy", {}), ensure_ascii=False),
        "- structural_efficiency_policy：" + json.dumps(data.get("structural_efficiency_policy", {}), ensure_ascii=False),
        "",
        "## 手动 R 档回报强度策略",
        "",
        f"- opening_chapter_count：{data.get('reader_reward_intensity_policy', {}).get('opening_chapter_count', '')}",
        "- opening_intensity_by_chapter："
        + json.dumps(data.get("reader_reward_intensity_policy", {}).get("opening_intensity_by_chapter", {}), ensure_ascii=False),
        f"- default_chapter_intensity：{data.get('reader_reward_intensity_policy', {}).get('default_chapter_intensity', '')}",
        "- allowed_chapter_overrides："
        + json.dumps(data.get("reader_reward_intensity_policy", {}).get("allowed_chapter_overrides", {}), ensure_ascii=False),
        f"- rationale：{data.get('reader_reward_intensity_policy', {}).get('rationale', '')}",
        "",
    ]
    return "\n".join(lines)


def review_status(text: str) -> str | None:
    for line in text.splitlines():
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


def metadata_value(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*+ ").strip()
        if not stripped:
            continue
        if ":" in stripped:
            label, value = stripped.split(":", 1)
        elif "：" in stripped:
            label, value = stripped.split("：", 1)
        else:
            continue
        if label.strip() == key:
            return value.strip()
    return ""


def review_bound_to_current_chapter(text: str, official_path: Path) -> bool:
    if not official_path.exists():
        return False
    return metadata_value(text, "official_chapter_sha256") == sha256(official_path)


def accepted_by_human_is_current(text: str, review_path: Path, official_path: Path) -> bool:
    if review_status(text) != "ACCEPTED_BY_HUMAN":
        return False
    if metadata_value(text, "accepted_by") != "human":
        return False
    if not metadata_value(text, "accepted_at"):
        return False
    if not metadata_value(text, "reason"):
        return False
    return review_bound_to_current_chapter(text, official_path)


def required_reviews_for_chapter(chapter: str) -> tuple[str, ...]:
    if chapter_number(chapter) <= 3:
        return ALL_READER_REVIEWS
    return READER_EXPERIENCE_REVIEWS


def write_default_review_template(path: Path, chapter: str, title: str) -> None:
    body = f"""# {title}: {chapter}

status: 待评

official_chapter_sha256:
review_sha256:

## Contract Checked

- 待读取 reader promise、brief、context pack、official chapter 后填写。

## Findings

- 待评。

## Evidence Quotes

- 待填：BLOCKED 或 ACCEPTED_BY_HUMAN 必须引用正文短句。

## Required Outcome

将 `status` 改为 `CLEAR`、`BLOCKED` 或 `ACCEPTED_BY_HUMAN`。
若为 `ACCEPTED_BY_HUMAN`，必须填写：

- accepted_at:
- accepted_by: human
- reason:
- official_chapter_sha256:
- review_sha256:
"""
    write_text(path, body)


def parse_personality_delta_json(raw: str) -> dict[str, Any] | None:
    value = raw.strip()
    if not value:
        return None
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("personality_delta JSON must be an object")
    return data


def validate_personality_delta(delta: object, event_type: str = "character_state_change") -> list[str]:
    errors: list[str] = []
    if delta is None:
        return []
    if event_type != "character_state_change":
        return ["personality_delta is only allowed on character_state_change events"]
    if not isinstance(delta, dict):
        return ["personality_delta must be an object"]
    target = delta.get("target_entity")
    ids = known_character_ids() | {"protagonist"}
    if target not in ids:
        errors.append(f"personality_delta.target_entity must be a known character id, got {target!r}")
    if delta.get("durability") not in {"temporary", "durable"}:
        errors.append("personality_delta.durability must be temporary or durable")
    if delta.get("does_not_rewrite_initial_personality") is not True:
        errors.append("personality_delta.does_not_rewrite_initial_personality must be true")
    fields = delta.get("changed_fields")
    if not isinstance(fields, list) or not fields:
        errors.append("personality_delta.changed_fields must be a non-empty list")
        return errors
    for index, item in enumerate(fields):
        if not isinstance(item, dict):
            errors.append(f"personality_delta.changed_fields[{index}] must be an object")
            continue
        if item.get("field") not in PERSONALITY_DELTA_FIELDS:
            errors.append(f"personality_delta.changed_fields[{index}].field is invalid")
        for key in ("from", "to", "trigger_event", "evidence_quote"):
            if has_placeholder(item.get(key)):
                errors.append(f"personality_delta.changed_fields[{index}].{key} is empty or placeholder")
    return errors


def official_chapter_path(chapter: str) -> Path:
    return ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"
