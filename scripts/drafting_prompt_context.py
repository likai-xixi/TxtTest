from __future__ import annotations

import re

from brief_contract import (
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    MAINLINE_TRACTION_SECTIONS,
    PROGRESS_CONTRACT_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
)
from element_context import (
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    USABLE_OBJECT_ID_SECTIONS,
    brief_schema_version,
    markdown_sections,
    section_body,
)


def filtered_brief_for_drafting(brief: str) -> str:
    sections = markdown_sections(brief)
    if brief_schema_version(brief) == 2:
        story = section_body(sections, ("Story Card",)).strip()
        machine = section_body(sections, ("Machine Contract Appendix",)).strip()
        return "\n\n".join(
            [
                "# Official Story Card\n\n" + (story or "none"),
                "# Hard Boundaries\n\n" + (machine or "none"),
            ]
        ).strip()

    story_lines = [
        "Legacy brief summarized for drafting:",
        f"- 第一屏扰动：{section_body(sections, ('开篇吸引点', 'Opening Hook'))}",
        f"- 主角本章想要：{section_body(sections, ('主角目标', 'Protagonist Goal'))}",
        f"- 主角主动动作：{section_body(sections, ('主角主动选择', 'Protagonist Active Choice'))}",
        f"- 最大阻力：{section_body(sections, ('主要阻力', 'Main Obstacle'))}",
        f"- 章末点击理由：{section_body(sections, ('章末问题', 'Ending Question'))}",
    ]
    hard_parts: list[str] = []
    for aliases in (
        MAINLINE_TRACTION_SECTIONS,
        PROGRESS_CONTRACT_SECTIONS,
        COST_CONSEQUENCE_CONTRACT_SECTIONS,
        RESOLUTION_BOUNDARY_SECTIONS,
        USABLE_OBJECT_ID_SECTIONS,
        USABLE_ABILITY_ID_SECTIONS,
        ALLOWED_NEW_ELEMENT_SECTIONS,
        PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    ):
        body = section_body(sections, aliases)
        if body:
            hard_parts.append(f"## {aliases[0]}\n\n{body}")
    return "\n\n".join(
        [
            "# Official Story Card\n\n" + "\n".join(story_lines),
            "# Hard Boundaries\n\n" + ("\n\n".join(hard_parts) or "none"),
        ]
    ).strip()


def sanitize_context_pack_for_drafting(context: str) -> str:
    def replace_brief_section(match: re.Match[str]) -> str:
        header = match.group(1).rstrip()
        return (
            header
            + "\n- filtered_for_drafting: true\n\n"
            "Official brief body omitted from the drafting context pack. "
            "Use the top-level Official Story Card and Hard Boundaries supplied in this prompt.\n\n"
        )

    return re.sub(
        r"(?ms)^(## [^\n]*brief[^\n]*\n\nsource_trace:\n.*?\n\n).*?(?=^## [^\n]+\n\nsource_trace:|\Z)",
        replace_brief_section,
        context,
    ).strip()
