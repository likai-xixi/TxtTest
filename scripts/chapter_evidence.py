from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, read_json, read_text
from brief_contract import (
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    HIGH_IMPACT_SCALES,
    LEDGER_EVENT_TYPES,
    PROGRESS_CONTRACT_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
    concrete_value,
    is_none_body,
    normalized_impact_scale,
    normalized_progress_mode,
    progress_value,
)
from candidate_style_requirements import prompt_paths, validate_prompt_manifest
from context_governance import context_manifest_path, context_quality_path
from deepseek_run_manifest import validate_run_manifest
from element_context import markdown_sections, missing_section, section_body
from element_usage import evaluate as evaluate_element_usage
from fact_cards import evaluate as evaluate_fact_cards
from reader_personality_contracts import (
    OPENING_RETENTION_REVIEW,
    READER_EXPERIENCE_REVIEWS,
    required_reviews_for_chapter,
)
from review_binding import (
    any_quote_matches_official,
    evidence_quotes,
    official_chapter_path,
    quote_matches_text,
    review_bound_to_current_chapter,
    review_hash_is_current,
    accepted_by_human_is_current,
    validate_markdown_review_binding,
)
from revision_closure import evaluate as evaluate_revision_closure
from product_kernel import always_required_ship_gates, personal_mode_runtime_failures, route_artifact_status, review_json_stale_failures
from shadow_check import evaluate as evaluate_shadow


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
CHOICES = {"Codex", "DeepSeek", "Mixed", "Rewrite brief", "No usable candidate"}
REQUIRED_MODEL_DISAGREEMENT_SECTIONS = (
    "## 双方一致的问题",
    "## Codex 独有问题",
    "## DeepSeek 独有问题",
    "## 冲突判断",
    "## 需要人类裁决事项",
    "## 建议动作",
)
AUXILIARY_REVIEWS = (
    "ai_taste.md",
    "dialogue_function.md",
    "emotion_relationship_gate.md",
    "semantic_reader_review.md",
    "memorable_scene.md",
    "web_satisfaction.md",
    "retention_risk.md",
    "originality.md",
    "similarity_risk.md",
    *READER_EXPERIENCE_REVIEWS,
)
ALLOWED_AUXILIARY_STATUS = {"CLEAR", "ACCEPTED_BY_HUMAN"}
SEMANTIC_READER_CATEGORIES = {
    "process_record_voice",
    "sermon_or_author_voice",
    "tool_character_risk",
    "information_without_drama",
}
END_STATE_CHANGE_SECTIONS = ("章末状态变化", "End State Change")


def has_placeholder(path: Path) -> bool:
    text = read_text(path)
    return any(marker in text for marker in PLACEHOLDERS)


def continuity_has_blocker(chapter: str) -> bool:
    text = read_text(ROOT / "reviews" / chapter / "continuity.md")
    for line in text.splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip() == "BLOCKED"
    return False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_current_file_ref(ref: object, expected_path: Path, label: str) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{label} missing file reference"]
    expected_rel = expected_path.relative_to(ROOT).as_posix()
    failures: list[str] = []
    if ref.get("path") != expected_rel:
        failures.append(f"{label} path mismatch: expected {expected_rel}")
    if not expected_path.exists():
        failures.append(f"{label} missing source file: {expected_rel}")
    elif ref.get("sha256") != sha256(expected_path):
        failures.append(f"{label} hash is stale: {expected_rel}")
    return failures


def normalized_text(path: Path) -> str:
    return "".join(path.read_text(encoding="utf-8").split())


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def artifact_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def status_value(text: str) -> str | None:
    for line in text.splitlines():
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


def validate_manifest_entry(chapter: str, reviewer: str, manifest: dict) -> list[str]:
    entry = manifest.get(reviewer)
    if not isinstance(entry, dict):
        return [f"{chapter}: missing {reviewer} review manifest"]

    inputs = entry.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        return [f"{chapter}: {reviewer} review manifest has no inputs"]

    paths = {item.get("path"): item for item in inputs if isinstance(item, dict)}
    volume, chapter_file = chapter_parts(chapter)
    required = {
        f"state/context_pack/{chapter}.md",
        f"state/context_pack/{chapter}_review_context.md",
        f"state/context_pack/{chapter}_review_context.json",
        f"chapters/{volume}/{chapter_file}",
    }
    allowed = {
        f"state/context_pack/{chapter}.md",
        f"state/context_pack/{chapter}_review_context.md",
        f"state/context_pack/{chapter}_review_context.json",
        f"chapters/{volume}/{chapter_file}",
        f"drafts/codex/{chapter}.md",
        f"drafts/deepseek/{chapter}.md",
        "state/project_reader_promise.json",
        "state/project_reader_promise.md",
        "state/derived/personality/protagonist.json",
        "state/derived/protagonist_progression.json",
        "state/derived/world_reveal_ledger.json",
        "state/derived/suspense_ledger.json",
    }
    failures: list[str] = []

    recorded_at = parse_time(entry.get("recorded_at"))
    if recorded_at is None:
        failures.append(f"{chapter}: {reviewer} review manifest missing valid recorded_at")

    missing = required - set(paths)
    failures.extend(f"{chapter}: {reviewer} manifest missing input {path}" for path in sorted(missing))

    for rel_path, item in paths.items():
        if rel_path not in allowed:
            failures.append(f"{chapter}: {reviewer} manifest has disallowed input {rel_path}")
            continue
        if not str(item.get("sha256", "")).strip():
            failures.append(f"{chapter}: {reviewer} manifest input missing sha256 for {rel_path}")
            continue
        path = ROOT / str(rel_path)
        if not path.exists():
            failures.append(f"{chapter}: {reviewer} manifest input missing on disk {rel_path}")
            continue
        expected = item.get("sha256")
        actual = sha256(path)
        if expected != actual:
            failures.append(f"{chapter}: {reviewer} manifest hash mismatch for {rel_path}")

    review_path = ROOT / "reviews" / chapter / f"{reviewer}_integrated_review.md"
    if recorded_at is not None and review_path.exists():
        if artifact_mtime(review_path) + timedelta(seconds=2) < recorded_at:
            failures.append(f"{chapter}: {reviewer} review artifact predates manifest")
    return failures


def selected_deepseek_candidates(selection: dict) -> list[Path]:
    candidates: list[Path] = []
    for item in selection.get("selected_candidates", []):
        rel_path = str(item.get("path", ""))
        if rel_path.startswith("drafts/deepseek/"):
            candidates.append(ROOT / rel_path)
    return candidates


def matching_selected_deepseek_candidates(chapter: str, selection: dict) -> list[Path]:
    volume, chapter_file = chapter_parts(chapter)
    official = ROOT / "chapters" / volume / chapter_file
    if not official.exists():
        return []
    official_hash = sha256(official)
    official_normalized = normalized_text(official)
    matches: list[Path] = []
    for candidate in selected_deepseek_candidates(selection):
        if not candidate.exists():
            continue
        if official_hash == sha256(candidate):
            matches.append(candidate)
        elif official_normalized and official_normalized == normalized_text(candidate):
            matches.append(candidate)
    return matches


def validate_deepseek_direct_adoption(chapter: str, selection: dict, landing: dict) -> list[str]:
    matches = matching_selected_deepseek_candidates(chapter, selection)
    if not matches:
        return []

    failures: list[str] = []
    selected_direction = landing.get("selected_direction", landing.get("source"))
    if selection.get("choice") != "DeepSeek":
        failures.append(f"{chapter}: direct DeepSeek official chapter requires candidate selection choice DeepSeek")
    if selected_direction != "DeepSeek":
        failures.append(f"{chapter}: direct DeepSeek official chapter requires landing selected_direction DeepSeek")
    if landing.get("deepseek_direct_adoption") is not True:
        failures.append(f"{chapter}: landing record must confirm deepseek_direct_adoption")

    direct_candidate = landing.get("direct_deepseek_candidate")
    direct_path = direct_candidate.get("path") if isinstance(direct_candidate, dict) else None
    match_paths = {candidate.relative_to(ROOT).as_posix() for candidate in matches}
    if direct_path not in match_paths:
        failures.append(f"{chapter}: landing record direct_deepseek_candidate does not match selected DeepSeek draft")
    return failures


def validate_landing(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "chapter_landing.json"
    record = read_json(path, {})
    if not record:
        return [f"{chapter}: missing official chapter landing record reviews/{chapter}/chapter_landing.json"]

    failures: list[str] = []
    volume, chapter_file = chapter_parts(chapter)
    chapter_rel = f"chapters/{volume}/{chapter_file}"
    required_inputs = {
        f"state/context_pack/{chapter}.md",
        f"state/derived/context_quality/{chapter}.json",
        f"outline/chapter_briefs/{chapter}.md",
    }

    if record.get("chapter") != chapter:
        failures.append(f"{chapter}: landing record chapter mismatch")
    selected_direction = record.get("selected_direction", record.get("source"))
    if selected_direction not in {"Codex", "DeepSeek", "Mixed"}:
        failures.append(f"{chapter}: landing record has invalid selected_direction")
    landed_by = record.get("landed_by", record.get("integrated_by"))
    if landed_by != "Codex":
        failures.append(f"{chapter}: landing record must have landed_by Codex")
    if not str(record.get("attestation", "")).strip():
        failures.append(f"{chapter}: landing record missing attestation")
    deepseek_direct_adoption = record.get("deepseek_direct_adoption") is True
    if deepseek_direct_adoption and selected_direction != "DeepSeek":
        failures.append(f"{chapter}: landing record deepseek_direct_adoption requires selected_direction DeepSeek")
    if not deepseek_direct_adoption and record.get("codex_integrated") is not True:
        failures.append(f"{chapter}: landing record must confirm codex_integrated")

    official = record.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: landing record missing official_chapter")
    else:
        if official.get("path") != chapter_rel:
            failures.append(f"{chapter}: landing official chapter path mismatch")
        chapter_path = ROOT / chapter_rel
        if not chapter_path.exists():
            failures.append(f"{chapter}: landing official chapter missing on disk {chapter_rel}")
        elif official.get("sha256") != sha256(chapter_path):
            failures.append(f"{chapter}: landing official chapter hash mismatch")

    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        failures.append(f"{chapter}: landing record has no inputs")
        return failures

    input_paths = {item.get("path"): item for item in inputs if isinstance(item, dict)}
    missing = required_inputs - set(input_paths)
    failures.extend(f"{chapter}: landing record missing input {item}" for item in sorted(missing))
    for rel_path, item in input_paths.items():
        if not rel_path or str(rel_path).startswith("reviews/"):
            failures.append(f"{chapter}: landing record has disallowed input {rel_path}")
            continue
        disk_path = ROOT / str(rel_path)
        if not disk_path.exists():
            failures.append(f"{chapter}: landing input missing on disk {rel_path}")
        elif item.get("sha256") != sha256(disk_path):
            failures.append(f"{chapter}: landing input hash mismatch for {rel_path}")
    return failures


def validate_context_quality(chapter: str, landing: dict) -> list[str]:
    failures: list[str] = []
    quality_path = context_quality_path(chapter)
    manifest_path = context_manifest_path(chapter)
    pack_path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    if not quality_path.exists():
        return [f"{chapter}: missing context quality report {quality_path.relative_to(ROOT)}"]
    quality = read_json(quality_path, {})
    if quality.get("status") != "READY":
        failures.append(f"{chapter}: context quality status is {quality.get('status', 'MISSING')}")
    if not pack_path.exists():
        failures.append(f"{chapter}: missing context pack for quality hash")
    elif quality.get("context_pack_sha256") != sha256(pack_path):
        failures.append(f"{chapter}: context quality context_pack_sha256 is stale")
    if not manifest_path.exists():
        failures.append(f"{chapter}: missing context manifest for quality hash")
    elif quality.get("manifest_sha256") != sha256(manifest_path):
        failures.append(f"{chapter}: context quality manifest_sha256 is stale")

    input_hashes = quality.get("input_hashes", {})
    if not isinstance(input_hashes, dict):
        failures.append(f"{chapter}: context quality input_hashes must be a mapping")

    landing_inputs = landing.get("inputs", [])
    landing_paths = {item.get("path"): item for item in landing_inputs if isinstance(item, dict)}
    quality_rel = f"state/derived/context_quality/{chapter}.json"
    if quality_rel not in landing_paths:
        failures.append(f"{chapter}: landing record missing context quality input {quality_rel}")
    elif landing_paths[quality_rel].get("sha256") != sha256(quality_path):
        failures.append(f"{chapter}: landing context quality hash mismatch")
    return failures


def validate_review_context(chapter: str) -> list[str]:
    json_path = ROOT / "state" / "context_pack" / f"{chapter}_review_context.json"
    md_path = ROOT / "state" / "context_pack" / f"{chapter}_review_context.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing review context {md_path.relative_to(ROOT)}")
    if not json_path.exists():
        return failures + [f"{chapter}: missing review context {json_path.relative_to(ROOT)}"]
    data = read_json(json_path, {})
    if not isinstance(data, dict):
        return failures + [f"{chapter}: review context must be a JSON object"]
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: review context chapter mismatch")
    if data.get("status") != "READY":
        failures.append(f"{chapter}: review context status is {data.get('status', 'MISSING')}; expected READY")
    official = data.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: review context missing official_chapter")
    elif official_chapter_path(chapter).exists() and official.get("sha256") != sha256(official_chapter_path(chapter)):
        failures.append(f"{chapter}: review context official chapter hash is stale")
    boundary = data.get("boundary")
    if not isinstance(boundary, dict) or boundary.get("no_previous_chapter_full_text") is not True:
        failures.append(f"{chapter}: review context must assert no_previous_chapter_full_text")
    failures.extend(input_hash_failures(chapter, json_path, data))
    for item in data.get("key_quotes", []):
        if isinstance(item, dict) and item.get("quote_anchor_status") not in {None, "", "matched"}:
            failures.append(f"{chapter}: review context key quote is not anchored: {item.get('event_id')}")
    return failures


