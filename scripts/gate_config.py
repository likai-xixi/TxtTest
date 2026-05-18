from __future__ import annotations

from typing import Any

from _common import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by environments without PyYAML
    yaml = None


GATE_KEYS = {
    "A": "gate_a_3_chapters",
    "B": "gate_b_10_chapters",
    "C": "gate_c_25_chapters",
    "E": "gate_e_125_chapters",
    "F": "gate_f_200_chapters",
    "G": "gate_g_500_chapters",
    "H": "gate_h_800_chapters",
}

DEFAULT_CRITERIA = {
    "A": "outline/gate_a_3_chapters.md",
    "B": "outline/gate_b_10_chapters.md",
    "C": "ops/gate_rules.yaml",
    "E": "ops/gate_rules.yaml",
    "F": "ops/gate_rules.yaml",
    "G": "ops/gate_rules.yaml",
    "H": "ops/gate_rules.yaml",
}

DEFAULT_READER_SYNTHESIS = {
    "A": "reader_tests/gate_a_synthesis.md",
    "B": "reader_tests/gate_b_synthesis.md",
    "C": None,
    "E": None,
    "F": None,
    "G": None,
    "H": None,
}

DEFAULT_READER_RESPONSE_DIR = {
    "A": "reader_tests/responses/gate_a",
    "B": "reader_tests/responses/gate_b",
    "C": None,
    "E": None,
    "F": None,
    "G": None,
    "H": None,
}

DEFAULT_MIN_READER_RESPONSES = {
    "A": 3,
    "B": 3,
    "C": 0,
    "E": 0,
    "F": 0,
    "G": 0,
    "H": 0,
}

DEFAULT_NEEDED = {
    "A": 3,
    "B": 10,
    "C": 25,
    "E": 125,
    "F": 200,
    "G": 500,
    "H": 800,
}

DEFAULT_ASSESSMENT = {
    "A": None,
    "B": None,
    "C": "state/gates/gate_c_assessment.md",
    "E": "state/gates/gate_e_300w_assessment.md",
    "F": "state/gates/gate_f_context_governance.md",
    "G": "state/gates/gate_g_longform_debt.md",
    "H": "state/gates/gate_h_terminal_governance.md",
}


def _as_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"ops/gate_rules.yaml {name} must be a mapping")
    return value


def _as_int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"ops/gate_rules.yaml {name} must be an integer") from exc


def _as_optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError(f"ops/gate_rules.yaml {name} must be text")
    return value


def _as_text_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeError(f"ops/gate_rules.yaml {name} must be a list of text")
    return value


def load_gate_configs() -> dict[str, dict[str, Any]]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read ops/gate_rules.yaml")

    path = ROOT / "ops" / "gate_rules.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data = _as_mapping(data, "root")

    configs: dict[str, dict[str, Any]] = {}
    for gate, key in GATE_KEYS.items():
        raw_value = data.get(key)
        if raw_value is None and gate in {"F", "G", "H"}:
            raw = {
                "gate": gate,
                "decide_only_after_chapters": DEFAULT_NEEDED[gate],
                "criteria": DEFAULT_CRITERIA[gate],
                "required_assessment": DEFAULT_ASSESSMENT[gate],
                "assessment_sections": [],
            }
        else:
            raw = _as_mapping(raw_value, key)
        gate_id = _as_optional_text(raw.get("gate"), f"{key}.gate")
        if gate_id != gate:
            raise RuntimeError(f"ops/gate_rules.yaml {key}.gate must be {gate!r}")
        needed = _as_int(raw.get("decide_only_after_chapters"), f"{key}.decide_only_after_chapters")
        configs[gate] = {
            "gate": gate_id,
            "needed": needed,
            "criteria": _as_optional_text(raw.get("criteria"), f"{key}.criteria") or DEFAULT_CRITERIA[gate],
            "reader_synthesis": _as_optional_text(
                raw.get("reader_synthesis"), f"{key}.reader_synthesis"
            )
            or DEFAULT_READER_SYNTHESIS[gate],
            "reader_response_dir": _as_optional_text(
                raw.get("reader_response_dir"), f"{key}.reader_response_dir"
            )
            or DEFAULT_READER_RESPONSE_DIR[gate],
            "min_reader_responses": _as_int(
                raw.get("min_reader_responses", DEFAULT_MIN_READER_RESPONSES[gate]),
                f"{key}.min_reader_responses",
            ),
            "assessment": _as_optional_text(raw.get("required_assessment", DEFAULT_ASSESSMENT[gate]), f"{key}.required_assessment"),
            "assessment_sections": _as_text_list(raw.get("assessment_sections"), f"{key}.assessment_sections"),
        }
    return configs
