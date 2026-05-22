from __future__ import annotations

import re
from pathlib import Path


USABLE_OBJECT_ID_SECTIONS = ("本章可用道具 IDs", "Usable Object IDs")
USABLE_ABILITY_ID_SECTIONS = ("本章可用技能 IDs", "Usable Ability IDs")
ALLOWED_NEW_ELEMENT_SECTIONS = ("本章允许新增元素", "Allowed New Elements")
PROHIBITED_INSTANT_SOLUTION_SECTIONS = ("本章禁止临场解决", "Prohibited Instant Solutions")

NONE_MARKERS = {"none", "n/a", "na", "无", "无。", "暂无", "暂无。"}
PLACEHOLDER_MARKERS = ("待定", "待填", "待人类确认", "TODO", "寰呭畾", "寰呭～")


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def brief_schema_version(text: str) -> int:
    match = re.search(r"(?mi)^\s*schema_version\s*[:：]\s*(\d+)\s*$", text or "")
    return int(match.group(1)) if match else 1


def _normalized_label(text: str) -> str:
    return compact_text(text).strip("`*#-：:")


def _labeled_blocks(body: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for raw in body.splitlines():
        top_level = raw.startswith(("- ", "* ", "+ "))
        line = raw.strip()
        if not line:
            if current:
                blocks[current].append("")
            continue
        match = re.match(r"^[-*+]\s*([^:：]+)\s*[:：]\s*(.*)$", line) if top_level else None
        if match:
            current = _normalized_label(match.group(1))
            blocks.setdefault(current, [])
            value = match.group(2).strip()
            if value:
                blocks[current].append(value)
            continue
        if current:
            blocks[current].append(line)
    return {key: "\n".join(value).strip() for key, value in blocks.items()}


def _block_value(blocks: dict[str, str], *labels: str) -> str:
    for label in labels:
        value = blocks.get(_normalized_label(label), "").strip()
        if value:
            return value
    return ""


def _append_unique_lines(*parts: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for raw in (part or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            key = compact_text(line)
            if key in seen:
                continue
            lines.append(line)
            seen.add(key)
    return "\n".join(lines).strip()


def _line(label: str, value: str) -> str:
    return f"- {label}：{value.strip()}" if value.strip() else ""


def _ensure_section(sections: dict[str, list[str]], title: str, body: str) -> None:
    if body.strip() and title not in sections:
        sections[title] = body.splitlines()


def _normalize_v2_brief_sections(text: str, sections: dict[str, list[str]]) -> None:
    if brief_schema_version(text) != 2:
        return
    story = _labeled_blocks("\n".join(sections.get("Story Card", [])))
    machine = _labeled_blocks("\n".join(sections.get("Machine Contract Appendix", [])))
    if not story and not machine:
        return

    first_disturbance = _block_value(story, "第一屏扰动")
    protagonist_want = _block_value(story, "主角本章想要")
    protagonist_action = _block_value(story, "主角主动动作")
    obstacle = _block_value(story, "最大阻力")
    midpoint_turn = _block_value(story, "中段变化点")
    small_payoff = _block_value(story, "本章小兑现")
    before_after = _block_value(story, "before -> after", "before→after")
    next_click = _block_value(story, "章末点击理由")
    one_rule = _block_value(story, "本章只讲懂的一条世界规则")
    forbidden_break = _block_value(story, "禁止临场破局")

    progress_contract = _append_unique_lines(
        _block_value(machine, "本章进展契约"),
        _line("有效推进单位", before_after),
        _line("有效推进证据目标", _block_value(machine, "reward_evidence_requirement", "回报证据要求") or small_payoff),
        _line("最低落账事件", _block_value(machine, "最低落账事件")),
    )
    retention_contract = _append_unique_lines(
        _line("第一屏钩子", first_disturbance),
        _line("本章核心问题", protagonist_want or next_click),
        _line("本章读者期待", small_payoff or next_click),
        _line("reader_reward_intensity", _block_value(machine, "reader_reward_intensity")),
        _line("reader_reward_type", _block_value(machine, "reader_reward_type")),
        _line("reader_reward_delivery", _block_value(machine, "reader_reward_delivery") or small_payoff),
        _line("reader_reward_timing", _block_value(machine, "reader_reward_timing")),
        _line("reward_evidence_requirement", _block_value(machine, "reward_evidence_requirement") or small_payoff),
        _line("低戏剧载体", _block_value(machine, "低戏剧载体", "low_drama_carrier")),
        _line("低戏剧载体承载的推进类型", _block_value(machine, "低戏剧载体承载的推进类型", "low_drama_progress_type")),
        _line("核心机制是否出现", _block_value(machine, "核心机制是否出现", "core_mechanism_presence")),
        _line("若未出现，当前沉默计数", _block_value(machine, "若未出现，当前沉默计数", "core_mechanism_silent_count")),
        _line("等待结尾债务", _block_value(machine, "等待结尾债务", "waiting_ending_debt")),
        _line("本章中段反转 / 加压", midpoint_turn),
        _line("本章小兑现", small_payoff),
        _line("本章章末钩子", next_click),
        _line("下一章点击理由", next_click),
    )

    _ensure_section(sections, "本章功能", f"{protagonist_want}；{small_payoff}")
    _ensure_section(sections, "开篇吸引点", first_disturbance)
    _ensure_section(sections, "主角目标", protagonist_want)
    _ensure_section(sections, "主要阻力", obstacle)
    _ensure_section(sections, "主角主动选择", protagonist_action)
    _ensure_section(sections, "上章章末锚点", _block_value(machine, "上章章末锚点"))
    _ensure_section(sections, "本章开场落点", _block_value(machine, "本章开场落点"))
    _ensure_section(sections, "场景承接说明", _block_value(machine, "场景承接说明"))
    _ensure_section(sections, "主线牵引档位", _block_value(machine, "主线牵引档位"))
    _ensure_section(sections, "外部压力档位", _block_value(machine, "外部压力档位"))
    _ensure_section(sections, "本章继承变化", _block_value(machine, "本章继承变化"))
    _ensure_section(sections, "本章节奏用途", _block_value(machine, "本章节奏用途"))
    _ensure_section(sections, "节奏说明", _block_value(machine, "节奏说明") or midpoint_turn)
    _ensure_section(sections, "本章进展契约", progress_contract)
    _ensure_section(sections, "本章代价与后果契约", _block_value(machine, "本章代价与后果契约"))
    _ensure_section(sections, "本章解决边界", _block_value(machine, "本章解决边界"))
    _ensure_section(sections, "本章推进", before_after)
    _ensure_section(sections, "信息增量", one_rule)
    _ensure_section(sections, "章末问题", next_click)
    _ensure_section(sections, "本章使用设定", one_rule)
    _ensure_section(sections, "本章可用人物状态", _block_value(machine, "可用人物状态") or "沿用 context pack 当前人物状态。")
    _ensure_section(sections, "本章可用道具 / 装备", _block_value(machine, "可用道具 / 装备", "可用道具") or _block_value(machine, "可用道具 IDs"))
    _ensure_section(sections, "本章可用道具 IDs", _block_value(machine, "可用道具 IDs"))
    _ensure_section(sections, "本章可用技能 / 能力", _block_value(machine, "可用技能 / 能力", "可用技能") or _block_value(machine, "可用技能 IDs"))
    _ensure_section(sections, "本章可用技能 IDs", _block_value(machine, "可用技能 IDs"))
    _ensure_section(sections, "能力限制 / 代价", _block_value(machine, "能力限制 / 代价") or _block_value(machine, "本章代价与后果契约"))
    _ensure_section(sections, "未解决伏笔", _block_value(machine, "未解决伏笔") or _block_value(machine, "本章解决边界"))
    _ensure_section(sections, "新增设定", _block_value(machine, "新增设定") or "none")
    _ensure_section(sections, "本章允许新增元素", _block_value(machine, "允许新增元素"))
    _ensure_section(sections, "本章禁止临场解决", _block_value(machine, "禁止临场破局", "本章禁止临场解决") or forbidden_break)
    _ensure_section(sections, "伏笔：新开 / 推进 / 回收", _block_value(machine, "本章解决边界"))
    _ensure_section(sections, "本章禁止新增", _block_value(machine, "禁止新增") or "不得新增未授权 L3/L4 机制。")
    _ensure_section(sections, "本章禁止解决", _block_value(machine, "禁止解决") or forbidden_break)
    _ensure_section(sections, "禁止新增 / 禁止解决 / 禁止模仿", _append_unique_lines(_block_value(machine, "禁止新增"), forbidden_break))
    _ensure_section(sections, "章末状态变化", _append_unique_lines(_line("type", "选择完成"), _line("reader_question", next_click), _line("next_required_continuity", next_click)))
    _ensure_section(sections, "本章留存合同", retention_contract)
    _ensure_section(
        sections,
        "本章主角魅力合同",
        _append_unique_lines(
            _line("主角本章主动目标", protagonist_want),
            _line("主角本章过人之处", protagonist_action),
            _line("主角本章弱点 / 误判 / 上头点", _block_value(machine, "主角弱点 / 误判", "主角弱点")),
            _line("金手指 / 特殊资源本章表现", _block_value(machine, "核心机制是否出现")),
            _line("能力、地位、认知或关系的刻度变化", before_after),
            _line("本章让读者喜欢主角的瞬间", protagonist_action),
        ),
    )
    _ensure_section(
        sections,
        "本章世界观展示合同",
        _append_unique_lines(
            _line("本章允许新增核心名词", _block_value(machine, "本章允许新增核心名词") or "none"),
            _line("本章允许新增次要名词", _block_value(machine, "本章允许新增次要名词") or "none"),
            _line("必须通过场景展示的设定", one_rule),
            _line("禁止集中说明的设定", one_rule),
            _line("普通人 / 外部视角对照", _block_value(machine, "普通人 / 外部视角对照") or "通过场景压力和人物反应呈现。"),
            _line("读者本章必须理解的一条规则", one_rule),
        ),
    )
    _ensure_section(
        sections,
        "本章名词预算",
        _append_unique_lines(
            _line("新核心名词上限", "1"),
            _line("新次要名词上限", "2"),
            _line("必须复用的旧名词", _block_value(machine, "必须复用的旧名词") or "none"),
            _line("本章不解释、只露面的名词", _block_value(machine, "本章不解释、只露面的名词") or "none"),
            _line("本章必须让读者看懂的规则", one_rule),
        ),
    )
    _ensure_section(
        sections,
        "本章悬念推进合同",
        _append_unique_lines(
            _line("旧问题", _block_value(machine, "旧问题") or "none"),
            _line("本章给出的新线索", small_payoff),
            _line("本章打碎的错误希望", midpoint_turn),
            _line("本章部分解答", small_payoff),
            _line("本章新问题", next_click),
            _line("悬念状态", _block_value(machine, "悬念状态") or "advanced"),
        ),
    )
    _ensure_section(
        sections,
        "本章语言记忆点",
        _append_unique_lines(
            _line("本章金句", _block_value(machine, "本章金句") or "none"),
            _line("本章梗 / 反差笑点", _block_value(machine, "本章梗 / 反差笑点") or "none"),
            _line("角色口头禅或标志动作", _block_value(machine, "角色口头禅或标志动作") or protagonist_action),
            _line("可截图传播的句子", _block_value(machine, "可截图传播的句子") or "none"),
            _line("禁止使用的平铺语气", "禁止审计腔、流程腔、总结腔。"),
        ),
    )


def markdown_sections(text: str) -> dict[str, str]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            result.setdefault(current, [])
            continue
        if current is not None:
            result[current].append(line)
    _normalize_v2_brief_sections(text, result)
    return {key: "\n".join(value).strip() for key, value in result.items()}


def section_body(sections: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if name in sections:
            return sections[name]
    return ""


def missing_section(sections: dict[str, str], names: tuple[str, ...]) -> bool:
    return not any(name in sections for name in names)


def has_placeholder(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def declared_ids(body: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = line.strip().strip("`'\"")
        if not line or line.lower() in NONE_MARKERS or line in NONE_MARKERS:
            continue
        for chunk in re.split(r"[,，]", line):
            token = chunk.strip().strip("`'\"")
            token = re.split(r"\s+|[:：#]", token, maxsplit=1)[0].strip().strip("`'\"")
            if not token or token.lower() in NONE_MARKERS or token in NONE_MARKERS:
                continue
            if token not in seen:
                ids.append(token)
                seen.add(token)
    return ids


def _scalar(value: str) -> str:
    value = value.split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def yaml_items_by_id(path: Path, root_key: str) -> dict[str, str]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    root_pattern = re.compile(rf"^{re.escape(root_key)}\s*:\s*(?:$|\[\]\s*$)")
    for index, line in enumerate(lines):
        if root_pattern.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return {}

    items: dict[str, str] = {}
    current_id: str | None = None
    current_start: int | None = None
    current_indent = 0
    item_pattern = re.compile(r"^(\s*)-\s+id\s*:\s*(.+?)\s*$")

    def close(end: int) -> None:
        if current_id is None or current_start is None:
            return
        block = "\n".join(lines[current_start:end]).rstrip()
        if block:
            items[current_id] = block

    for index in range(start, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if stripped and not line.startswith((" ", "\t", "-")) and not stripped.startswith("#"):
            break
        match = item_pattern.match(line)
        if match:
            indent = len(match.group(1))
            if current_id is None:
                current_id = _scalar(match.group(2))
                current_start = index
                current_indent = indent
            elif indent <= current_indent:
                close(index)
                current_id = _scalar(match.group(2))
                current_start = index
                current_indent = indent
    close(len(lines))
    return items


def yaml_id_index(path: Path, root_key: str) -> list[str]:
    return sorted(yaml_items_by_id(path, root_key))


def selected_yaml_section(title: str, path: Path, root_key: str, ids: list[str]) -> tuple[str, list[str]]:
    items = yaml_items_by_id(path, root_key)
    missing = [item for item in ids if item not in items]
    if missing:
        return "", missing
    if not ids:
        return f"## {title}\n\nnone\n", []
    body = "\n".join(items[item] for item in ids)
    return f"## {title}\n\n```yaml\n{root_key}:\n{body}\n```\n", []
