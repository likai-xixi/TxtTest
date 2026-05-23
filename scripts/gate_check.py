from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from _common import ROOT, read_text
from artifact_integrity import validate_current_ref
from chapter_evidence import chapter_evidence_failures
from context_governance import context_quality_path
from gate_config import load_gate_configs
from reader_personality_contracts import load_reader_promise, validate_reader_promise
from reader_test import GATE_QUESTIONS


GATES = load_gate_configs()

PLACEHOLDERS = (
    "待定",
    "待评",
    "待生成",
    "待人类裁决",
    "待填",
    "TODO",
    "寰呭畾",
    "寰呰瘎",
    "寰呯敓",
    "寰呬汉",
    "寰呭～",
)


def chapter_id(number: int) -> str:
    return f"v01_c{number:03d}"


def chapter_path(chapter: str) -> Path:
    return ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"


def decision_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return None


def candidate_selection_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "candidate_selection.md")
    for line in text.splitlines():
        if line.startswith("choice:"):
            return line.split(":", 1)[1].strip()
    return None


def event_chapters() -> set[str]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    chapters: set[str] = set()
    if not ledger.exists():
        return chapters
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("verified_by") == "human" and entry.get("chapter"):
            chapters.add(str(entry["chapter"]))
    return chapters


def has_placeholder(path: Path) -> bool:
    text = read_text(path)
    return any(marker in text for marker in PLACEHOLDERS)


def status_value(text: str) -> str | None:
    for line in text.splitlines():
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


def continuity_has_blocker(chapter: str) -> bool:
    path = ROOT / "reviews" / chapter / "continuity.md"
    text = read_text(path)
    for line in text.splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip() == "BLOCKED"
    for level in ("P0", "P1"):
        match = re.search(rf"^## {level}\n(?P<body>.*?)(?=^## |\Z)", text, flags=re.M | re.S)
        if not match:
            continue
        body = match.group("body")
        issue_lines = [line for line in body.splitlines() if line.strip().startswith("-")]
        if any("无" not in line and "none" not in line.lower() for line in issue_lines):
            return True
    return False


def check_reader_synthesis(path_text: str | None, failures: list[str]) -> None:
    if not path_text:
        return
    path = ROOT / path_text
    text = read_text(path)
    if not text.strip():
        failures.append(f"missing reader synthesis: {path_text}")
        return
    if has_placeholder(path):
        failures.append(f"reader synthesis still has placeholders: {path_text}")


def check_reader_responses(config: dict, failures: list[str]) -> None:
    directory_text = config.get("reader_response_dir")
    required = int(config.get("min_reader_responses", 0))
    if not directory_text or required <= 0:
        return
    directory = ROOT / directory_text
    count = len(list(directory.glob("*.json"))) if directory.exists() else 0
    if count < required:
        failures.append(f"reader responses below minimum: {count} < {required} in {directory_text}")
    gate = "A" if directory_text.endswith("gate_a") else "B" if directory_text.endswith("gate_b") else ""
    if gate:
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failures.append(f"reader response invalid JSON {path.relative_to(ROOT)}: {exc}")
                continue
            if str(data.get("target_reader", "")).strip() in {"", "unknown"}:
                failures.append(f"reader response {path.relative_to(ROOT)} missing target_reader")
            answers = data.get("answers", {})
            for question in GATE_QUESTIONS[gate]:
                answer = str(answers.get(question, "")).strip()
                if not answer or answer in PLACEHOLDERS:
                    failures.append(f"reader response {path.relative_to(ROOT)} missing answer: {question}")


def check_assessment(config: dict, failures: list[str]) -> None:
    path_text = config.get("assessment")
    if not path_text:
        return
    path = ROOT / str(path_text)
    text = read_text(path)
    if not text.strip():
        failures.append(f"missing gate assessment: {path_text}")
        return
    if has_placeholder(path):
        failures.append(f"gate assessment still has placeholders: {path_text}")
    status = status_value(text)
    if status not in {"CLEAR", "READY", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"gate assessment {path_text} status is {status or 'MISSING'}")
    for section in config.get("assessment_sections", []):
        if section not in text:
            failures.append(f"gate assessment {path_text} missing section {section}")


