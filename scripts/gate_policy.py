from __future__ import annotations

from _common import chapter_number, gate_decision
from gate_config import load_gate_configs


def gate_errors_for_chapter(chapter: str, action: str) -> list[str]:
    number = chapter_number(chapter)
    configs = load_gate_configs()
    errors: list[str] = []
    for gate, config in sorted(configs.items(), key=lambda item: int(item[1]["needed"])):
        needed = int(config["needed"])
        if number > needed and gate_decision(gate.lower()) != "continue":
            errors.append(f"Gate {gate} must be recorded as continue before {action} chapter {needed + 1}+.")
    return errors
