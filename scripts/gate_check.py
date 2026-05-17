from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _common import ROOT, read_text
from chapter_evidence import chapter_evidence_failures
from gate_config import load_gate_configs
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
    if status not in {"CLEAR", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"gate assessment {path_text} status is {status or 'MISSING'}")
    for section in config.get("assessment_sections", []):
        if section not in text:
            failures.append(f"gate assessment {path_text} missing section {section}")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check machine-verifiable evidence before a human gate decision.")
    parser.add_argument("--gate", required=True, choices=sorted(GATES))
    args = parser.parse_args()

    gate = args.gate.upper()
    config = GATES[gate]
    failures: list[str] = []
    chapters_with_events = event_chapters()

    check_assessment(config, failures)
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
