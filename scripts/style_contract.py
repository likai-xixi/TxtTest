from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from core_setting_freeze import selected_idea_id, validate_freeze


CONTRACT_JSON = ROOT / "state" / "project_style_contract.json"
CONTRACT_MD = ROOT / "state" / "project_style_contract.md"
STYLE_GUIDE = ROOT / "bible" / "style_guide.md"
STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"
PLACEHOLDERS = ("TODO", "TBD", "待定", "待填", "寰呭畾", "寰呭～")

REQUIRED_FIELDS = (
    "narration_person",
    "narration_distance",
    "tense_policy",
    "sentence_rhythm",
    "paragraph_density",
    "dialogue_ratio",
    "interiority_ratio",
    "action_style",
    "exposition_policy",
    "emotional_tone",
    "humor_level",
    "payoff_style",
    "metaphor_sources",
    "forbidden_styles",
    "reference_style_policy",
    "imitation_policy",
)

BLOCKER_MARKERS = {
    "[style-drift:person]": "chapter declares person drift",
    "[style_drift:person]": "chapter declares person drift",
    "[style-drift:distance]": "chapter declares narration distance drift",
    "[style_drift:distance]": "chapter declares narration distance drift",
    "[style-drift:voice]": "chapter declares protagonist voice drift",
    "[style_drift:voice]": "chapter declares protagonist voice drift",
}

WARNING_MARKERS = {
    "[style-drift:dialogue]": "chapter declares dialogue ratio drift",
    "[style_drift:dialogue]": "chapter declares dialogue ratio drift",
    "[style-drift:exposition]": "chapter declares exposition drift",
    "[style_drift:exposition]": "chapter declares exposition drift",
}


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
    return ROOT / "state" / "idea_lab" / idea_id / "style_contract.json"


def candidate_md_path(idea_id: str) -> Path:
    return ROOT / "state" / "idea_lab" / idea_id / "style_contract.md"


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def default_contract(idea_id: str, *, status: str = "CANDIDATE") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": status,
        "idea_id": idea_id,
        "created_at": now_iso(),
        "narration_person": "third_person_limited",
        "narration_distance": "close_to_protagonist",
        "tense_policy": "standard_chinese_narrative_tense",
        "sentence_rhythm": "short_and_medium_sentences_for_forward_motion",
        "paragraph_density": "medium",
        "dialogue_ratio": "medium",
        "interiority_ratio": "controlled",
        "action_style": "continuous_scene_motion_with_concrete_cost",
        "exposition_policy": "reveal_in_scene_or_after_action; no encyclopedia dumps",
        "emotional_tone": "tense, restrained, commercially readable",
        "humor_level": "low",
        "payoff_style": ["information_gap_payoff", "choice_payoff", "costly_progress"],
        "metaphor_sources": ["daily life", "urban pressure", "technology when authorized by brief"],
        "forbidden_styles": [
            "internet meme voice",
            "lecture voice",
            "uncontrolled lyrical drift",
            "old-school domineering romance voice",
            "copying protected author voice or distinctive phrasing",
        ],
        "reference_style_policy": {
            "allowed": [
                "abstract pacing",
                "narration distance",
                "dialogue density",
                "emotional structure",
            ],
            "forbidden": [
                "specific sentence patterns",
                "character catchphrases",
                "worldview structure",
                "plot-beat combinations",
                "distinctive protected narrative voice",
            ],
        },
        "imitation_policy": "Do not ask any model to imitate a living or modern copyrighted author's identifiable voice. Translate references into technical parameters only.",
        "style_profile_policy": "After Gate A, build a style profile from the first three shipped chapters and check later chapters against it.",
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }


