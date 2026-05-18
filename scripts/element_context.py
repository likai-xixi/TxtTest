from __future__ import annotations

import re
from pathlib import Path


USABLE_OBJECT_ID_SECTIONS = ("本章可用道具 IDs", "Usable Object IDs")
USABLE_ABILITY_ID_SECTIONS = ("本章可用技能 IDs", "Usable Ability IDs")
ALLOWED_NEW_ELEMENT_SECTIONS = ("本章允许新增元素", "Allowed New Elements")
PROHIBITED_INSTANT_SOLUTION_SECTIONS = ("本章禁止临场解决", "Prohibited Instant Solutions")

NONE_MARKERS = {"none", "n/a", "na", "无", "无。", "暂无", "暂无。"}
PLACEHOLDER_MARKERS = ("待定", "待填", "待人类确认", "TODO", "寰呭畾", "寰呭～")


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
