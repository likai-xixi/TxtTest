from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, read_text, write_json, write_text
from core_setting_freeze import freeze_path, selected_idea_id, validate_freeze


BOOK_JSON = ROOT / "outline" / "book_outline.json"
BOOK_MD = ROOT / "outline" / "book_outline.md"
VOLUME_DIR = ROOT / "outline" / "volumes"
PLACEHOLDERS = ("TODO", "TBD", "待定", "待填", "寰呭畾", "寰呭～")

REQUIRED_FIELDS = (
    "book_title_working",
    "genre_lane",
    "target_reader",
    "target_word_count",
    "word_count_range",
    "estimated_volumes",
    "chapter_word_count_range",
    "one_sentence_promise",
    "main_story_question",
    "protagonist_long_term_desire",
    "core_opposition",
    "worldview_reveal_strategy",
    "commercial_hook",
    "emotional_hook",
    "differentiation_angle",
    "volume_plan",
    "major_character_arcs",
    "main_thread_plan",
    "relationship_thread_plan",
    "power_or_rule_progression",
    "risk_and_cost_progression",
    "first_3_chapters_validation",
    "first_10_chapters_validation",
    "gate_plan",
    "ending_direction",
    "red_lines",
    "open_questions",
    "anti_imitation_attestation",
)