def check_gate_a_reader_experience_json(failures: list[str]) -> None:
    path = ROOT / "state" / "gates" / "gate_a_reader_experience.json"
    if not path.exists():
        failures.append("missing Gate A reader experience machine report: state/gates/gate_a_reader_experience.json")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"Gate A reader experience report invalid JSON: {exc}")
        return
    if not isinstance(data, dict):
        failures.append("Gate A reader experience report must be a JSON object")
        return
    if data.get("gate") != "A":
        failures.append("Gate A reader experience report gate must be A")
    status = str(data.get("status", "")).upper()
    if status not in {"READY", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"Gate A reader experience report status is {status or 'MISSING'}")
    recommendation = str(data.get("decision_recommendation", "")).strip()
    if recommendation != "continue":
        failures.append(f"Gate A reader experience recommendation is {recommendation or 'MISSING'}, not continue")
    checks = data.get("sustainability_checks")
    if not isinstance(checks, dict):
        failures.append("Gate A reader experience missing sustainability_checks")
    else:
        for key, value in checks.items():
            if not value:
                failures.append(f"Gate A sustainability check failed: {key}")
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers:
        failures.extend(f"Gate A reader experience blocker: {item}" for item in blockers)
    failures.extend(validate_current_ref(data.get("source_event_ledger"), ROOT / "state" / "event_ledger.jsonl", "Gate A reader experience source_event_ledger"))
    for item in data.get("chapters", []):
        if not isinstance(item, dict):
            failures.append("Gate A reader experience chapter item must be an object")
            continue
        chapter = str(item.get("chapter", ""))
        if not chapter:
            failures.append("Gate A reader experience chapter item missing chapter")
            continue
        gate_ref = item.get("reader_reward_gate")
        shape_ref = item.get("chapter_shape")
        gate_path = ROOT / "reviews" / chapter / "reader_reward_gate.json"
        shape_path = ROOT / "reviews" / chapter / "chapter_shape.json"
        failures.extend(validate_current_ref(gate_ref, gate_path, f"Gate A reader experience {chapter} reader_reward_gate"))
        failures.extend(validate_current_ref(shape_ref, shape_path, f"Gate A reader experience {chapter} chapter_shape"))


def reader_feedback_accepted(data: dict) -> bool:
    acceptance = data.get("human_acceptance")
    if not isinstance(acceptance, dict):
        return False
    risk_items = acceptance.get("risk_acceptance_items")
    if not (
        acceptance.get("accepted_by") == "human"
        and all(str(acceptance.get(key, "")).strip() for key in ("accepted_at", "reason", "report_sha256"))
        and isinstance(risk_items, list)
        and any(str(item).strip() for item in risk_items)
    ):
        return False
    clean = dict(data)
    clean.pop("human_acceptance", None)
    clean.pop("status", None)
    report_hash = hashlib.sha256(json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return acceptance.get("report_sha256") == report_hash


def check_chapter_reader_feedback(chapter: str, failures: list[str]) -> None:
    path = ROOT / "reviews" / chapter / "reader_feedback.json"
    if not path.exists():
        failures.append(f"{chapter}: missing reader feedback summary: {path.relative_to(ROOT).as_posix()}")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"{chapter}: reader feedback invalid JSON: {exc}")
        return
    if not isinstance(data, dict):
        failures.append(f"{chapter}: reader feedback must be a JSON object")
        return
    status = str(data.get("status", "")).upper()
    count = int(data.get("response_count", 0) or 0)
    if status == "READY" and count > 0:
        return
    if status == "ACCEPTED_BY_HUMAN" and reader_feedback_accepted(data):
        return
    failures.append(f"{chapter}: reader feedback requires real responses or human acceptance with reason/time/hash/risk")


def check_chapter(chapter: str, chapters_with_events: set[str], failures: list[str]) -> None:
    cpath = chapter_path(chapter)
    if not cpath.exists() or not read_text(cpath).strip():
        failures.append(f"{chapter}: missing non-empty official chapter {cpath.relative_to(ROOT)}")

    if not (ROOT / "state" / "context_pack" / f"{chapter}.md").exists():
        failures.append(f"{chapter}: missing context pack")

    if decision_for(chapter) != "Ship":
        failures.append(f"{chapter}: human decision is not Ship")

    if not candidate_selection_for(chapter):
        failures.append(f"{chapter}: missing candidate selection record")

    if chapter not in chapters_with_events:
        failures.append(f"{chapter}: missing human-verified event ledger entry")
    failures.extend(chapter_evidence_failures(chapter))