def authorized_ids_from_quality(chapter: str) -> tuple[set[str], set[str]]:
    quality = read_json(context_quality_path(chapter), {})
    objects = {str(item) for item in quality.get("object_ids", []) if str(item).strip()}
    abilities = {str(item) for item in quality.get("ability_ids", []) if str(item).strip()}
    return objects, abilities


def validate_authorized_breakers(chapter: str) -> list[str]:
    volume, chapter_file = chapter_parts(chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    text = read_text(chapter_path)
    object_ids, ability_ids = authorized_ids_from_quality(chapter)
    failures: list[str] = []
    for match in re.finditer(r"\[(object|ability):([A-Za-z0-9_.-]+)\]", text):
        kind, item_id = match.group(1), match.group(2)
        if kind == "object" and item_id not in object_ids:
            failures.append(f"{chapter}: unauthorized object marker used in official chapter: {item_id}")
        if kind == "ability" and item_id not in ability_ids:
            failures.append(f"{chapter}: unauthorized ability marker used in official chapter: {item_id}")
    if re.search(r"\bL[34]\b", text):
        brief = read_text(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md")
        if not re.search(r"\bL[34]\b", brief):
            failures.append(f"{chapter}: official chapter contains L3/L4 marker not authorized by brief")
    return failures


def validate_element_usage(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "element_usage.json"
    try:
        current = evaluate_element_usage(chapter)
    except (FileNotFoundError, ValueError) as exc:
        return [f"{chapter}: element usage cannot be evaluated: {exc}"]
    if not path.exists():
        return [f"{chapter}: missing element usage report reviews/{chapter}/element_usage.json"]
    recorded = read_json(path, {})
    failures: list[str] = []
    if recorded.get("status") != "READY":
        failures.append(f"{chapter}: element usage status is {recorded.get('status', 'MISSING')}")
    for key in ("used_object_ids", "used_ability_ids", "authorized_object_ids", "authorized_ability_ids"):
        if sorted(recorded.get(key, [])) != sorted(current.get(key, [])):
            failures.append(f"{chapter}: element usage {key} is stale")
    for blocker in current.get("blockers", []):
        failures.append(f"{chapter}: {blocker}")
    return failures


def validate_selection(chapter: str) -> list[str]:
    selection = read_json(ROOT / "state" / "selections" / f"{chapter}.json", {})
    failures: list[str] = []
    choice = selection.get("choice")
    if not choice:
        return [f"{chapter}: missing structured candidate selection state/selections/{chapter}.json"]
    if choice not in CHOICES:
        failures.append(f"{chapter}: invalid candidate selection choice {choice!r}")
    if choice in {"Rewrite brief", "No usable candidate"}:
        failures.append(f"{chapter}: candidate selection {choice!r} cannot be used for Ship")
    if not str(selection.get("reason", "")).strip():
        failures.append(f"{chapter}: candidate selection missing reason")
    candidates = selection.get("selected_candidates")
    if choice in {"Codex", "DeepSeek", "Mixed"} and not candidates:
        failures.append(f"{chapter}: candidate selection missing candidate hashes")
    if isinstance(candidates, list):
        for item in candidates:
            path = ROOT / str(item.get("path", ""))
            if not path.exists():
                failures.append(f"{chapter}: selected candidate missing on disk {item.get('path')}")
                continue
            expected = item.get("sha256")
            actual = sha256(path)
            if expected != actual:
                failures.append(f"{chapter}: selected candidate hash mismatch for {item.get('path')}")
    return failures


def providers_for_choice(choice: object) -> list[str]:
    providers: list[str] = []
    if choice in {"Codex", "Mixed"}:
        providers.append("Codex")
    if choice in {"DeepSeek", "Mixed"}:
        providers.append("DeepSeek")
    return providers


def validate_candidate_prompt_evidence(chapter: str, selection: dict, landing: dict) -> list[str]:
    choice = selection.get("choice")
    providers = providers_for_choice(choice)
    if not providers:
        return []

    failures: list[str] = []
    selected_prompt_evidence = selection.get("selected_prompt_evidence")
    if not isinstance(selected_prompt_evidence, list):
        return []
    evidence_by_provider = {
        item.get("provider"): item
        for item in selected_prompt_evidence
        if isinstance(item, dict) and item.get("provider") in providers
    }

    landing_inputs = landing.get("inputs", []) if isinstance(landing, dict) else []
    landing_paths = {item.get("path"): item for item in landing_inputs if isinstance(item, dict)}
    for provider in providers:
        failures.extend(validate_prompt_manifest(chapter, provider, require_candidate_written=(provider == "DeepSeek")))
        _prompt_path, manifest_path = prompt_paths(chapter, provider)
        manifest_rel = manifest_path.relative_to(ROOT).as_posix()
        selection_item = evidence_by_provider.get(provider)
        if not isinstance(selection_item, dict):
            failures.append(f"{chapter}: candidate selection missing {provider} prompt evidence")
        else:
            manifest_item = selection_item.get("manifest")
            if not isinstance(manifest_item, dict):
                failures.append(f"{chapter}: candidate selection {provider} prompt manifest ref is malformed")
            else:
                if manifest_item.get("path") != manifest_rel:
                    failures.append(f"{chapter}: candidate selection {provider} prompt manifest path mismatch")
                elif not manifest_path.exists():
                    failures.append(f"{chapter}: selected {provider} prompt manifest missing on disk")
                elif manifest_item.get("sha256") != sha256(manifest_path):
                    failures.append(f"{chapter}: selected {provider} prompt manifest hash mismatch")
        landing_item = landing_paths.get(manifest_rel)
        if not isinstance(landing_item, dict):
            failures.append(f"{chapter}: landing record missing {provider} prompt manifest input {manifest_rel}")
        elif not manifest_path.exists():
            failures.append(f"{chapter}: landing {provider} prompt manifest missing on disk")
        elif landing_item.get("sha256") != sha256(manifest_path):
            failures.append(f"{chapter}: landing {provider} prompt manifest hash mismatch")
    return failures


def validate_model_disagreement(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "model_disagreement.md"
    text = read_text(path)
    failures: list[str] = []
    for heading in REQUIRED_MODEL_DISAGREEMENT_SECTIONS:
        if heading not in text:
            failures.append(f"{chapter}: model_disagreement missing section {heading}")
    if has_placeholder(path):
        failures.append(f"{chapter}: model_disagreement still has placeholders")
    return failures


def validate_continuity(chapter: str) -> list[str]:
    text = read_text(ROOT / "reviews" / chapter / "continuity.md")
    values: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    failures: list[str] = []
    if values.get("status") != "CLEAR":
        failures.append(f"{chapter}: continuity status is not CLEAR")
    if values.get("p0_count") != "0":
        failures.append(f"{chapter}: continuity p0_count is not 0")
    if values.get("p1_count") != "0":
        failures.append(f"{chapter}: continuity p1_count is not 0")
    return failures


def validate_style_check(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "style_metrics.json"
    failures: list[str] = []
    if not path.exists():
        return [f"{chapter}: missing style check artifact {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if data.get("status") != "READY":
        failures.append(f"{chapter}: style check status is {data.get('status', 'MISSING')}")
    official = data.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: style check missing official_chapter")
        return failures
    rel_path = official.get("path")
    expected_sha = official.get("sha256")
    if not rel_path or not expected_sha:
        failures.append(f"{chapter}: style check official_chapter missing path/sha256")
        return failures
    chapter_file = ROOT / str(rel_path)
    if not chapter_file.exists():
        failures.append(f"{chapter}: style check official chapter missing on disk")
    elif sha256(chapter_file) != expected_sha:
        failures.append(f"{chapter}: style check official chapter hash is stale")
    return failures


def validate_input_ref(chapter: str, item: object, label: str, *, required: bool = True) -> list[str]:
    if not isinstance(item, dict):
        return [f"{chapter}: series style input {label} is malformed"]
    rel_path = str(item.get("path", "")).strip()
    expected_sha = str(item.get("sha256", "")).strip()
    if not rel_path:
        return [f"{chapter}: series style input {label} missing path"]
    path = ROOT / rel_path
    if not path.exists():
        if required or item.get("exists") is True:
            return [f"{chapter}: series style input missing on disk {rel_path}"]
        return []
    if not expected_sha:
        return [f"{chapter}: series style input {rel_path} missing sha256"]
    if sha256(path) != expected_sha:
        return [f"{chapter}: series style input hash mismatch for {rel_path}"]
    return []


def validate_series_style_inputs(chapter: str, inputs: object) -> list[str]:
    if not isinstance(inputs, dict):
        return [f"{chapter}: series style report missing inputs"]
    failures: list[str] = []
    failures.extend(validate_input_ref(chapter, inputs.get("style_profile"), "style_profile"))
    failures.extend(validate_input_ref(chapter, inputs.get("style_metrics"), "style_metrics"))
    recent = inputs.get("recent_style_metrics", [])
    if recent is None:
        recent = []
    if not isinstance(recent, list):
        failures.append(f"{chapter}: series style recent_style_metrics is malformed")
    else:
        for index, item in enumerate(recent):
            failures.extend(validate_input_ref(chapter, item, f"recent_style_metrics[{index}]", required=False))
    if "deepseek_style_review" in inputs:
        failures.extend(validate_input_ref(chapter, inputs.get("deepseek_style_review"), "deepseek_style_review", required=False))
    return failures


def validate_series_style_check(chapter: str) -> list[str]:
    number = chapter_number(chapter)
    if number < 4:
        return []
    path = ROOT / "reviews" / chapter / "series_style.json"
    if not path.exists():
        return [f"{chapter}: missing series style check artifact {path.relative_to(ROOT)}"]

    data = read_json(path, {})
    failures: list[str] = []
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: series style report chapter mismatch")

    expected_mode = "ADVISORY" if number < 6 else "HARD"
    if data.get("gate_mode") != expected_mode:
        failures.append(f"{chapter}: series style gate_mode is {data.get('gate_mode', 'MISSING')}; expected {expected_mode}")

    official = data.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: series style report missing official_chapter")
    else:
        rel_path = str(official.get("path", "")).strip()
        expected_sha = str(official.get("sha256", "")).strip()
        official_path = ROOT / rel_path
        if not rel_path or not expected_sha:
            failures.append(f"{chapter}: series style official_chapter missing path/sha256")
        elif not official_path.exists():
            failures.append(f"{chapter}: series style official chapter missing on disk")
        elif sha256(official_path) != expected_sha:
            failures.append(f"{chapter}: series style official chapter hash is stale")

    status = data.get("status")
    inputs = data.get("inputs")
    failures.extend(validate_series_style_inputs(chapter, inputs))
    if isinstance(inputs, dict) and isinstance(inputs.get("deepseek_style_review"), dict):
        deepseek_rel = str(inputs["deepseek_style_review"].get("path", "")).strip()
        deepseek_path = ROOT / deepseek_rel
        if deepseek_path.exists():
            deepseek_data = read_json(deepseek_path, {})
            deepseek_official = deepseek_data.get("official_chapter") if isinstance(deepseek_data, dict) else {}
            official_sha = official.get("sha256") if isinstance(official, dict) else ""
            if not isinstance(deepseek_official, dict) or deepseek_official.get("sha256") != official_sha:
                failures.append(f"{chapter}: DeepSeek series style review is stale")
            if number >= 6 and deepseek_data.get("status") in {"BLOCKED", "NOT_READY"} and status != "ACCEPTED_BY_HUMAN":
                failures.append(f"{chapter}: DeepSeek series style review reports blocking drift")

    if number < 6:
        allowed = {"READY", "WARNING", "ACCEPTED_BY_HUMAN"}
    else:
        allowed = {"READY", "ACCEPTED_BY_HUMAN"}
    if status not in allowed:
        failures.append(f"{chapter}: series style status is {status or 'MISSING'}; expected one of {sorted(allowed)}")

    blockers = data.get("blockers", [])
    if blockers and status != "ACCEPTED_BY_HUMAN":
        failures.append(f"{chapter}: series style report has unresolved blockers")

    if status == "ACCEPTED_BY_HUMAN":
        acceptance = data.get("human_acceptance")
        if not isinstance(acceptance, dict):
            failures.append(f"{chapter}: series style human acceptance missing")
        else:
            if not str(acceptance.get("accepted_at", "")).strip():
                failures.append(f"{chapter}: series style human acceptance missing accepted_at")
            if not str(acceptance.get("reason", "")).strip():
                failures.append(f"{chapter}: series style human acceptance missing reason")
            official_sha = official.get("sha256") if isinstance(official, dict) else ""
            if acceptance.get("official_chapter_sha256") != official_sha:
                failures.append(f"{chapter}: series style human acceptance hash mismatch")
    return failures


def collect_structured_quotes(value: object) -> list[str]:
    quotes: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_quote"} and isinstance(item, str) and item.strip():
                quotes.append(item.strip())
            elif key in {"evidence_quotes"} and isinstance(item, list):
                quotes.extend(str(quote).strip() for quote in item if str(quote).strip())
            else:
                quotes.extend(collect_structured_quotes(item))
    elif isinstance(value, list):
        for item in value:
            quotes.extend(collect_structured_quotes(item))
    return quotes


def validate_structured_official_binding(chapter: str, path: Path, data: dict) -> list[str]:
    failures: list[str] = []
    official_path = official_chapter_path(chapter)
    official = data.get("official_chapter")
    if not isinstance(official, dict):
        return [f"{chapter}: structured review {path.relative_to(ROOT)} missing official_chapter"]
    expected_rel = official_path.relative_to(ROOT).as_posix()
    if official.get("path") != expected_rel:
        failures.append(f"{chapter}: structured review {path.name} official chapter path is stale or wrong")
    if not official_path.exists() or official.get("sha256") != sha256(official_path):
        failures.append(f"{chapter}: structured review {path.name} official chapter hash is missing or stale")
    return failures


def structured_review_body_hash(data: dict) -> str:
    clean = dict(data)
    clean.pop("human_acceptance", None)
    clean.pop("accepted_by", None)
    clean.pop("accepted_at", None)
    clean.pop("reason", None)
    clean.pop("review_sha256", None)
    body = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_structured_human_acceptance(chapter: str, path: Path, data: dict) -> list[str]:
    acceptance = data.get("human_acceptance")
    if not isinstance(acceptance, dict):
        return [f"{chapter}: {path.name} human_acceptance is missing"]
    failures: list[str] = []
    if acceptance.get("accepted_by") != "human":
        failures.append(f"{chapter}: {path.name} human_acceptance.accepted_by must be human")
    if not str(acceptance.get("accepted_at", "")).strip():
        failures.append(f"{chapter}: {path.name} human_acceptance.accepted_at is missing")
    if not str(acceptance.get("reason", "")).strip():
        failures.append(f"{chapter}: {path.name} human_acceptance.reason is missing")
    official = official_chapter_path(chapter)
    if not official.exists() or acceptance.get("official_chapter_sha256") != sha256(official):
        failures.append(f"{chapter}: {path.name} human_acceptance official chapter hash is missing or stale")
    if acceptance.get("review_sha256") != structured_review_body_hash(data):
        failures.append(f"{chapter}: {path.name} human_acceptance review hash is missing or stale")
    return failures


def validate_codex_anti_ai_manifest(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "codex_anti_ai_review_manifest.json"
    if not path.exists():
        return [f"{chapter}: missing Codex anti-AI review manifest {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: Codex anti-AI review manifest must be a JSON object"]
    volume, chapter_file = chapter_parts(chapter)
    required = {
        f"chapters/{volume}/{chapter_file}",
        f"outline/chapter_briefs/{chapter}.md",
        f"state/context_pack/{chapter}.md",
        f"state/context_pack/{chapter}_review_context.md",
        f"state/context_pack/{chapter}_review_context.json",
        "state/project_style_contract.json",
        "state/project_reader_promise.json",
    }
    failures: list[str] = []
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: Codex anti-AI review manifest chapter mismatch")
    if data.get("reviewer") != "codex_anti_ai_subagent":
        failures.append(f"{chapter}: Codex anti-AI review manifest reviewer must be codex_anti_ai_subagent")
    prompt = data.get("prompt")
    if not isinstance(prompt, dict):
        failures.append(f"{chapter}: Codex anti-AI review manifest missing prompt")
    else:
        prompt_path = ROOT / str(prompt.get("path", ""))
        if not prompt_path.exists():
            failures.append(f"{chapter}: Codex anti-AI review prompt is missing")
        elif prompt.get("sha256") != sha256(prompt_path):
            failures.append(f"{chapter}: Codex anti-AI review prompt hash is stale")
    inputs = data.get("inputs")
    if not isinstance(inputs, list):
        failures.append(f"{chapter}: Codex anti-AI review manifest inputs must be a list")
        return failures
    paths = {item.get("path"): item for item in inputs if isinstance(item, dict)}
    failures.extend(f"{chapter}: Codex anti-AI review manifest missing input {item}" for item in sorted(required - set(paths)))
    failures.extend(input_hash_failures(chapter, path, data, "inputs"))
    forbidden = data.get("forbidden_inputs")
    if not isinstance(forbidden, list) or not forbidden:
        failures.append(f"{chapter}: Codex anti-AI review manifest missing forbidden_inputs")
    attestation = str(data.get("isolation_attestation", "")).strip()
    if not attestation:
        failures.append(f"{chapter}: Codex anti-AI review manifest missing isolation_attestation")
    return failures


def validate_codex_semantic_reader_manifest(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "codex_semantic_reader_review_manifest.json"
    if not path.exists():
        return [f"{chapter}: missing Codex semantic reader review manifest {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: Codex semantic reader review manifest must be a JSON object"]
    volume, chapter_file = chapter_parts(chapter)
    required = {
        f"chapters/{volume}/{chapter_file}",
        f"outline/chapter_briefs/{chapter}.md",
        f"state/context_pack/{chapter}.md",
        f"state/context_pack/{chapter}_review_context.md",
        f"state/context_pack/{chapter}_review_context.json",
        "state/project_style_contract.json",
        "state/project_reader_promise.json",
    }
    failures: list[str] = []
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: Codex semantic reader review manifest chapter mismatch")
    if data.get("reviewer") != "codex_semantic_reader_subagent":
        failures.append(f"{chapter}: Codex semantic reader review manifest reviewer must be codex_semantic_reader_subagent")
    prompt = data.get("prompt")
    if not isinstance(prompt, dict):
        failures.append(f"{chapter}: Codex semantic reader review manifest missing prompt")
    else:
        prompt_path = ROOT / str(prompt.get("path", ""))
        if not prompt_path.exists():
            failures.append(f"{chapter}: Codex semantic reader review prompt is missing")
        elif prompt.get("sha256") != sha256(prompt_path):
            failures.append(f"{chapter}: Codex semantic reader review prompt hash is stale")
    inputs = data.get("inputs")
    if not isinstance(inputs, list):
        failures.append(f"{chapter}: Codex semantic reader review manifest inputs must be a list")
        return failures
    paths = {item.get("path"): item for item in inputs if isinstance(item, dict)}
    failures.extend(f"{chapter}: Codex semantic reader review manifest missing input {item}" for item in sorted(required - set(paths)))
    failures.extend(input_hash_failures(chapter, path, data, "inputs"))
    forbidden = data.get("forbidden_inputs")
    if not isinstance(forbidden, list) or not forbidden:
        failures.append(f"{chapter}: Codex semantic reader review manifest missing forbidden_inputs")
    else:
        required_forbidden = {
            f"reviews/{chapter}/deepseek_semantic_reader_review.md",
            f"reviews/{chapter}/deepseek_semantic_reader_review.json",
            f"reviews/{chapter}/semantic_reader_review.md",
            f"reviews/{chapter}/semantic_reader_review.json",
            f"reviews/{chapter}/ai_taste.json",
            f"reviews/{chapter}/dialogue_function.json",
        }
        missing = required_forbidden - set(map(str, forbidden))
        failures.extend(f"{chapter}: Codex semantic reader review manifest forbidden_inputs missing {item}" for item in sorted(missing))
    attestation = str(data.get("isolation_attestation", "")).strip()
    if not attestation:
        failures.append(f"{chapter}: Codex semantic reader review manifest missing isolation_attestation")
    return failures


def validate_ai_taste_json(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "ai_taste.json"
    if not path.exists():
        return [f"{chapter}: missing structured anti-AI review {path.relative_to(ROOT)}"]
    data, parse_failures = read_json_object(path, chapter, "ai_taste.json")
    if parse_failures:
        return parse_failures
    failures = validate_structured_official_binding(chapter, path, data)
    if data.get("status") not in {"CLEAR", "WARNING", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: ai_taste.json status is {data.get('status', 'MISSING')}; expected CLEAR, WARNING, or ACCEPTED_BY_HUMAN")
    if data.get("status") == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    categories = data.get("categories")
    required = {
        "show_dont_tell",
        "rhythm_disorder",
        "emotional_risk",
        "gray_motive",
        "dialogue_agenda",
        "detail_economy",
        "consequence_integrity",
    }
    if not isinstance(categories, dict):
        failures.append(f"{chapter}: ai_taste.json missing categories")
    else:
        missing = sorted(required - set(categories))
        failures.extend(f"{chapter}: ai_taste.json missing category {item}" for item in missing)
        for key, item in categories.items():
            if not isinstance(item, dict):
                failures.append(f"{chapter}: ai_taste.json category {key} is malformed")
                continue
            status = item.get("status")
            severity = item.get("severity")
            if data.get("status") != "ACCEPTED_BY_HUMAN" and status == "BLOCKED":
                failures.append(f"{chapter}: ai_taste.json category {key} is BLOCKED")
            if data.get("status") != "ACCEPTED_BY_HUMAN" and severity in {"P0", "P1"} and status != "CLEAR":
                failures.append(f"{chapter}: ai_taste.json category {key} has unresolved {severity}")
            if not isinstance(item.get("revision_actions"), list) or not item.get("revision_actions"):
                failures.append(f"{chapter}: ai_taste.json category {key} missing revision_actions")
            if not isinstance(item.get("issue"), str) or not item.get("issue", "").strip():
                failures.append(f"{chapter}: ai_taste.json category {key} missing issue")
    quotes = collect_structured_quotes(data)
    if not quotes:
        failures.append(f"{chapter}: ai_taste.json has no evidence quotes")
    elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
        failures.append(f"{chapter}: ai_taste.json evidence quotes do not match the official chapter")
    return failures


def validate_dialogue_function_json(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "dialogue_function.json"
    if not path.exists():
        return [f"{chapter}: missing structured dialogue review {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: structured dialogue review must be a JSON object"]
    failures = validate_structured_official_binding(chapter, path, data)
    if data.get("status") not in {"CLEAR", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: dialogue_function.json status is {data.get('status', 'MISSING')}; expected CLEAR or ACCEPTED_BY_HUMAN")
    if data.get("status") == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    samples = data.get("samples")
    if not isinstance(samples, list) or not samples:
        failures.append(f"{chapter}: dialogue_function.json requires at least one sampled dialogue or no-dialogue scene")
    else:
        for index, sample in enumerate(samples, start=1):
            if not isinstance(sample, dict):
                failures.append(f"{chapter}: dialogue_function.json sample #{index} is malformed")
                continue
            if data.get("status") != "ACCEPTED_BY_HUMAN" and sample.get("status") == "BLOCKED":
                failures.append(f"{chapter}: dialogue_function.json sample #{index} is BLOCKED")
            if not str(sample.get("function", "")).strip():
                failures.append(f"{chapter}: dialogue_function.json sample #{index} missing function")
            if not str(sample.get("character_goal", "")).strip():
                failures.append(f"{chapter}: dialogue_function.json sample #{index} missing character_goal")
    blockers = data.get("blockers")
    if data.get("status") != "ACCEPTED_BY_HUMAN" and isinstance(blockers, list) and blockers:
        failures.extend(f"{chapter}: dialogue_function.json blocker: {item}" for item in blockers)
    quotes = collect_structured_quotes(data)
    if not quotes:
        failures.append(f"{chapter}: dialogue_function.json has no evidence quotes")
    elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
        failures.append(f"{chapter}: dialogue_function.json evidence quotes do not match the official chapter")
    return failures


def validate_agent_anti_ai_review(chapter: str, stem: str, label: str) -> list[str]:
    path = ROOT / "reviews" / chapter / f"{stem}.json"
    md_path = ROOT / "reviews" / chapter / f"{stem}.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing {label} anti-AI review {md_path.relative_to(ROOT)}")
    else:
        failures.extend(validate_markdown_review_binding(chapter=chapter, review_path=md_path))
    if not path.exists():
        return failures + [f"{chapter}: missing {label} anti-AI review {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return failures + [f"{chapter}: {label} anti-AI review must be a JSON object"]
    failures.extend(validate_structured_official_binding(chapter, path, data))
    status = data.get("status")
    if status not in {"CLEAR", "ACCEPTED_BY_HUMAN"}:
        failures.append(
            f"{chapter}: {stem}.json status is {status or 'MISSING'}; "
            "expected CLEAR or ACCEPTED_BY_HUMAN"
        )
    if status == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers and status != "ACCEPTED_BY_HUMAN":
        failures.extend(f"{chapter}: {stem}.json blocker: {item}" for item in blockers)

    categories = data.get("categories")
    required = {
        "show_dont_tell",
        "rhythm_disorder",
        "emotional_risk",
        "gray_motive",
        "dialogue_agenda",
        "detail_economy",
        "setting_integration",
        "consequence_integrity",
    }
    if not isinstance(categories, dict):
        failures.append(f"{chapter}: {stem}.json missing categories")
    else:
        missing = sorted(required - set(categories))
        failures.extend(f"{chapter}: {stem}.json missing category {item}" for item in missing)
        for key, item in categories.items():
            if not isinstance(item, dict):
                failures.append(f"{chapter}: {stem}.json category {key} is malformed")
                continue
            item_status = item.get("status")
            severity = item.get("severity")
            if status != "ACCEPTED_BY_HUMAN" and item_status == "BLOCKED":
                failures.append(f"{chapter}: {stem}.json category {key} is BLOCKED")
            if status != "ACCEPTED_BY_HUMAN" and severity in {"P0", "P1"} and item_status != "CLEAR":
                failures.append(f"{chapter}: {stem}.json category {key} has unresolved {severity}")
            if not isinstance(item.get("revision_actions"), list) or not item.get("revision_actions"):
                failures.append(f"{chapter}: {stem}.json category {key} missing revision_actions")
            if not isinstance(item.get("issue"), str) or not item.get("issue", "").strip():
                failures.append(f"{chapter}: {stem}.json category {key} missing issue")

    samples = data.get("dialogue_samples")
    if not isinstance(samples, list):
        failures.append(f"{chapter}: {stem}.json dialogue_samples must be a list")
    else:
        for index, sample in enumerate(samples, start=1):
            if not isinstance(sample, dict):
                failures.append(f"{chapter}: {stem}.json dialogue sample #{index} is malformed")
                continue
            if status != "ACCEPTED_BY_HUMAN" and sample.get("status") == "BLOCKED":
                failures.append(f"{chapter}: {stem}.json dialogue sample #{index} is BLOCKED")
            if not str(sample.get("function", "")).strip():
                failures.append(f"{chapter}: {stem}.json dialogue sample #{index} missing function")
            if not str(sample.get("character_goal", "")).strip():
                failures.append(f"{chapter}: {stem}.json dialogue sample #{index} missing character_goal")

    quotes = collect_structured_quotes(data)
    if not quotes:
        failures.append(f"{chapter}: {stem}.json has no evidence quotes")
    elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
        failures.append(f"{chapter}: {stem}.json evidence quotes do not match the official chapter")
    return failures


def validate_agent_semantic_reader_review(chapter: str, stem: str, label: str) -> list[str]:
    path = ROOT / "reviews" / chapter / f"{stem}.json"
    md_path = ROOT / "reviews" / chapter / f"{stem}.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing {label} semantic reader review {md_path.relative_to(ROOT)}")
    else:
        failures.extend(validate_markdown_review_binding(chapter=chapter, review_path=md_path))
    if not path.exists():
        return failures + [f"{chapter}: missing {label} semantic reader review {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return failures + [f"{chapter}: {label} semantic reader review must be a JSON object"]
    failures.extend(validate_structured_official_binding(chapter, path, data))
    status = data.get("status")
    if status not in {"CLEAR", "ACCEPTED_BY_HUMAN"}:
        failures.append(
            f"{chapter}: {stem}.json status is {status or 'MISSING'}; "
            "expected CLEAR or ACCEPTED_BY_HUMAN"
        )
    if status == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers and status != "ACCEPTED_BY_HUMAN":
        failures.extend(f"{chapter}: {stem}.json blocker: {item}" for item in blockers)

    categories = data.get("categories")
    if not isinstance(categories, dict):
        failures.append(f"{chapter}: {stem}.json missing categories")
    else:
        missing = sorted(SEMANTIC_READER_CATEGORIES - set(categories))
        failures.extend(f"{chapter}: {stem}.json missing category {item}" for item in missing)
        for key in SEMANTIC_READER_CATEGORIES:
            item = categories.get(key)
            if not isinstance(item, dict):
                continue
            item_status = item.get("status")
            severity = item.get("severity")
            if status != "ACCEPTED_BY_HUMAN" and item_status == "BLOCKED":
                failures.append(f"{chapter}: {stem}.json category {key} is BLOCKED")
            if status != "ACCEPTED_BY_HUMAN" and severity in {"P0", "P1"} and item_status != "CLEAR":
                failures.append(f"{chapter}: {stem}.json category {key} has unresolved {severity}")
            if not isinstance(item.get("revision_actions"), list) or not item.get("revision_actions"):
                failures.append(f"{chapter}: {stem}.json category {key} missing revision_actions")
            if not isinstance(item.get("issue"), str) or not item.get("issue", "").strip():
                failures.append(f"{chapter}: {stem}.json category {key} missing issue")

    quotes = collect_structured_quotes(data)
    if not quotes:
        failures.append(f"{chapter}: {stem}.json has no evidence quotes")
    elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
        failures.append(f"{chapter}: {stem}.json evidence quotes do not match the official chapter")
    return failures


def validate_semantic_reader_review(chapter: str) -> list[str]:
    failures = validate_agent_semantic_reader_review(chapter, "semantic_reader_review", "aggregate")
    path = ROOT / "reviews" / chapter / "semantic_reader_review.json"
    if not path.exists():
        return failures
    data = read_json(path, {})
    if not isinstance(data, dict):
        return failures
    source_reviews = data.get("source_reviews")
    if not isinstance(source_reviews, dict):
        failures.append(f"{chapter}: semantic_reader_review.json missing source_reviews")
        return failures
    for stem in ("codex_semantic_reader_review", "deepseek_semantic_reader_review"):
        item = source_reviews.get(stem)
        if not isinstance(item, dict):
            failures.append(f"{chapter}: semantic_reader_review.json missing source review {stem}")
            continue
        json_ref = item.get("json")
        md_ref = item.get("markdown")
        if not isinstance(json_ref, dict):
            failures.append(f"{chapter}: semantic_reader_review.json source {stem} missing json ref")
        else:
            failures.extend(
                validate_current_file_ref(
                    json_ref,
                    ROOT / "reviews" / chapter / f"{stem}.json",
                    f"{chapter}: semantic_reader_review source {stem} json",
                )
            )
        if not isinstance(md_ref, dict):
            failures.append(f"{chapter}: semantic_reader_review.json source {stem} missing markdown ref")
        else:
            failures.extend(
                validate_current_file_ref(
                    md_ref,
                    ROOT / "reviews" / chapter / f"{stem}.md",
                    f"{chapter}: semantic_reader_review source {stem} markdown",
                )
            )
    return failures


def validate_codex_anti_ai_review(chapter: str) -> list[str]:
    failures = validate_agent_anti_ai_review(chapter, "codex_anti_ai_review", "Codex")
    failures.extend(validate_codex_anti_ai_manifest(chapter))
    return failures


def validate_deepseek_anti_ai_review(chapter: str) -> list[str]:
    return validate_agent_anti_ai_review(chapter, "deepseek_anti_ai_review", "DeepSeek")


def validate_codex_semantic_reader_review(chapter: str) -> list[str]:
    failures = validate_agent_semantic_reader_review(chapter, "codex_semantic_reader_review", "Codex")
    failures.extend(validate_codex_semantic_reader_manifest(chapter))
    return failures


def validate_deepseek_semantic_reader_review(chapter: str) -> list[str]:
    return validate_agent_semantic_reader_review(chapter, "deepseek_semantic_reader_review", "DeepSeek")


def validate_deepseek_run_manifests(chapter: str) -> list[str]:
    failures: list[str] = []
    for kind in ("review", "anti_ai_review", "semantic_reader_review"):
        failures.extend(f"{chapter}: {item}" for item in validate_run_manifest(chapter, kind))
    return failures


def input_hash_failures(chapter: str, path: Path, data: dict, key: str = "input_hashes") -> list[str]:
    failures: list[str] = []
    values = data.get(key, [])
    if not isinstance(values, list):
        return [f"{chapter}: {path.name} {key} must be a list"]
    for item in values:
        if not isinstance(item, dict):
            failures.append(f"{chapter}: {path.name} {key} entry is malformed")
            continue
        rel_path = str(item.get("path", "")).strip()
        expected = str(item.get("sha256", "")).strip()
        if not rel_path or not expected:
            failures.append(f"{chapter}: {path.name} {key} entry missing path/sha256")
            continue
        source = ROOT / rel_path
        if not source.exists():
            failures.append(f"{chapter}: {path.name} input missing {rel_path}")
        elif sha256(source) != expected:
            failures.append(f"{chapter}: {path.name} input hash mismatch {rel_path}")
    return failures


def decision_value(chapter: str) -> str:
    data = read_json(ROOT / "reviews" / chapter / "decision.json", {})
    if isinstance(data, dict) and data.get("decision"):
        return str(data["decision"])
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return ""


def read_json_object(path: Path, chapter: str, label: str) -> tuple[dict, list[str]]:
    try:
        data = read_json(path, {})
    except Exception as exc:
        return {}, [f"{chapter}: {label} invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{chapter}: {label} must be a JSON object"]
    return data, []


def validate_revision_plan(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "revision_plan.json"
    if not path.exists():
        if decision_value(chapter) == "Revise once":
            return [f"{chapter}: Revise once requires current revision_plan.json"]
        return []
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: revision_plan.json must be a JSON object"]
    failures: list[str] = []
    official = data.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: revision_plan.json missing official_chapter")
    elif official_chapter_path(chapter).exists() and official.get("sha256") != sha256(official_chapter_path(chapter)):
        failures.append(f"{chapter}: revision_plan.json official chapter hash is stale")
    failures.extend(input_hash_failures(chapter, path, data))
    must_fix = data.get("must_fix")
    if not isinstance(must_fix, list):
        failures.append(f"{chapter}: revision_plan.json malformed must_fix")
    elif must_fix:
        failures.append(f"{chapter}: revision_plan.json still has must_fix items")
    for item in data.get("highlight_revisions", []) if isinstance(data.get("highlight_revisions"), list) else []:
        if not isinstance(item, dict):
            failures.append(f"{chapter}: revision_plan highlight_revisions item is malformed")
            continue
        action = str(item.get("action", "")).strip().lower()
        if action in {"delete", "remove", "flatten", "smooth", "rewrite_plain", "rewrite-flat"}:
            reason = str(item.get("human_override_reason", "")).strip()
            if not reason:
                failures.append(
                    f"{chapter}: revision_plan highlight {item.get('highlight_id', 'UNKNOWN')} "
                    "removal/flattening requires human_override_reason"
                )
    if data.get("status") != "READY":
        failures.append(f"{chapter}: revision_plan.json status must be READY before Ship")
    return failures


def validate_revision_closure(chapter: str) -> list[str]:
    report = evaluate_revision_closure(chapter)
    failures = [f"{chapter}: revision closure blocker: {item}" for item in report.get("blockers", []) if item]
    if str(report.get("status", "")).upper() != "READY":
        failures.append(f"{chapter}: revision closure status is {report.get('status') or 'MISSING'}")
    return failures


def validate_review_arbitration(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "review_arbitration.json"
    md_path = ROOT / "reviews" / chapter / "review_arbitration.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing review arbitration {md_path.relative_to(ROOT)}")
    elif status_value(read_text(md_path)) == "ACCEPTED_BY_HUMAN":
        if not accepted_by_human_is_current(read_text(md_path), md_path, official_chapter_path(chapter)):
            failures.append(f"{chapter}: review_arbitration.md human acceptance is missing or stale")
    if not path.exists():
        return failures + [f"{chapter}: missing review arbitration {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return failures + [f"{chapter}: review_arbitration.json must be a JSON object"]
    status = str(data.get("status", ""))
    accepted = status == "ACCEPTED_BY_HUMAN" or isinstance(data.get("human_acceptance"), dict)
    if accepted:
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    if status not in {"READY", "ACCEPTED_BY_HUMAN"} and not accepted:
        failures.append(f"{chapter}: review_arbitration.json status is {status or 'MISSING'}; expected READY or ACCEPTED_BY_HUMAN")
    if data.get("blockers") and not accepted:
        failures.extend(f"{chapter}: review_arbitration blocker: {item}" for item in data.get("blockers", []))
    failures.extend(input_hash_failures(chapter, path, data))
    return failures


def text_has_high_impact_gray(chapter: str) -> bool:
    text = read_text(official_chapter_path(chapter)).lower()
    gray = any(marker in text for marker in ("lie", "hide", "secret", "selfish", "betray", "私心", "隐瞒", "骗", "使坏"))
    impact = any(marker in text for marker in ("relationship", "trust", "rule", "ability", "关系", "信任", "规则", "人格", "破局"))
    return gray and impact


def validate_gray_consequence(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "gray_consequence.json"
    if not path.exists():
        return [f"{chapter}: high-impact gray behavior requires gray_consequence.json"] if text_has_high_impact_gray(chapter) else []
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: gray_consequence.json must be a JSON object"]
    official = data.get("official_chapter")
    failures: list[str] = []
    if not isinstance(official, dict):
        failures.append(f"{chapter}: gray_consequence.json missing official_chapter")
    elif official_chapter_path(chapter).exists() and official.get("sha256") != sha256(official_chapter_path(chapter)):
        failures.append(f"{chapter}: gray_consequence.json official chapter hash is stale")
    status = data.get("status")
    if status == "BLOCKED":
        failures.append(f"{chapter}: gray_consequence.json is BLOCKED")
    if text_has_high_impact_gray(chapter) and status != "READY":
        failures.append(f"{chapter}: high-impact gray behavior requires READY gray consequence evidence")
    return failures


def validate_chapter_shape(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "chapter_shape.json"
    if chapter_number(chapter) < 6 and not path.exists():
        return []
    if not path.exists():
        return [f"{chapter}: chapter 6+ requires chapter_shape.json"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: chapter_shape.json must be a JSON object"]
    official = data.get("official_chapter")
    failures: list[str] = []
    if isinstance(official, dict) and official_chapter_path(chapter).exists() and official.get("sha256") != sha256(official_chapter_path(chapter)):
        failures.append(f"{chapter}: chapter_shape.json official chapter hash is stale")
    status = data.get("status")
    if status == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, path, data))
    if chapter_number(chapter) >= 6 and status not in {"READY", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: chapter_shape.json status is {status or 'MISSING'}; expected READY or ACCEPTED_BY_HUMAN for chapter 6+")
    if status == "BLOCKED":
        failures.append(f"{chapter}: chapter_shape.json is BLOCKED")
    return failures


def validate_prose_risk(chapter: str) -> list[str]:
    json_path = ROOT / "reviews" / chapter / "prose_risk.json"
    md_path = ROOT / "reviews" / chapter / "prose_risk.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing prose risk review {md_path.relative_to(ROOT)}")
    else:
        md_text = read_text(md_path)
        md_status = status_value(md_text)
        if md_status not in {"CLEAR", "WARNING", "BLOCKED", "ACCEPTED_BY_HUMAN"}:
            failures.append(f"{chapter}: prose_risk.md status is {md_status or 'MISSING'}")
        if md_status in {"CLEAR", "WARNING", "BLOCKED"}:
            if not review_bound_to_current_chapter(md_text, official_chapter_path(chapter)):
                failures.append(f"{chapter}: prose_risk.md official chapter hash is missing or stale")
            if not review_hash_is_current(md_text, md_path):
                failures.append(f"{chapter}: prose_risk.md review_sha256 is missing or stale")
        if md_status == "ACCEPTED_BY_HUMAN" and not accepted_by_human_is_current(md_text, md_path, official_chapter_path(chapter)):
            failures.append(f"{chapter}: prose_risk.md human acceptance is missing or stale")
    if not json_path.exists():
        return failures + [f"{chapter}: missing prose risk review {json_path.relative_to(ROOT)}"]
    data, parse_failures = read_json_object(json_path, chapter, "prose_risk.json")
    if parse_failures:
        return failures + parse_failures
    failures.extend(validate_structured_official_binding(chapter, json_path, data))
    brief_ref = data.get("official_brief")
    failures.extend(validate_current_file_ref(brief_ref, ROOT / "outline" / "chapter_briefs" / f"{chapter}.md", f"{chapter}: prose_risk official_brief"))
    failures.extend(input_hash_failures(chapter, json_path, data))
    status = str(data.get("status", "")).strip().upper()
    if status not in {"CLEAR", "WARNING", "BLOCKED", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: prose_risk.json status is {status or 'MISSING'}")
    if status == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_structured_human_acceptance(chapter, json_path, data))
    if status == "BLOCKED":
        failures.append(f"{chapter}: prose_risk.json is BLOCKED")
    categories = data.get("categories")
    required = {
        "subject_repetition",
        "process_bloat",
        "protagonist_invulnerable",
        "flat_side_character",
        "homogeneous_hook",
        "qa_dialogue",
        "anomaly_density",
    }
    if not isinstance(categories, dict):
        failures.append(f"{chapter}: prose_risk.json missing categories")
    else:
        for key in sorted(required - set(categories)):
            failures.append(f"{chapter}: prose_risk.json missing category {key}")
        for key, item in categories.items():
            if not isinstance(item, dict):
                failures.append(f"{chapter}: prose_risk.json category {key} is malformed")
                continue
            for field in ("status", "severity", "issue", "evidence_quotes", "revision_actions", "human_acceptance_allowed"):
                if field not in item:
                    failures.append(f"{chapter}: prose_risk.json category {key} missing {field}")
            severity = str(item.get("severity", "")).upper()
            category_status = str(item.get("status", "")).upper()
            if status != "ACCEPTED_BY_HUMAN" and category_status == "BLOCKED":
                failures.append(f"{chapter}: prose_risk.json category {key} is BLOCKED")
            if status != "ACCEPTED_BY_HUMAN" and severity in {"P0", "P1"} and category_status != "CLEAR":
                failures.append(f"{chapter}: prose_risk.json category {key} has unresolved {severity}")
            if key == "anomaly_density" and category_status == "BLOCKED":
                failures.append(f"{chapter}: prose_risk anomaly_density cannot be accepted without authorization rewrite")
    quotes = collect_structured_quotes(data)
    if not quotes:
        failures.append(f"{chapter}: prose_risk.json has no evidence quotes")
    elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
        failures.append(f"{chapter}: prose_risk.json evidence quotes do not match the official chapter")
    return failures


def validate_prose_risk_index(chapter: str) -> list[str]:
    path = ROOT / "state" / "derived" / "prose_risk" / "latest.json"
    if not path.exists():
        return [f"{chapter}: missing prose risk index; run prose-risk-index --to {chapter} --write"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: prose risk index latest.json must be a JSON object"]
    failures: list[str] = []
    through = str(data.get("through", ""))
    try:
        through_number = chapter_number(through)
    except ValueError:
        through_number = -1
    if through[:3] != chapter[:3] or through_number < chapter_number(chapter):
        failures.append(f"{chapter}: prose risk index is stale; expected through {chapter} or later")
    status = str(data.get("status", "")).strip().upper()
    if status == "BLOCKED":
        failures.append(f"{chapter}: prose risk index is BLOCKED")
    elif status not in {"READY", "WARNING"}:
        failures.append(f"{chapter}: prose risk index status is {status or 'MISSING'}")
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers:
        failures.extend(f"{chapter}: prose risk blocker: {item}" for item in blockers[:10])
    failures.extend(
        validate_current_file_ref(
            data.get("source_event_ledger"),
            ROOT / "state" / "event_ledger.jsonl",
            f"{chapter}: prose risk source_event_ledger",
        )
    )
    for item in data.get("chapters", []):
        if not isinstance(item, dict):
            failures.append(f"{chapter}: prose risk index chapter entry is malformed")
            continue
        item_chapter = str(item.get("chapter", ""))
        if not item_chapter:
            continue
        try:
            if chapter_number(item_chapter) > chapter_number(chapter):
                continue
        except ValueError:
            continue
        failures.extend(
            validate_current_file_ref(
                item.get("prose_risk"),
                ROOT / "reviews" / item_chapter / "prose_risk.json",
                f"{chapter}: prose risk {item_chapter} prose_risk",
            )
        )
        if "chapter_shape" in item:
            failures.extend(
                validate_current_file_ref(
                    item.get("chapter_shape"),
                    ROOT / "reviews" / item_chapter / "chapter_shape.json",
                    f"{chapter}: prose risk {item_chapter} chapter_shape",
                )
            )
    return failures


def brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def validate_reader_reward_acceptance(chapter: str, path: Path, data: dict) -> list[str]:
    acceptance = data.get("human_acceptance")
    if not isinstance(acceptance, dict):
        return [f"{chapter}: reader_reward_gate.json human_acceptance is missing"]
    failures: list[str] = []
    for field in (
        "accepted_by",
        "accepted_at",
        "reason",
        "compensation_evidence_quote",
        "next_chapter_obligation",
        "official_chapter_sha256",
        "official_brief_sha256",
        "reader_promise_sha256",
        "policy_sha256",
        "review_sha256",
    ):
        if not str(acceptance.get(field, "")).strip():
            failures.append(f"{chapter}: reader_reward_gate.json human_acceptance.{field} is missing")
    if acceptance.get("accepted_by") != "human":
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance.accepted_by must be human")
    official = official_chapter_path(chapter)
    brief = brief_path(chapter)
    hashes = {item.get("path"): item.get("sha256") for item in data.get("input_hashes", []) if isinstance(item, dict)}
    if not official.exists() or acceptance.get("official_chapter_sha256") != sha256(official):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance official chapter hash is missing or stale")
    if not brief.exists() or acceptance.get("official_brief_sha256") != sha256(brief):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance official brief hash is missing or stale")
    if acceptance.get("reader_promise_sha256") != hashes.get("state/project_reader_promise.json"):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance reader promise hash is missing or stale")
    if acceptance.get("policy_sha256") != hashes.get("ops/reader_reward_policy.json"):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance policy hash is missing or stale")
    clean = dict(data)
    clean.pop("human_acceptance", None)
    clean.pop("status", None)
    review_hash = hashlib.sha256(
        json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if acceptance.get("review_sha256") != review_hash:
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance review hash is missing or stale")
    quote = str(acceptance.get("compensation_evidence_quote", "")).strip()
    if quote and official.exists() and not quote_matches_text(quote, read_text(official)):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance compensation evidence quote does not match official chapter")
    allowed_reason_markers = ("回报强度争议", "节奏策略争议", "慢热", "低动作")
    reason = str(acceptance.get("reason", ""))
    if reason and not any(marker in reason for marker in allowed_reason_markers):
        failures.append(f"{chapter}: reader_reward_gate.json human_acceptance reason is not an allowed reader reward exception")
    return failures


def validate_reader_reward_gate(chapter: str) -> list[str]:
    json_path = ROOT / "reviews" / chapter / "reader_reward_gate.json"
    md_path = ROOT / "reviews" / chapter / "reader_reward_gate.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing reader reward gate {md_path.relative_to(ROOT)}")
    if not json_path.exists():
        return failures + [f"{chapter}: missing reader reward gate {json_path.relative_to(ROOT)}"]
    data = read_json(json_path, {})
    if not isinstance(data, dict):
        return failures + [f"{chapter}: reader_reward_gate.json must be a JSON object"]
    official = data.get("official_chapter")
    if not isinstance(official, dict):
        failures.append(f"{chapter}: reader_reward_gate.json missing official_chapter")
    elif official_chapter_path(chapter).exists() and official.get("sha256") != sha256(official_chapter_path(chapter)):
        failures.append(f"{chapter}: reader_reward_gate.json official chapter hash is stale")
    brief = data.get("official_brief")
    if not isinstance(brief, dict):
        failures.append(f"{chapter}: reader_reward_gate.json missing official_brief")
    elif brief_path(chapter).exists() and brief.get("sha256") != sha256(brief_path(chapter)):
        failures.append(f"{chapter}: reader_reward_gate.json official brief hash is stale")
    failures.extend(input_hash_failures(chapter, json_path, data))
    status = data.get("status")
    if status == "BLOCKED":
        failures.append(f"{chapter}: reader_reward_gate.json is BLOCKED")
    if status not in {"READY", "WARNING", "ACCEPTED_BY_HUMAN", "BLOCKED"}:
        failures.append(f"{chapter}: reader_reward_gate.json status is {status or 'MISSING'}")
    if status == "ACCEPTED_BY_HUMAN":
        failures.extend(validate_reader_reward_acceptance(chapter, json_path, data))
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers and status != "ACCEPTED_BY_HUMAN":
        failures.extend(f"{chapter}: reader_reward_gate blocker: {item}" for item in blockers)
    intensity = str(data.get("reader_reward_intensity", "")).strip().upper()
    matched = data.get("matched_evidence_quotes")
    if intensity in {"R2", "R3", "R4"}:
        if not isinstance(matched, list) or not matched:
            failures.append(f"{chapter}: R2+ reader_reward_gate requires matched evidence quotes")
        elif not any_quote_matches_official([str(item) for item in matched], official_chapter_path(chapter)):
            failures.append(f"{chapter}: reader_reward_gate matched evidence quotes do not match official chapter")
    return failures


def validate_reader_reward_index(chapter: str) -> list[str]:
    path = ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json"
    if not path.exists():
        return [f"{chapter}: missing derived reader reward index {path.relative_to(ROOT)}"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: reader_reward_index.json must be a JSON object"]
    failures: list[str] = []
    for key, rel_path in (
        ("source_policy", "ops/reader_reward_policy.json"),
        ("source_reader_promise", "state/project_reader_promise.json"),
    ):
        item = data.get(key)
        source = ROOT / rel_path
        if not isinstance(item, dict) or item.get("path") != rel_path or not source.exists() or item.get("sha256") != sha256(source):
            failures.append(f"{chapter}: reader_reward_index.json {key} hash is missing or stale")
    entry = None
    for item in data.get("chapters", []):
        if isinstance(item, dict) and item.get("chapter") == chapter:
            entry = item
            break
    if not isinstance(entry, dict):
        return failures + [f"{chapter}: reader_reward_index.json missing current chapter entry"]
    gate = entry.get("gate")
    gate_path = ROOT / "reviews" / chapter / "reader_reward_gate.json"
    if not isinstance(gate, dict) or gate.get("path") != f"reviews/{chapter}/reader_reward_gate.json":
        failures.append(f"{chapter}: reader_reward_index.json gate reference is missing or wrong")
    elif gate_path.exists() and gate.get("sha256") != sha256(gate_path):
        failures.append(f"{chapter}: reader_reward_index.json gate hash is stale")
    cross_blockers = entry.get("cross_blockers")
    if isinstance(cross_blockers, list) and cross_blockers:
        gate_data = read_json(gate_path, {})
        accepted = isinstance(gate_data, dict) and gate_data.get("status") == "ACCEPTED_BY_HUMAN"
        acceptance = gate_data.get("human_acceptance") if isinstance(gate_data, dict) else None
        has_obligation = isinstance(acceptance, dict) and bool(str(acceptance.get("next_chapter_obligation", "")).strip())
        if not accepted or not has_obligation:
            failures.extend(f"{chapter}: reader reward cross-chapter blocker: {item}" for item in cross_blockers)
    return failures


def validate_reader_risk_index(chapter: str) -> list[str]:
    path = ROOT / "state" / "derived" / "reader_risk" / "latest.json"
    if not path.exists():
        return [f"{chapter}: missing reader risk index; run reader-risk-index --to {chapter} --write"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: reader risk index latest.json must be a JSON object"]
    failures: list[str] = []
    through = str(data.get("through", ""))
    try:
        through_number = chapter_number(through)
    except ValueError:
        through_number = -1
    if through[:3] != chapter[:3] or through_number < chapter_number(chapter):
        failures.append(f"{chapter}: reader risk index is stale; expected through {chapter} or later")
    status = str(data.get("status", "")).strip().upper()
    if status == "BLOCKED":
        failures.append(f"{chapter}: reader risk index is BLOCKED")
    elif status not in {"READY", "WARNING"}:
        failures.append(f"{chapter}: reader risk index status is {status or 'MISSING'}")
    blockers = data.get("blockers")
    if isinstance(blockers, list) and blockers:
        failures.extend(f"{chapter}: reader risk blocker: {item}" for item in blockers[:10])
    failures.extend(
        validate_current_file_ref(
            data.get("source_reader_promise"),
            ROOT / "state" / "project_reader_promise.json",
            f"{chapter}: reader risk source_reader_promise",
        )
    )
    failures.extend(
        validate_current_file_ref(
            data.get("source_event_ledger"),
            ROOT / "state" / "event_ledger.jsonl",
            f"{chapter}: reader risk source_event_ledger",
        )
    )
    for item in data.get("chapters", []):
        if not isinstance(item, dict):
            continue
        item_chapter = str(item.get("chapter", ""))
        if not item_chapter:
            continue
        try:
            if chapter_number(item_chapter) > chapter_number(chapter):
                continue
        except ValueError:
            continue
        failures.extend(
            validate_current_file_ref(
                item.get("reader_reward_gate"),
                ROOT / "reviews" / item_chapter / "reader_reward_gate.json",
                f"{chapter}: reader risk {item_chapter} reader_reward_gate",
            )
        )
        failures.extend(
            validate_current_file_ref(
                item.get("chapter_shape"),
                ROOT / "reviews" / item_chapter / "chapter_shape.json",
                f"{chapter}: reader risk {item_chapter} chapter_shape",
            )
        )
        failures.extend(
            validate_current_file_ref(
                item.get("reader_feedback"),
                ROOT / "reviews" / item_chapter / "reader_feedback.json",
                f"{chapter}: reader risk {item_chapter} reader_feedback",
            )
        )
    return failures


def validate_long_health(chapter: str) -> list[str]:
    if chapter_number(chapter) < 10:
        return []
    path = ROOT / "state" / "derived" / "long_health" / "latest.json"
    if not path.exists():
        return [f"{chapter}: chapter 10+ requires long_health latest report; run long-health --to {chapter} --write"]
    data = read_json(path, {})
    if not isinstance(data, dict):
        return [f"{chapter}: long_health latest.json must be a JSON object"]
    failures: list[str] = []
    through = str(data.get("through", ""))
    try:
        through_number = chapter_number(through)
    except ValueError:
        through_number = -1
    if through[:3] != chapter[:3] or through_number < chapter_number(chapter):
        failures.append(f"{chapter}: long_health latest.json is stale; expected through {chapter} or later in the same volume")
    status = str(data.get("status", "")).strip().upper()
    if status == "BLOCKED":
        failures.append(f"{chapter}: long_health is BLOCKED")
    elif status not in {"READY", "WARNING"}:
        failures.append(f"{chapter}: long_health status is {status or 'MISSING'}")
    blockers = data.get("rolling_blockers")
    if isinstance(blockers, list) and blockers:
        failures.extend(f"{chapter}: long_health blocker: {item}" for item in blockers)
    failures.extend(
        validate_current_file_ref(
            data.get("source_reader_promise"),
            ROOT / "state" / "project_reader_promise.json",
            f"{chapter}: long_health source_reader_promise",
        )
    )
    failures.extend(
        validate_current_file_ref(
            data.get("source_event_ledger"),
            ROOT / "state" / "event_ledger.jsonl",
            f"{chapter}: long_health source_event_ledger",
        )
    )
    for item in data.get("rolling_input_refs", []):
        if not isinstance(item, dict):
            continue
        item_chapter = str(item.get("chapter", ""))
        if not item_chapter:
            continue
        failures.extend(
            validate_current_file_ref(
                item.get("reader_reward_gate"),
                ROOT / "reviews" / item_chapter / "reader_reward_gate.json",
                f"{chapter}: long_health {item_chapter} reader_reward_gate",
            )
        )
        failures.extend(
            validate_current_file_ref(
                item.get("chapter_shape"),
                ROOT / "reviews" / item_chapter / "chapter_shape.json",
                f"{chapter}: long_health {item_chapter} chapter_shape",
            )
        )
    for item in data.get("context_health_window", []):
        if not isinstance(item, dict):
            failures.append(f"{chapter}: long_health context_health_window entry must be an object")
            continue
        item_chapter = str(item.get("chapter", ""))
        if not item_chapter:
            failures.append(f"{chapter}: long_health context_health_window entry missing chapter")
            continue
        failures.extend(
            validate_current_file_ref(
                item.get("context_quality"),
                ROOT / "state" / "derived" / "context_quality" / f"{item_chapter}.json",
                f"{chapter}: long_health {item_chapter} context_quality",
            )
        )
    return failures


def validate_auxiliary_review(chapter: str, name: str) -> list[str]:
    path = ROOT / "reviews" / chapter / name
    if not path.exists() or not read_text(path).strip():
        return [f"{chapter}: missing auxiliary review {path.relative_to(ROOT)}"]
    text = read_text(path)
    failures: list[str] = []
    if has_placeholder(path):
        failures.append(f"{chapter}: auxiliary review still has placeholders {path.relative_to(ROOT)}")
    status = status_value(text)
    if status not in ALLOWED_AUXILIARY_STATUS:
        failures.append(
            f"{chapter}: auxiliary review {name} status is {status or 'MISSING'}; "
            f"expected one of {sorted(ALLOWED_AUXILIARY_STATUS)}"
        )
    if status == "CLEAR" and not review_bound_to_current_chapter(text, official_chapter_path(chapter)):
        failures.append(f"{chapter}: auxiliary review {name} official chapter hash is missing or stale")
    if status == "CLEAR" and not review_hash_is_current(text, path):
        failures.append(f"{chapter}: auxiliary review {name} review_sha256 is missing or stale")
    if status == "CLEAR":
        quotes = evidence_quotes(text)
        if not quotes:
            failures.append(f"{chapter}: auxiliary review {name} has no Evidence Quotes")
        elif not any_quote_matches_official(quotes, official_chapter_path(chapter)):
            failures.append(f"{chapter}: auxiliary review {name} Evidence Quotes do not match the official chapter")
    if status == "ACCEPTED_BY_HUMAN" and not accepted_by_human_is_current(text, path, official_chapter_path(chapter)):
        failures.append(f"{chapter}: auxiliary review {name} human acceptance is missing or stale")
    if name == "originality.md":
        required_terms = ("撞梗", "换皮", "设定名词", "人物关系", "句式", "对白节奏", "标志性表达")
        for term in required_terms:
            if term not in text:
                failures.append(f"{chapter}: originality review missing risk term {term}")
    return failures


def load_ledger_events() -> list[dict]:
    path = ROOT / "state" / "event_ledger.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_cards(report: dict) -> list[dict]:
    cards = report.get("cards", [])
    if not isinstance(cards, list):
        return []
    normalized = []
    for item in cards:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": str(item.get("id", "")),
                "type": str(item.get("type", "")),
                "importance": str(item.get("importance", "")),
                "fact": str(item.get("fact", "")),
                "evidence_quote": str(item.get("evidence_quote", "")),
                "consequence": str(item.get("consequence", "")),
                "tags": [str(tag) for tag in item.get("tags", []) if str(tag).strip()],
            }
        )
    return normalized


def validate_fact_cards(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "fact_cards.json"
    if not path.exists():
        return [f"{chapter}: missing fact card evidence reviews/{chapter}/fact_cards.json"]
    recorded = read_json(path, {})
    failures: list[str] = []
    try:
        current = evaluate_fact_cards(chapter)
    except (FileNotFoundError, ValueError) as exc:
        return [f"{chapter}: fact cards cannot be evaluated: {exc}"]

    if recorded.get("chapter") != chapter:
        failures.append(f"{chapter}: fact card report chapter mismatch")
    if recorded.get("source_hashes") != current.get("source_hashes"):
        failures.append(f"{chapter}: fact card report is stale; regenerate with `python scripts/novel.py fact-cards {chapter} --write`")
    if normalized_cards(recorded) != normalized_cards(current):
        failures.append(f"{chapter}: fact card report cards are stale or malformed")

    accepted_card_ids: set[str] = set()
    card_by_id = {card["id"]: card for card in normalized_cards(current)}
    for event in load_ledger_events():
        if event.get("chapter") != chapter or event.get("verified_by") != "human":
            continue
        tags = {str(tag) for tag in event.get("tags", []) if str(tag).strip()}
        for card_id, card in card_by_id.items():
            if card_id in tags and event.get("type") == card.get("type"):
                accepted_card_ids.add(card_id)
    if not accepted_card_ids:
        failures.append(
            f"{chapter}: Ship requires at least one accepted fact card in state/event_ledger.jsonl "
            "(use `python scripts/novel.py accept-fact-card ...`)"
        )
    return failures


def validate_human_flavor_json(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "human_flavor.json"
    if not path.exists():
        return [f"{chapter}: missing human flavor review {path.relative_to(ROOT)}"]
    data, parse_failures = read_json_object(path, chapter, "human_flavor.json")
    if parse_failures:
        return parse_failures
    failures: list[str] = []
    status = data.get("status")
    if status not in {"CLEAR", "WARNING", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: human_flavor.json status is {status or 'MISSING'}")
    failures.extend(validate_current_file_ref(data.get("official_chapter"), official_chapter_path(chapter), f"{chapter}: human_flavor official_chapter"))
    failures.extend(validate_current_file_ref(data.get("official_brief"), ROOT / "outline" / "chapter_briefs" / f"{chapter}.md", f"{chapter}: human_flavor official_brief"))
    failures.extend(input_hash_failures(chapter, path, data))
    quotes = data.get("evidence_quotes")
    if isinstance(quotes, list) and quotes and not any_quote_matches_official([str(item) for item in quotes], official_chapter_path(chapter)):
        failures.append(f"{chapter}: human_flavor evidence quotes do not match official chapter")
    window = data.get("window") if isinstance(data.get("window"), dict) else {}
    if status != "ACCEPTED_BY_HUMAN":
        try:
            missing_cost_window = int(window.get("last_3_missing_cost_or_misjudgment", 0) or 0)
        except (TypeError, ValueError):
            missing_cost_window = 0
        try:
            warning_window = int(window.get("last_5_human_flavor_warnings", 0) or 0)
        except (TypeError, ValueError):
            warning_window = 0
        if missing_cost_window >= 3:
            failures.append(f"{chapter}: human_flavor 3-chapter window requires forced revision before Ship")
        if warning_window >= 5:
            failures.append(f"{chapter}: human_flavor 5-chapter warning window requires Gate or long_health review before Ship")
    return failures


def validate_highlights_review_json(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "highlights_review.json"
    if not path.exists():
        return [f"{chapter}: missing highlights review {path.relative_to(ROOT)}"]
    data, parse_failures = read_json_object(path, chapter, "highlights_review.json")
    if parse_failures:
        return parse_failures
    failures: list[str] = []
    status = data.get("status")
    if status not in {"CLEAR", "WARNING", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: highlights_review.json status is {status or 'MISSING'}")
    failures.extend(validate_current_file_ref(data.get("official_chapter"), official_chapter_path(chapter), f"{chapter}: highlights_review official_chapter"))
    failures.extend(input_hash_failures(chapter, path, data))
    highlights = data.get("protected_highlights")
    if highlights is None or highlights == []:
        return failures
    if not isinstance(highlights, list):
        failures.append(f"{chapter}: highlights_review.json protected_highlights must be a list")
        return failures
    official_text = read_text(official_chapter_path(chapter))
    for item in highlights:
        if not isinstance(item, dict):
            failures.append(f"{chapter}: highlights_review contains malformed highlight")
            continue
        highlight_id = str(item.get("highlight_id", "")).strip()
        quote = str(item.get("quote", "")).strip()
        if not highlight_id:
            failures.append(f"{chapter}: highlights_review highlight missing highlight_id")
        if not quote:
            failures.append(f"{chapter}: highlights_review {highlight_id or 'highlight'} missing quote")
        elif not quote_matches_text(quote, official_text):
            failures.append(f"{chapter}: highlights_review {highlight_id or 'highlight'} quote does not match official chapter")
        if item.get("protection_level") != "preserve_or_human_reason":
            failures.append(f"{chapter}: highlights_review {highlight_id or 'highlight'} protection_level must be preserve_or_human_reason")
    return failures


def labeled_value(body: str, key: str) -> str:
    for raw in body.splitlines():
        line = raw.strip().lstrip("-*+ ").strip()
        if not line:
            continue
        if ":" in line:
            label, value = line.split(":", 1)
        elif "：" in line:
            label, value = line.split("：", 1)
        else:
            continue
        if label.strip() == key:
            return value.strip()
    return ""


def validate_end_state_change(chapter: str) -> list[str]:
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    sections = markdown_sections(read_text(brief_path))
    body = section_body(sections, END_STATE_CHANGE_SECTIONS)
    if not body:
        return []
    affected = labeled_value(body, "affected_thread")
    if not affected or "P0" not in body and "P1" not in body:
        return []
    events = [
        event
        for event in load_ledger_events()
        if event.get("chapter") == chapter
        and event.get("type") in {"thread_opened", "thread_advanced", "thread_paid_off"}
    ]
    for event in events:
        values = {
            str(event.get("thread_id", "")),
            str(event.get("fact", "")),
            *(str(item) for item in event.get("tags", []) if str(item).strip()),
            *(str(item) for item in event.get("entities", []) if str(item).strip()),
        }
        if affected in values or any(affected and affected in value for value in values):
            return []
    return [f"{chapter}: 章末状态变化 declares P0/P1 thread {affected!r} but event ledger has no thread ledger entry"]


def validate_progress_contract(chapter: str) -> list[str]:
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    sections = markdown_sections(read_text(brief_path))
    failures: list[str] = []
    for aliases in (
        PROGRESS_CONTRACT_SECTIONS,
        COST_CONSEQUENCE_CONTRACT_SECTIONS,
        RESOLUTION_BOUNDARY_SECTIONS,
    ):
        if missing_section(sections, aliases):
            failures.append(f"{chapter}: official brief missing progress evidence section {aliases[0]}")
    if failures:
        return failures

    progress = section_body(sections, PROGRESS_CONTRACT_SECTIONS)
    cost = section_body(sections, COST_CONSEQUENCE_CONTRACT_SECTIONS)
    boundary = section_body(sections, RESOLUTION_BOUNDARY_SECTIONS)
    minimum_event = progress_value(progress, "minimum_ledger_event").strip()
    if minimum_event not in LEDGER_EVENT_TYPES:
        failures.append(f"{chapter}: progress contract has invalid minimum ledger event {minimum_event or 'MISSING'}")
        return failures

    chapter_events = [event for event in load_ledger_events() if event.get("chapter") == chapter]
    if not any(event.get("type") == minimum_event for event in chapter_events):
        failures.append(f"{chapter}: progress contract minimum ledger event not found: {minimum_event}")

    resolved_threads = progress_value(boundary, "resolved_threads")
    if not is_none_body(resolved_threads) and not any(event.get("type") == "thread_paid_off" for event in chapter_events):
        failures.append(f"{chapter}: resolved_threads requires a thread_paid_off event in event ledger")

    impact_scale = normalized_impact_scale(progress_value(cost, "impact_scale"))
    progress_mode = normalized_progress_mode(progress_value(progress, "progress_mode"))
    requires_aftermath_record = (
        impact_scale in HIGH_IMPACT_SCALES
        or progress_mode == "payoff"
        or not is_none_body(resolved_threads)
    )
    if requires_aftermath_record and concrete_value(progress_value(cost, "aftermath_obligation")):
        obligations = read_json(ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json", {})
        derived_has_obligation = any(
            isinstance(item, dict) and item.get("source_chapter") == chapter
            for item in obligations.get("obligations", [])
        )
        anchor_has_continuity = any(
            event.get("type") == "chapter_anchor"
            and isinstance(event.get("anchor"), dict)
            and str(event["anchor"].get("next_required_continuity", "")).strip()
            for event in chapter_events
        )
        if not derived_has_obligation and not anchor_has_continuity:
            failures.append(f"{chapter}: high progress aftermath obligation is not recorded in derived pacing or chapter anchor")

    return failures


def always_required_ship_gate_failures(chapter: str) -> list[str]:
    failures: list[str] = []
    failures.extend(personal_mode_runtime_failures())
    selection = read_json(ROOT / "state" / "selections" / f"{chapter}.json", {})
    landing = read_json(ROOT / "reviews" / chapter / "chapter_landing.json", {})

    validators = {
        "candidate_selection": lambda: validate_selection(chapter),
        "official_chapter_landing": lambda: validate_landing(chapter),
        "candidate_prompt_provenance": lambda: validate_candidate_prompt_evidence(chapter, selection, landing),
        "context_quality": lambda: validate_context_quality(chapter, landing),
        "shadow_memory": lambda: [f"{chapter}: shadow memory {item}" for item in evaluate_shadow(chapter).get("blockers", [])],
        "review_context": lambda: validate_review_context(chapter),
        "authorized_breakers": lambda: validate_authorized_breakers(chapter),
        "element_usage": lambda: validate_element_usage(chapter),
        "deepseek_direct_adoption_provenance": lambda: validate_deepseek_direct_adoption(chapter, selection, landing),
        "progress_contract_ledger": lambda: validate_progress_contract(chapter),
        "fact_cards": lambda: validate_fact_cards(chapter),
        "end_state_change": lambda: validate_end_state_change(chapter),
        "continuity_p0_p1": lambda: validate_continuity(chapter),
    }
    configured = set(always_required_ship_gates())
    expected = set(validators)
    for name in sorted(configured - expected):
        failures.append(f"{chapter}: unknown always-required Ship gate in review_routing.yaml: {name}")
    for name in sorted(expected - configured):
        failures.append(f"{chapter}: review_routing.yaml missing always-required Ship gate: {name}")
    for name, validator in validators.items():
        failures.extend(validator())

    if continuity_has_blocker(chapter):
        failures.append(f"{chapter}: continuity report has unresolved P0/P1")

    return failures


def heavyweight_review_failures(chapter: str, *, include_revision_closure: bool = True) -> list[str]:
    failures: list[str] = []
    required_reviews = [
        "codex_integrated_review.md",
        "deepseek_integrated_review.md",
        "model_disagreement.md",
        "continuity.md",
    ]
    for name in required_reviews:
        path = ROOT / "reviews" / chapter / name
        if not path.exists() or not read_text(path).strip():
            failures.append(f"{chapter}: missing review artifact {path.relative_to(ROOT)}")
            continue
        if name in {"codex_integrated_review.md", "deepseek_integrated_review.md"} and has_placeholder(path):
            failures.append(f"{chapter}: review artifact still has placeholders {path.relative_to(ROOT)}")

    manifest = read_json(ROOT / "reviews" / chapter / "review_manifest.json", {})
    failures.extend(validate_manifest_entry(chapter, "codex", manifest))
    failures.extend(validate_manifest_entry(chapter, "deepseek", manifest))
    failures.extend(validate_model_disagreement(chapter))
    failures.extend(validate_deepseek_run_manifests(chapter))
    failures.extend(validate_review_arbitration(chapter))
    if include_revision_closure:
        failures.extend(validate_revision_plan(chapter))
        failures.extend(validate_revision_closure(chapter))
    return failures


def validate_integrated_review_file(chapter: str, name: str) -> list[str]:
    path = ROOT / "reviews" / chapter / name
    if not path.exists() or not read_text(path).strip():
        return [f"{chapter}: missing review artifact {path.relative_to(ROOT)}"]
    if has_placeholder(path):
        return [f"{chapter}: review artifact still has placeholders {path.relative_to(ROOT)}"]
    return []


def validate_reader_reward_suite(chapter: str) -> list[str]:
    failures: list[str] = []
    failures.extend(validate_reader_reward_gate(chapter))
    failures.extend(validate_reader_reward_index(chapter))
    return failures


def validate_reader_risk_suite(chapter: str) -> list[str]:
    failures: list[str] = []
    failures.extend(validate_reader_risk_index(chapter))
    return failures


def literary_review_failures(
    chapter: str,
    route: str,
    *,
    route_data: dict | None = None,
    include_revision_closure: bool = True,
) -> list[str]:
    failures: list[str] = []
    validators = {
        "human_flavor": lambda: validate_human_flavor_json(chapter),
        "highlights": lambda: validate_highlights_review_json(chapter),
        "style_voice": lambda: validate_style_check(chapter) + validate_series_style_check(chapter),
        "ai_taste": lambda: validate_ai_taste_json(chapter),
        "dialogue_function": lambda: validate_dialogue_function_json(chapter),
        "emotion_relationship": lambda: validate_auxiliary_review(chapter, "emotion_relationship_gate.md"),
        "memorable_scene": lambda: validate_auxiliary_review(chapter, "memorable_scene.md"),
        "prose_risk": lambda: validate_prose_risk(chapter) + validate_prose_risk_index(chapter),
        "reader_reward": lambda: validate_reader_reward_suite(chapter),
        "reader_risk": lambda: validate_reader_risk_suite(chapter),
        "codex_integrated": lambda: validate_integrated_review_file(chapter, "codex_integrated_review.md"),
        "deepseek_integrated": lambda: validate_integrated_review_file(chapter, "deepseek_integrated_review.md"),
        "codex_anti_ai": lambda: validate_codex_anti_ai_review(chapter),
        "deepseek_anti_ai": lambda: validate_deepseek_anti_ai_review(chapter),
        "codex_semantic": lambda: validate_codex_semantic_reader_review(chapter),
        "deepseek_semantic": lambda: validate_deepseek_semantic_reader_review(chapter),
        "semantic_reader": lambda: validate_semantic_reader_review(chapter),
        "review_arbitration": lambda: validate_review_arbitration(chapter),
        "revision_plan": lambda: validate_revision_plan(chapter) + (validate_revision_closure(chapter) if include_revision_closure else []),
        "series_style": lambda: validate_series_style_check(chapter),
        "long_health": lambda: validate_long_health(chapter),
    }

    configured_reviews: list[str]
    route_path = ROOT / "reviews" / chapter / "review_route.json"
    if route_data is None:
        if route_path.exists():
            try:
                route_data = read_json(route_path, {})
            except Exception as exc:
                route_data = {}
                failures.append(f"{chapter}: review_route.json invalid JSON: {exc}")
        else:
            route_data = {}
    if isinstance(route_data, dict) and isinstance(route_data.get("additional_literary_reviews"), list):
        configured_reviews = [str(item) for item in route_data["additional_literary_reviews"]]
    else:
        # Fail-closed fallback: no route artifact means legacy HEAVY behavior.
        configured_reviews = [
            "style_voice",
            "ai_taste",
            "dialogue_function",
            "emotion_relationship",
            "memorable_scene",
            "prose_risk",
            "reader_reward",
            "reader_risk",
            "codex_anti_ai",
            "deepseek_anti_ai",
            "codex_semantic",
            "deepseek_semantic",
            "semantic_reader",
            "review_arbitration",
            "revision_plan",
            "series_style",
            "long_health",
        ]
    for name in configured_reviews:
        validator = validators.get(name)
        if validator is None:
            failures.append(f"{chapter}: unknown routed literary review {name}")
            continue
        failures.extend(validator())

    if route in {"heavy", "gate"} or not route_path.exists():
        failures.extend(heavyweight_review_failures(chapter, include_revision_closure=include_revision_closure))

    review_names = list(AUXILIARY_REVIEWS)
    for name in required_reviews_for_chapter(chapter):
        if name not in review_names:
            review_names.append(name)
    if route in {"heavy", "gate"} or not route_path.exists():
        for name in review_names:
            failures.extend(validate_auxiliary_review(chapter, name))
        failures.extend(validate_gray_consequence(chapter))
        failures.extend(validate_chapter_shape(chapter))

    return failures


def validate_receive_chapter_report(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "receive_chapter.json"
    if not path.exists():
        return [f"{chapter}: missing receive control-plane report {path.relative_to(ROOT)}"]
    data, parse_failures = read_json_object(path, chapter, "receive_chapter.json")
    if parse_failures:
        return parse_failures
    failures: list[str] = []
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: receive_chapter.json chapter mismatch")
    if data.get("status") != "READY":
        failures.append(f"{chapter}: receive_chapter.json status is {data.get('status', 'MISSING')}")
    input_hashes = data.get("input_hashes")
    if not isinstance(input_hashes, list) or not input_hashes:
        failures.append(f"{chapter}: receive_chapter.json missing input_hashes")
        input_hashes = []
    required_paths = {
        official_chapter_path(chapter).relative_to(ROOT).as_posix(),
        f"outline/chapter_briefs/{chapter}.md",
        f"state/context_pack/{chapter}.manifest.json",
        "state/event_ledger.jsonl",
        f"reviews/{chapter}/review_route.json",
    }
    seen_paths: set[str] = set()
    for index, item in enumerate(input_hashes, start=1):
        label = f"{chapter}: receive_chapter input_hashes[{index}]"
        if not isinstance(item, dict):
            failures.append(f"{label} must be a file reference")
            continue
        rel_path = str(item.get("path", "")).strip()
        if rel_path:
            seen_paths.add(rel_path)
        failures.extend(validate_current_file_ref(item, ROOT / rel_path, label) if rel_path else [f"{label} missing path"])
    missing = sorted(required_paths - seen_paths)
    if missing:
        failures.append(f"{chapter}: receive_chapter.json missing required input refs: {', '.join(missing)}")
    return failures


def chapter_evidence_failures(
    chapter: str,
    *,
    include_revision_closure: bool = True,
    require_receive: bool = False,
) -> list[str]:
    failures: list[str] = []
    route, route_failures, route_data = route_artifact_status(chapter)
    failures.extend(route_failures)
    failures.extend(always_required_ship_gate_failures(chapter))
    failures.extend(
        literary_review_failures(
            chapter,
            route,
            route_data=route_data,
            include_revision_closure=include_revision_closure,
        )
    )
    if require_receive:
        failures.extend(validate_receive_chapter_report(chapter))

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check per-chapter evidence before Ship close.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--require-receive", action="store_true", help="Require a current READY receive_chapter.json control-plane report.")
    args = parser.parse_args()

    failures = chapter_evidence_failures(args.chapter, require_receive=args.require_receive)
    print(f"# Chapter Evidence: {args.chapter}")
    print()
    if failures:
        print("status: NOT_READY")
        print()
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
