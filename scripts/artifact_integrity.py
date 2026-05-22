from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import ROOT


READY_STATUSES = {"READY", "WARNING", "ACCEPTED_BY_HUMAN"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def read_json_object(path: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing {label}: {rel(path)}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{label} invalid JSON {rel(path)}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{label} must be a JSON object: {rel(path)}"]
    return data, []


def validate_current_ref(ref: Any, expected_path: Path, label: str) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{label} missing file reference"]
    failures: list[str] = []
    expected_rel = rel(expected_path)
    if ref.get("path") != expected_rel:
        failures.append(f"{label} path mismatch: expected {expected_rel}")
    if not expected_path.exists():
        failures.append(f"{label} missing source file: {expected_rel}")
    elif ref.get("sha256") != sha256(expected_path):
        failures.append(f"{label} hash is stale: {expected_rel}")
    return failures


def validate_reader_reward_gate(chapter: str) -> tuple[dict[str, Any], list[str]]:
    path = ROOT / "reviews" / chapter / "reader_reward_gate.json"
    data, failures = read_json_object(path, "reader_reward_gate")
    if failures:
        return data, failures
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: reader_reward_gate chapter mismatch")
    status = str(data.get("status", "")).upper()
    if status not in READY_STATUSES:
        failures.append(f"{chapter}: reader_reward_gate status is {status or 'MISSING'}")
    chapter_path = ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    failures.extend(validate_current_ref(data.get("official_chapter"), chapter_path, f"{chapter}: reader_reward_gate official_chapter"))
    failures.extend(validate_current_ref(data.get("official_brief"), brief_path, f"{chapter}: reader_reward_gate official_brief"))
    return data, failures


def validate_chapter_shape(chapter: str) -> tuple[dict[str, Any], list[str]]:
    path = ROOT / "reviews" / chapter / "chapter_shape.json"
    data, failures = read_json_object(path, "chapter_shape")
    if failures:
        return data, failures
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: chapter_shape chapter mismatch")
    status = str(data.get("status", "")).upper()
    if status not in READY_STATUSES:
        failures.append(f"{chapter}: chapter_shape status is {status or 'MISSING'}")
    chapter_path = ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"
    failures.extend(validate_current_ref(data.get("official_chapter"), chapter_path, f"{chapter}: chapter_shape official_chapter"))
    return data, failures