def render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value or "").strip() or "none"


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Project Style Contract",
        "",
        f"status: {data.get('status', 'UNKNOWN')}",
        f"idea_id: {data.get('idea_id', '')}",
        "",
        "This is a writing-voice contract. It is not canon and cannot write chapters.",
        "",
    ]
    for key in REQUIRED_FIELDS:
        lines.extend([f"## {key}", "", render_value(data.get(key)), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_style_guide(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Style Guide",
            "",
            "status: READY",
            "source: state/project_style_contract.json",
            "",
            "## Hard Boundaries",
            "",
            "- Do not imitate a specific modern copyrighted work or author voice.",
            "- Do not copy protected setting names, character relationships, plot-beat combinations, catchphrases, or distinctive sentence patterns.",
            "- Use references only as technical parameters such as pacing, distance, dialogue density, and emotional structure.",
            "- Polish may improve language, but it must not change person, narration distance, protagonist voice, or authorized style profile.",
            "",
            "## Voice Parameters",
            "",
            f"- narration_person: {data.get('narration_person')}",
            f"- narration_distance: {data.get('narration_distance')}",
            f"- tense_policy: {data.get('tense_policy')}",
            f"- sentence_rhythm: {data.get('sentence_rhythm')}",
            f"- paragraph_density: {data.get('paragraph_density')}",
            f"- dialogue_ratio: {data.get('dialogue_ratio')}",
            f"- interiority_ratio: {data.get('interiority_ratio')}",
            f"- action_style: {data.get('action_style')}",
            f"- exposition_policy: {data.get('exposition_policy')}",
            f"- emotional_tone: {data.get('emotional_tone')}",
            f"- humor_level: {data.get('humor_level')}",
            f"- payoff_style: {render_value(data.get('payoff_style'))}",
            f"- metaphor_sources: {render_value(data.get('metaphor_sources'))}",
            "",
            "## Forbidden Styles",
            "",
            render_value(data.get("forbidden_styles")),
            "",
        ]
    ).rstrip() + "\n"


def protected_imitation_findings(text: str) -> list[str]:
    findings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        protective = any(token in stripped for token in ("禁止", "不得", "不许", "不能", "不要", "不按", "不仿写", "不模仿", "不复制")) or any(
            token in lowered for token in ("do not", "never", "forbidden", "not imitate")
        )
        risky = (
            ("仿写" in stripped or "模仿" in stripped or "复刻" in stripped)
            and ("《" in stripped or "作者" in stripped or "小说" in stripped)
        ) or "in the style of" in lowered or "write like " in lowered
        if risky and not protective:
            findings.append(f"style guide requests identifiable imitation: {stripped[:120]}")
    return findings


def validate_contract(data: dict[str, Any], *, official: bool, include_style_guide: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["style contract must be a JSON object"]
    if data.get("schema_version") != 1:
        errors.append("style contract schema_version must be 1")
    allowed_status = {"READY"} if official else {"CANDIDATE", "READY"}
    if data.get("status") not in allowed_status:
        errors.append(f"style contract status must be one of {sorted(allowed_status)}")
    for flag in ("writes_canon", "writes_chapters", "writes_event_ledger"):
        if data.get(flag) is not False:
            errors.append(f"style contract {flag} must be false")
    for key in REQUIRED_FIELDS:
        if has_placeholder(data.get(key)):
            errors.append(f"style contract missing or placeholder field: {key}")
    errors.extend(protected_imitation_findings(json.dumps(data, ensure_ascii=False)))
    if official and include_style_guide:
        if not STYLE_GUIDE.exists():
            errors.append(f"missing style guide: {rel(STYLE_GUIDE)}")
        else:
            guide = read_text(STYLE_GUIDE)
            if has_placeholder(guide):
                errors.append(f"style guide contains placeholder text: {rel(STYLE_GUIDE)}")
            errors.extend(protected_imitation_findings(guide))
    return errors


def load_contract(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing style contract: {rel(path)}"]
    try:
        data = read_json(path, {})
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON in {rel(path)}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{rel(path)} must be a JSON object"]
    return data, []


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


def command_contract_check(args: argparse.Namespace) -> int:
    path = candidate_json_path(args.id) if args.id else CONTRACT_JSON
    data, errors = load_contract(path)
    if data is not None:
        errors.extend(validate_contract(data, official=args.id is None, include_style_guide=args.id is None))
    print("# Style Contract Check")
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
    source = candidate_json_path(args.id)
    data, errors = load_contract(source)
    errors.extend(validate_freeze(args.id))
    if data is not None:
        errors.extend(validate_contract(data, official=False, include_style_guide=False))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    assert data is not None
    data = dict(data)
    data["status"] = "READY"
    data["landed_at"] = now_iso()
    data["landed_from"] = rel(source)
    write_json(CONTRACT_JSON, data)
    write_text(CONTRACT_MD, render_markdown(data))
    write_text(STYLE_GUIDE, render_style_guide(data))
    print(f"OK: wrote {rel(CONTRACT_JSON)}")
    print(f"OK: wrote {rel(CONTRACT_MD)}")
    print(f"OK: wrote {rel(STYLE_GUIDE)}")
    return 0


def sentence_lengths(text: str) -> list[int]:
    parts = [part.strip() for part in re.split(r"[。！？.!?]+", text) if part.strip()]
    return [len(part) for part in parts]


def paragraph_lengths(text: str) -> list[int]:
    return [len(part.strip()) for part in re.split(r"\n\s*\n", text) if part.strip()]


def dialogue_line_ratio(text: str) -> float:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.0
    dialogue = [
        line
        for line in lines
        if line.startswith(("“", "\"", "'", "「", "『", "- ")) or ("”" in line and "“" in line)
    ]
    return len(dialogue) / len(lines)


def metrics_for_text(text: str) -> dict[str, Any]:
    lengths = sentence_lengths(text)
    paras = paragraph_lengths(text)
    return {
        "char_count": len(text),
        "paragraph_count": len(paras),
        "average_paragraph_chars": round(statistics.mean(paras), 2) if paras else 0,
        "average_sentence_chars": round(statistics.mean(lengths), 2) if lengths else 0,
        "dialogue_line_ratio": round(dialogue_line_ratio(text), 3),
    }


def shipped_chapters() -> list[str]:
    chapters: list[str] = []
    for decision in sorted((ROOT / "reviews").glob("v??_c???/decision.md")):
        text = read_text(decision)
        if "decision: Ship" in text:
            chapters.append(decision.parent.name)
    return chapters


def command_profile_build(_args: argparse.Namespace) -> int:
    chapters = []
    metrics = []
    for chapter in shipped_chapters():
        path = chapter_path(chapter)
        if not path.exists():
            continue
        chapters.append(chapter)
        metrics.append(metrics_for_text(read_text(path)))
    status = "READY" if len(chapters) >= 3 else "WARMUP"
    profile = {
        "schema_version": 1,
        "status": status,
        "generated_at": now_iso(),
        "generated_from_chapters": chapters,
        "metrics": {
            "chapter_count": len(chapters),
            "average_paragraph_chars": round(statistics.mean(item["average_paragraph_chars"] for item in metrics), 2) if metrics else 0,
            "average_sentence_chars": round(statistics.mean(item["average_sentence_chars"] for item in metrics), 2) if metrics else 0,
            "average_dialogue_line_ratio": round(statistics.mean(item["dialogue_line_ratio"] for item in metrics), 3) if metrics else 0,
        },
        "warnings": [] if status == "READY" else ["style profile needs three shipped chapters before it becomes READY"],
        "blockers": [],
    }
    write_json(STYLE_PROFILE, profile)
    print("# Style Profile Build")
    print()
    print(f"status: {status}")
    print(f"path: {rel(STYLE_PROFILE)}")
    return 0


def command_profile_check(_args: argparse.Namespace) -> int:
    print("# Style Profile Check")
    print()
    if not STYLE_PROFILE.exists():
        print("status: WARNING")
        print(f"- missing style profile: {rel(STYLE_PROFILE)}")
        return 0
    data = read_json(STYLE_PROFILE, {})
    status = data.get("status")
    if status == "READY":
        print("status: READY")
        print(f"path: {rel(STYLE_PROFILE)}")
        return 0
    print("status: WARNING")
    print(f"path: {rel(STYLE_PROFILE)}")
    for item in data.get("warnings", []) or ["style profile is not READY"]:
        print(f"- {item}")
    return 0


def profile_warnings_for_chapter(chapter: str) -> list[str]:
    try:
        _volume, chapter_file = chapter_parts(chapter)
    except ValueError:
        return []
    number = int(chapter_file[1:4])
    if number >= 4:
        if not STYLE_PROFILE.exists():
            return ["style profile missing after Gate A window; run style-profile-build"]
        data = read_json(STYLE_PROFILE, {})
        if data.get("status") != "READY":
            return ["style profile is not READY for post-Gate-A chapter"]
    return []


def check_chapter_text(chapter: str, text: str) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    for marker, message in BLOCKER_MARKERS.items():
        if marker in text:
            blockers.append(message)
    for marker, message in WARNING_MARKERS.items():
        if marker in text:
            warnings.append(message)
    blockers.extend(protected_imitation_findings(text))
    warnings.extend(profile_warnings_for_chapter(chapter))
    metrics = metrics_for_text(text)
    return blockers, warnings, metrics


def command_style_check(args: argparse.Namespace) -> int:
    data, errors = load_contract(CONTRACT_JSON)
    if data is not None:
        errors.extend(validate_contract(data, official=True, include_style_guide=True))
    chapter = args.chapter
    blockers = list(errors)
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    official_hash = ""
    official_rel = ""
    if chapter:
        try:
            path = chapter_path(chapter)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        official_rel = rel(path)
        if not path.exists() or not read_text(path).strip():
            blockers.append(f"missing official chapter text: {official_rel}")
        else:
            import hashlib

            text = read_text(path)
            official_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            chapter_blockers, chapter_warnings, metrics = check_chapter_text(chapter, text)
            blockers.extend(chapter_blockers)
            warnings.extend(chapter_warnings)
        result = {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "READY" if not blockers else "NOT_READY",
            "official_chapter": {"path": official_rel, "sha256": official_hash},
            "style_contract": {"path": rel(CONTRACT_JSON), "status": data.get("status") if isinstance(data, dict) else "MISSING"},
            "style_profile": {
                "path": rel(STYLE_PROFILE),
                "status": read_json(STYLE_PROFILE, {}).get("status", "MISSING") if STYLE_PROFILE.exists() else "MISSING",
            },
            "metrics": metrics,
            "blockers": blockers,
            "warnings": warnings,
        }
        out_json = ROOT / "reviews" / chapter / "style_metrics.json"
        out_md = ROOT / "reviews" / chapter / "style_consistency.md"
        write_json(out_json, result)
        write_text(out_md, render_style_report(result))
    print("# Style Check")
    print()
    if blockers:
        print("status: NOT_READY")
        for item in blockers:
            print(f"- {item}")
        return 1
    print("status: READY" if not warnings else "status: WARNING")
    for item in warnings:
        print(f"- {item}")
    return 0


def render_style_report(result: dict[str, Any]) -> str:
    lines = [
        f"# Style Consistency: {result.get('chapter')}",
        "",
        f"status: {result.get('status')}",
        "",
        "## Metrics",
        "",
        json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2),
        "",
    ]
    if result.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in result["blockers"])
        lines.append("")
    if result.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in result["warnings"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command_drift_report(_args: argparse.Namespace) -> int:
    print("# Style Drift Report")
    print()
    if not STYLE_PROFILE.exists():
        print("status: INFO")
        print("- style profile has not been built")
        return 0
    data = read_json(STYLE_PROFILE, {})
    print(f"status: {data.get('status', 'UNKNOWN')}")
    print(f"path: {rel(STYLE_PROFILE)}")
    print(json.dumps(data.get("metrics", {}), ensure_ascii=False, indent=2))
    return 0


def ensure_ready(*, stream=sys.stderr) -> bool:
    data, errors = load_contract(CONTRACT_JSON)
    if data is not None:
        errors.extend(validate_contract(data, official=True, include_style_guide=True))
    if not errors:
        return True
    for error in errors:
        print(f"ERROR: {error}", file=stream)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage project style contract, profile, and chapter style checks.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start")
    p.add_argument("--id", default=None)
    p.set_defaults(func=command_start)

    p = sub.add_parser("contract-check")
    p.add_argument("--id", default=None)
    p.set_defaults(func=command_contract_check)

    p = sub.add_parser("land")
    p.add_argument("--id", required=True)
    p.add_argument("--source", default="selected", choices=["selected"])
    p.set_defaults(func=command_land)

    p = sub.add_parser("profile-build")
    p.set_defaults(func=command_profile_build)

    p = sub.add_parser("profile-check")
    p.set_defaults(func=command_profile_check)

    p = sub.add_parser("style-check")
    p.add_argument("chapter", nargs="?")
    p.set_defaults(func=command_style_check)

    p = sub.add_parser("drift-report")
    p.set_defaults(func=command_drift_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