def chunk_file_for_chapter_number(number: int) -> str:
    start = ((number - 1) // 50) * 50 + 1
    return f"state/derived/arcs/chunk_{start:03d}_{start + 49:03d}.md"


def check_context_governance(gate: str, config: dict, failures: list[str]) -> None:
    required = [
        "ops/process_budget.yaml",
        "state/derived/current_state.yaml",
        "state/derived/entities",
        "state/derived/threads/open.yaml",
        "state/derived/threads/active.yaml",
        "state/derived/threads/paid_off_index.yaml",
        "state/derived/indexes/events_by_chapter",
        "state/derived/indexes/events_by_type",
        "state/derived/arcs/volume_01.md",
    ]
    if gate in {"F", "G", "H"}:
        required.append(chunk_file_for_chapter_number(config["needed"]))
    for item in required:
        path = ROOT / item
        if not path.exists():
            failures.append(f"context governance missing required derived path: {item}")

    if gate in {"F", "G", "H"}:
        for number in (200, 500, 800):
            if number <= config["needed"]:
                chunk = ROOT / chunk_file_for_chapter_number(number)
                if not chunk.exists():
                    failures.append(f"context governance missing simulated long-range chunk: {chunk.relative_to(ROOT)}")

    missing_quality = []
    context_health_failures = []
    for number in range(1, config["needed"] + 1):
        chapter = chapter_id(number)
        quality_path = context_quality_path(chapter)
        if not quality_path.exists():
            missing_quality.append(chapter)
            if len(missing_quality) >= 5:
                break
            continue
        try:
            quality = json.loads(quality_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            context_health_failures.append(f"{chapter}: invalid context quality JSON: {exc}")
            continue
        health = quality.get("context_health") if isinstance(quality, dict) else None
        if not isinstance(health, dict):
            context_health_failures.append(f"{chapter}: missing context_health in context quality report")
            continue
        blockers = health.get("blockers") if isinstance(health.get("blockers"), list) else []
        if blockers:
            context_health_failures.append(f"{chapter}: context health blockers: {', '.join(map(str, blockers[:5]))}")
    if missing_quality:
        failures.append(f"context governance missing context quality reports, first missing: {', '.join(missing_quality)}")
    if context_health_failures:
        failures.append(f"context governance context health not clear: {'; '.join(context_health_failures[:5])}")


def check_reader_experience_governance(gate: str, config: dict, failures: list[str]) -> None:
    if gate not in {"A", "B", "F", "G", "H"}:
        return
    for error in validate_reader_promise(load_reader_promise(), require_ready=True):
        failures.append(f"reader promise not ready: {error}")

    required = [
        "state/derived/personality/protagonist.json",
        "state/derived/protagonist_progression.json",
        "state/derived/concept_index.json",
        "state/derived/world_reveal_ledger.json",
        "state/derived/suspense_ledger.json",
    ]
    ledger_path = ROOT / "state" / "event_ledger.jsonl"
    expected_chapters = {chapter_id(number) for number in range(1, int(config["needed"]) + 1)}
    for item in required:
        path = ROOT / item
        if not path.exists():
            failures.append(f"reader experience missing derived ledger: {item}")
            continue
        if ledger_path.exists() and path.stat().st_mtime + 0.001 < ledger_path.stat().st_mtime:
            failures.append(f"reader experience derived ledger is stale: {item}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"reader experience ledger invalid JSON {item}: {exc}")
            continue
        blockers = data.get("blockers", []) if isinstance(data, dict) else ["malformed ledger"]
        if blockers:
            failures.append(f"reader experience ledger has blockers: {item}: {', '.join(map(str, blockers[:5]))}")
        if item.endswith("protagonist_progression.json") or item.endswith("world_reveal_ledger.json"):
            chapters = {str(entry.get("chapter")) for entry in data.get("entries", []) if isinstance(entry, dict)}
            missing = sorted(expected_chapters - chapters)
            if missing:
                failures.append(f"reader experience ledger missing chapter coverage {item}: {', '.join(missing[:5])}")
        if item.endswith("suspense_ledger.json"):
            chapters: set[str] = set()
            for thread in data.get("threads", []) if isinstance(data, dict) else []:
                if not isinstance(thread, dict):
                    continue
                for move in thread.get("moves", []) or []:
                    if isinstance(move, dict) and move.get("chapter"):
                        chapters.add(str(move["chapter"]))
            missing = sorted(expected_chapters - chapters)
            if missing:
                failures.append(f"suspense ledger missing chapter coverage: {', '.join(missing[:5])}")
    if gate in {"A", "B"}:
        for number in range(1, int(config["needed"]) + 1):
            check_chapter_reader_feedback(chapter_id(number), failures)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check machine-verifiable evidence before a human gate decision.")
    parser.add_argument("--gate", required=True, choices=sorted(GATES))
    args = parser.parse_args()

    gate = args.gate.upper()
    config = GATES[gate]
    failures: list[str] = []
    chapters_with_events = event_chapters()

    check_assessment(config, failures)
    if gate == "A":
        check_gate_a_reader_experience_json(failures)
    check_context_governance(gate, config, failures)
    check_reader_experience_governance(gate, config, failures)
    for number in range(1, config["needed"] + 1):
        check_chapter(chapter_id(number), chapters_with_events, failures)
    check_reader_synthesis(config["reader_synthesis"], failures)
    check_reader_responses(config, failures)

    print(f"# Gate {gate} Evidence Check")
    print()
    print(f"required_chapters: {config['needed']}")
    print(f"criteria_file: {config['criteria']}")
    print()
    if failures:
        print("status: NOT_READY")
        print()
        print("## Blockers")
        print()
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("status: READY_FOR_HUMAN_DECISION")
    print()
    print("This command does not pass the gate; it only confirms the evidence is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