VOLUME_REQUIRED_FIELDS = (
    "volume",
    "volume_title_working",
    "estimated_word_count",
    "volume_function",
    "start_state",
    "end_state",
    "primary_opposition",
    "major_character_change",
    "promises_to_pay_off",
    "questions_not_to_solve_early",
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def has_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        return not text or any(marker in text for marker in PLACEHOLDERS)
    if isinstance(value, list):
        return not value or any(has_placeholder(item) for item in value)
    if isinstance(value, dict):
        return not value or any(has_placeholder(item) for item in value.values())
    return False


def candidate_json_path(idea_id: str) -> Path:
    return ROOT / "state" / "idea_lab" / idea_id / "book_outline_candidate.json"


def candidate_md_path(idea_id: str) -> Path:
    return ROOT / "state" / "idea_lab" / idea_id / "book_outline_candidate.md"


def freeze_data(idea_id: str | None = None) -> dict[str, Any]:
    path = freeze_path(idea_id)
    if path and path.exists():
        return read_json(path, {})
    return {}


def freeze_fields(idea_id: str | None = None) -> dict[str, str]:
    data = freeze_data(idea_id)
    fields = data.get("fields")
    return fields if isinstance(fields, dict) else {}


def current_freeze_ref(idea_id: str | None = None) -> dict[str, Any]:
    path = freeze_path(idea_id)
    if not path or not path.exists():
        return {"idea_id": idea_id or "", "path": "", "sha256": ""}
    data = read_json(path, {})
    return {
        "idea_id": str(data.get("idea_id") or idea_id or ""),
        "path": rel(path),
        "sha256": sha256_file(path),
    }


def default_contract(idea_id: str, *, status: str = "CANDIDATE") -> dict[str, Any]:
    fields = freeze_fields(idea_id)
    worldview = fields.get("worldview_core") or "The opening pilot must expose the core pressure through scenes."
    limits = fields.get("worldview_hard_limits") or "Do not resolve core rules before the brief authorizes it."
    desire = fields.get("protagonist_family") or "Protect a personal bond while pursuing the main question."
    first_three = fields.get("first_three_chapter_constraints") or "The first three chapters validate hook, agency, and pressure."
    red_lines = fields.get("forbidden_changes") or limits
    open_questions = fields.get("open_questions_allowed") or "Later volumes, exact ending mechanics, and secondary arcs remain open."
    return {
        "schema_version": 1,
        "status": status,
        "idea_id": idea_id,
        "created_at": now_iso(),
        "core_setting_freeze_ref": current_freeze_ref(idea_id),
        "book_title_working": "Working Title",
        "genre_lane": "commercial long-form genre fiction",
        "target_reader": "readers who want a strong hook, clear agency, and serialized consequences",
        "target_word_count": 3000000,
        "word_count_range": {"min": 800000, "max": 3000000},
        "estimated_volumes": 6,
        "chapter_word_count_range": {"min": 2500, "max": 6000},
        "one_sentence_promise": worldview,
        "main_story_question": "Can the protagonist uncover the true rule behind the anomaly without losing the human bond that anchors the story?",
        "protagonist_long_term_desire": desire,
        "core_opposition": limits,
        "worldview_reveal_strategy": "Reveal rules through pressure, choices, cost, and aftermath; avoid encyclopedia exposition.",
        "commercial_hook": "A repeatable anomaly creates immediate investigation pressure and chapter-end reasons to continue.",
        "emotional_hook": "The protagonist's closest relationship turns abstract rules into personal cost.",
        "differentiation_angle": "Pilot first, long-run commitments later; no full 300w fine outline before Gate A evidence.",
        "volume_plan": [
            {
                "volume": "v01",
                "volume_title_working": "Pilot Volume",
                "estimated_word_count": 120000,
                "volume_function": "Validate the premise and reader pull before expanding long-run structure.",
                "start_state": "The protagonist enters the anomaly with limited understanding.",
                "end_state": "Gate evidence decides whether the first major stage deserves expansion.",
                "primary_opposition": limits,
                "major_character_change": "The protagonist moves from reaction to costly agency.",
                "promises_to_pay_off": [first_three],
                "questions_not_to_solve_early": [open_questions],
            }
        ],
        "major_character_arcs": ["Protagonist agency must become visible before long-run escalation."],
        "main_thread_plan": ["Chapters must leave verifiable state changes, not only atmosphere."],
        "relationship_thread_plan": ["The family/intimate anchor supplies stakes, cost, and risk."],
        "power_or_rule_progression": ["Rules are authorized by brief and confirmed by shipped events only."],
        "risk_and_cost_progression": ["High progress creates aftermath obligations; no cost-free breakthroughs."],
        "first_3_chapters_validation": [
            "The one-sentence promise is legible.",
            "The protagonist makes active choices.",
            "Readers have a concrete reason to continue.",
        ],
        "first_10_chapters_validation": [
            "The first volume has sustained mainline pull.",
            "Relationship pressure remains renewable.",
            "Repeated beats and shortcut solutions are controlled.",
        ],
        "gate_plan": {
            "A": "After 3 shipped chapters, decide continue/rework/pause from reader pull and protagonist agency.",
            "B": "After 10 shipped chapters, check first-volume traction and repetition risk.",
            "C": "After 25 shipped chapters, update volume structure and restrict new core mechanisms.",
            "E": "After 125 shipped chapters, reassess 300w feasibility and debt load.",
            "F": "At 200 chapters, govern state indexes and foreshadowing ledger.",
            "G": "At 500 chapters, govern repetition, setting debt, and long-thread payoff.",
            "H": "At 800 chapters, govern endgame and restrict new long-term mechanisms.",
        },
        "ending_direction": "The ending resolves the main story question through paid costs, not an unbriefed new rule.",
        "red_lines": [red_lines],
        "open_questions": [open_questions],
        "anti_imitation_attestation": "This outline is a strategic map. It does not copy protected plots, settings, character relationships, phrases, or distinctive narrative voice.",
        "core_setting_freeze_conflicts": [],
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# Book Outline: {data.get('book_title_working', 'Working Title')}",
        "",
        f"status: {data.get('status', 'UNKNOWN')}",
        f"idea_id: {data.get('idea_id', '')}",
        "",
        "This is a strategic map. It is not canon, not an event ledger, and not a chapter brief.",
        "",
    ]
    for key in REQUIRED_FIELDS:
        lines.extend([f"## {key}", "", render_value(data.get(key)), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value or "").strip() or "none"


def validate_contract(data: dict[str, Any], *, official: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["book outline must be a JSON object"]
    if data.get("schema_version") != 1:
        errors.append("book outline schema_version must be 1")
    allowed_status = {"READY"} if official else {"CANDIDATE", "READY"}
    if data.get("status") not in allowed_status:
        errors.append(f"book outline status must be one of {sorted(allowed_status)}")
    for flag in ("writes_canon", "writes_chapters", "writes_event_ledger"):
        if data.get(flag) is not False:
            errors.append(f"book outline {flag} must be false")
    for key in REQUIRED_FIELDS:
        if has_placeholder(data.get(key)):
            errors.append(f"book outline missing or placeholder field: {key}")
    if not isinstance(data.get("volume_plan"), list) or not data.get("volume_plan"):
        errors.append("book outline volume_plan must contain at least one volume")
    else:
        for index, volume in enumerate(data["volume_plan"], start=1):
            if not isinstance(volume, dict):
                errors.append(f"volume_plan item {index} must be an object")
                continue
            for field in VOLUME_REQUIRED_FIELDS:
                if has_placeholder(volume.get(field)):
                    errors.append(f"volume_plan item {index} missing field: {field}")
    conflicts = data.get("core_setting_freeze_conflicts", [])
    if conflicts:
        errors.append("book outline declares conflicts with core_setting_freeze: " + ", ".join(map(str, conflicts)))
    ref = data.get("core_setting_freeze_ref")
    if official:
        freeze_errors = validate_freeze()
        if freeze_errors:
            errors.extend(f"core freeze not ready for book outline: {item}" for item in freeze_errors)
        elif isinstance(ref, dict):
            current = current_freeze_ref()
            if ref.get("idea_id") != current.get("idea_id"):
                errors.append("book outline core_setting_freeze_ref idea_id is stale")
            if ref.get("sha256") and ref.get("sha256") != current.get("sha256"):
                errors.append("book outline core_setting_freeze_ref sha256 is stale")
        else:
            errors.append("book outline missing core_setting_freeze_ref")
    return errors


def command_start(args: argparse.Namespace) -> int:
    idea_id = args.id or selected_idea_id()
    if not idea_id:
        print("ERROR: missing idea id; run idea-select first or pass --id", file=sys.stderr)
        return 1
    lab = ROOT / "state" / "idea_lab" / idea_id
    if not lab.exists():
        print(f"ERROR: missing idea lab: {rel(lab)}", file=sys.stderr)
        return 1
    data = default_contract(idea_id)
    write_json(candidate_json_path(idea_id), data)
    write_text(candidate_md_path(idea_id), render_markdown(data))
    print(f"OK: wrote {rel(candidate_json_path(idea_id))}")
    print(f"OK: wrote {rel(candidate_md_path(idea_id))}")
    return 0


def load_contract(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing book outline: {rel(path)}"]
    try:
        data = read_json(path, {})
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON in {rel(path)}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{rel(path)} must be a JSON object"]
    return data, []


def command_check(args: argparse.Namespace) -> int:
    path = candidate_json_path(args.id) if args.id else BOOK_JSON
    data, errors = load_contract(path)
    if data is not None:
        errors.extend(validate_contract(data, official=args.id is None))
    print("# Book Outline Check")
    print()
    if errors:
        print("status: NOT_READY")
        print(f"path: {rel(path)}")
        print()
        for error in errors:
            print(f"- {error}")
        return 1
    print("status: READY")
    print(f"path: {rel(path)}")
    return 0


def command_land(args: argparse.Namespace) -> int:
    idea_id = args.id
    source = candidate_json_path(idea_id)
    data, errors = load_contract(source)
    errors.extend(validate_freeze(idea_id))
    if data is not None:
        errors.extend(validate_contract(data, official=False))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    assert data is not None
    data = dict(data)
    data["status"] = "READY"
    data["landed_at"] = now_iso()
    data["landed_from"] = rel(source)
    data["core_setting_freeze_ref"] = current_freeze_ref(idea_id)
    write_json(BOOK_JSON, data)
    write_text(BOOK_MD, render_markdown(data))
    print(f"OK: wrote {rel(BOOK_JSON)}")
    print(f"OK: wrote {rel(BOOK_MD)}")
    if args.build_volume:
        return command_volume_build(argparse.Namespace(volume=args.volume))
    return 0


def volume_json_path(volume: str) -> Path:
    return VOLUME_DIR / f"{volume}_outline.json"


def volume_md_path(volume: str) -> Path:
    return VOLUME_DIR / f"{volume}_outline.md"


def volume_from_book(data: dict[str, Any], volume: str) -> dict[str, Any] | None:
    for item in data.get("volume_plan", []) or []:
        if isinstance(item, dict) and str(item.get("volume")) == volume:
            return item
    return None


def command_volume_build(args: argparse.Namespace) -> int:
    data, errors = load_contract(BOOK_JSON)
    if data is not None:
        errors.extend(validate_contract(data, official=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    assert data is not None
    volume = volume_from_book(data, args.volume)
    if volume is None:
        print(f"ERROR: book outline has no volume_plan entry for {args.volume}", file=sys.stderr)
        return 1
    outline = {
        "schema_version": 1,
        "status": "READY",
        "book_outline_ref": {"path": rel(BOOK_JSON), "sha256": sha256_file(BOOK_JSON)},
        **volume,
        "updated_at": now_iso(),
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }
    write_json(volume_json_path(args.volume), outline)
    write_text(volume_md_path(args.volume), render_volume_markdown(outline))
    print(f"OK: wrote {rel(volume_json_path(args.volume))}")
    print(f"OK: wrote {rel(volume_md_path(args.volume))}")
    return 0


def render_volume_markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# Volume Outline: {data.get('volume', '')}",
        "",
        f"status: {data.get('status', 'UNKNOWN')}",
        "",
        "This rolling outline is a planning asset, not canon.",
        "",
    ]
    for field in VOLUME_REQUIRED_FIELDS:
        lines.extend([f"## {field}", "", render_value(data.get(field)), ""])
    return "\n".join(lines).rstrip() + "\n"


def validate_volume(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("volume outline schema_version must be 1")
    if data.get("status") != "READY":
        errors.append("volume outline status must be READY")
    for flag in ("writes_canon", "writes_chapters", "writes_event_ledger"):
        if data.get(flag) is not False:
            errors.append(f"volume outline {flag} must be false")
    for field in VOLUME_REQUIRED_FIELDS:
        if has_placeholder(data.get(field)):
            errors.append(f"volume outline missing or placeholder field: {field}")
    ref = data.get("book_outline_ref")
    if isinstance(ref, dict) and ref.get("sha256") and BOOK_JSON.exists() and ref["sha256"] != sha256_file(BOOK_JSON):
        errors.append("volume outline book_outline_ref sha256 is stale")
    return errors


def command_volume_check(args: argparse.Namespace) -> int:
    path = volume_json_path(args.volume)
    if not path.exists():
        print("# Volume Outline Check")
        print()
        print("status: WARNING")
        print(f"- missing volume outline: {rel(path)}")
        return 0
    data, errors = load_contract(path)
    if data is not None:
        errors.extend(validate_volume(data))
    print("# Volume Outline Check")
    print()
    if errors:
        print("status: NOT_READY")
        print(f"path: {rel(path)}")
        for error in errors:
            print(f"- {error}")
        return 1
    print("status: READY")
    print(f"path: {rel(path)}")
    return 0


def ensure_ready(*, stream=sys.stderr) -> bool:
    data, errors = load_contract(BOOK_JSON)
    if data is not None:
        errors.extend(validate_contract(data, official=True))
    if not errors:
        return True
    for error in errors:
        print(f"ERROR: {error}", file=stream)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage book outline and rolling volume outline contracts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start")
    p.add_argument("--id", default=None)
    p.set_defaults(func=command_start)

    p = sub.add_parser("check")
    p.add_argument("--id", default=None)
    p.set_defaults(func=command_check)

    p = sub.add_parser("land")
    p.add_argument("--id", required=True)
    p.add_argument("--source", default="selected", choices=["selected"])
    p.add_argument("--volume", default="v01")
    p.add_argument("--build-volume", action="store_true")
    p.set_defaults(func=command_land)

    p = sub.add_parser("volume-build")
    p.add_argument("--volume", required=True)
    p.set_defaults(func=command_volume_build)

    p = sub.add_parser("volume-check")
    p.add_argument("--volume", required=True)
    p.set_defaults(func=command_volume_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
