from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


DEFAULT_CONTEXT_PACK = {
    "hard_max_chars": 24000,
    "tiers": [
        {"max_chapter": 3, "limit_chars": 6000},
        {"max_chapter": 10, "limit_chars": 8000},
        {"max_chapter": 50, "limit_chars": 10000},
        {"max_chapter": 200, "limit_chars": 12000},
        {"max_chapter": 500, "limit_chars": 16000},
        {"max_chapter": 800, "limit_chars": 20000},
    ],
    "section_budgets": {
        "core_freeze": 1600,
        "chapter_brief": 2500,
        "chapter_anchor_continuity": 900,
        "active_aftermath_obligations": 900,
        "authorized_elements_full": 4000,
        "active_entity_cards": 3500,
        "open_threads": 2500,
        "recent_events": 2000,
        "arc_summary": 2000,
        "rules_and_boundaries": 2000,
    },
}


def load_process_budget() -> dict[str, Any]:
    path = ROOT / "ops" / "process_budget.yaml"
    if yaml is None:
        raise RuntimeError("PyYAML is required to read ops/process_budget.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError("ops/process_budget.yaml must be a mapping")
    context_pack = data.get("context_pack") or {}
    if not isinstance(context_pack, dict):
        raise RuntimeError("ops/process_budget.yaml context_pack must be a mapping")
    merged = dict(DEFAULT_CONTEXT_PACK)
    merged.update(context_pack)
    merged["tiers"] = context_pack.get("tiers") or DEFAULT_CONTEXT_PACK["tiers"]
    merged["section_budgets"] = {
        **DEFAULT_CONTEXT_PACK["section_budgets"],
        **(context_pack.get("section_budgets") or {}),
    }
    pilot = data.get("pilot") or {}
    if not isinstance(pilot, dict):
        pilot = {}
    chapter_brief_chars = pilot.get("chapter_brief_chars") or {}
    if not isinstance(chapter_brief_chars, dict):
        chapter_brief_chars = {}
    pilot = {
        **pilot,
        "chapter_brief_chars": {
            "min": int(chapter_brief_chars.get("min", 300)),
            "max": int(chapter_brief_chars.get("max", 1800)),
        },
    }
    return {"context_pack": merged, "pilot": pilot}


def context_pack_budget(chapter: str, override: int | None = None) -> int:
    config = load_process_budget()["context_pack"]
    hard_max = int(config["hard_max_chars"])
    if override is not None:
        return min(int(override), hard_max)
    number = chapter_number(chapter)
    tiers = sorted(config["tiers"], key=lambda item: int(item["max_chapter"]))
    for tier in tiers:
        if number <= int(tier["max_chapter"]):
            return min(int(tier["limit_chars"]), hard_max)
    return hard_max


def section_budgets() -> dict[str, int]:
    return {key: int(value) for key, value in load_process_budget()["context_pack"]["section_budgets"].items()}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def input_hash(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)}


def context_manifest_path(chapter: str) -> Path:
    return ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"


def context_quality_path(chapter: str) -> Path:
    return ROOT / "state" / "derived" / "context_quality" / f"{chapter}.json"
