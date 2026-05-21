from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, read_json


POLICY_PATH = ROOT / "ops" / "reader_reward_policy.json"
READER_PROMISE_PATH = ROOT / "state" / "project_reader_promise.json"
VALID_INTENSITIES = {"R0", "R1", "R2", "R3", "R4"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path) if path.exists() else ""}


def load_policy() -> dict[str, Any]:
    return read_json(POLICY_PATH, {})


def load_reader_promise() -> dict[str, Any]:
    return read_json(READER_PROMISE_PATH, {})


def normalize_intensity(value: object) -> str:
    text = str(value or "").strip().upper()
    return text if text in VALID_INTENSITIES else ""


def chapter_lookup_keys(chapter: str) -> tuple[str, ...]:
    number = chapter_number(chapter)
    return (chapter, f"c{number:03d}", str(number), f"{number:03d}")


def override_intensity(chapter: str, overrides: object) -> tuple[str, str]:
    keys = set(chapter_lookup_keys(chapter))
    if isinstance(overrides, dict):
        for key, item in overrides.items():
            if str(key) not in keys:
                continue
            intensity = item.get("intensity") if isinstance(item, dict) else item
            return normalize_intensity(intensity), f"allowed_chapter_overrides.{key}"
    if isinstance(overrides, list):
        for index, item in enumerate(overrides, start=1):
            if not isinstance(item, dict) or str(item.get("chapter", "")) not in keys:
                continue
            return normalize_intensity(item.get("intensity")), f"allowed_chapter_overrides[{index}]"
    return "", ""


def opening_intensity(chapter: str, opening_map: object) -> tuple[str, str]:
    keys = set(chapter_lookup_keys(chapter))
    if not isinstance(opening_map, dict):
        return "", ""
    for key, intensity in opening_map.items():
        if str(key) in keys:
            return normalize_intensity(intensity), f"opening_intensity_by_chapter.{key}"
    return "", ""


def configured_intensity_for_chapter(chapter: str, promise: dict[str, Any] | None = None) -> tuple[str, list[str], str]:
    data = promise if promise is not None else load_reader_promise()
    errors: list[str] = []
    if not isinstance(data, dict):
        return "", ["reader promise is missing or malformed"], ""
    policy = data.get("reader_reward_intensity_policy")
    if not isinstance(policy, dict):
        return "", ["reader promise missing reader_reward_intensity_policy"], ""

    override, source = override_intensity(chapter, policy.get("allowed_chapter_overrides"))
    if override:
        return override, errors, source
    if source:
        errors.append(f"reader promise {source} has illegal intensity")

    opening_count = policy.get("opening_chapter_count")
    if not isinstance(opening_count, int) or opening_count < 0:
        errors.append("reader promise opening_chapter_count must be a non-negative integer")
        opening_count = 0
    if chapter_number(chapter) <= opening_count:
        intensity, source = opening_intensity(chapter, policy.get("opening_intensity_by_chapter"))
        if intensity:
            return intensity, errors, source
        errors.append(f"reader promise missing opening intensity for {chapter}")
        return "", errors, ""

    default = normalize_intensity(policy.get("default_chapter_intensity"))
    if not default:
        errors.append("reader promise default_chapter_intensity must be R0-R4")
    return default, errors, "default_chapter_intensity" if default else ""


def level_rules(intensity: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    data = policy if policy is not None else load_policy()
    levels = data.get("levels") if isinstance(data, dict) else {}
    item = levels.get(intensity) if isinstance(levels, dict) else {}
    return item if isinstance(item, dict) else {}


def input_hashes() -> list[dict[str, str]]:
    return [file_ref(READER_PROMISE_PATH), file_ref(POLICY_PATH)]
