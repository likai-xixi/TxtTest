from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import ROOT, chapter_parts, read_json, read_text
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
from context_governance import context_manifest_path, context_quality_path
from element_context import markdown_sections, missing_section, section_body
from element_usage import evaluate as evaluate_element_usage
from fact_cards import evaluate as evaluate_fact_cards


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
    "web_satisfaction.md",
    "retention_risk.md",
    "originality.md",
    "similarity_risk.md",
)
ALLOWED_AUXILIARY_STATUS = {"CLEAR", "ACCEPTED_BY_HUMAN"}
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
        f"chapters/{volume}/{chapter_file}",
    }
    allowed = {
        f"state/context_pack/{chapter}.md",
        f"chapters/{volume}/{chapter_file}",
        f"drafts/codex/{chapter}.md",
        f"drafts/deepseek/{chapter}.md",
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


def chapter_evidence_failures(chapter: str) -> list[str]:
    failures: list[str] = []
    selection = read_json(ROOT / "state" / "selections" / f"{chapter}.json", {})
    landing = read_json(ROOT / "reviews" / chapter / "chapter_landing.json", {})

    failures.extend(validate_selection(chapter))
    failures.extend(validate_landing(chapter))
    failures.extend(validate_context_quality(chapter, landing))
    failures.extend(validate_authorized_breakers(chapter))
    failures.extend(validate_element_usage(chapter))
    failures.extend(validate_deepseek_direct_adoption(chapter, selection, landing))
    failures.extend(validate_progress_contract(chapter))
    failures.extend(validate_fact_cards(chapter))
    failures.extend(validate_end_state_change(chapter))

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
    failures.extend(validate_continuity(chapter))
    for name in AUXILIARY_REVIEWS:
        failures.extend(validate_auxiliary_review(chapter, name))

    if continuity_has_blocker(chapter):
        failures.append(f"{chapter}: continuity report has unresolved P0/P1")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check per-chapter evidence before Ship close.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    failures = chapter_evidence_failures(args.chapter)
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
