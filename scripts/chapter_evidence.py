from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import ROOT, chapter_parts, read_json, read_text


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
)
ALLOWED_AUXILIARY_STATUS = {"CLEAR", "ACCEPTED_BY_HUMAN"}


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


def validate_no_direct_deepseek_copy(chapter: str, selection: dict) -> list[str]:
    volume, chapter_file = chapter_parts(chapter)
    official = ROOT / "chapters" / volume / chapter_file
    if not official.exists():
        return []
    official_hash = sha256(official)
    official_normalized = normalized_text(official)
    failures: list[str] = []
    for candidate in selected_deepseek_candidates(selection):
        if not candidate.exists():
            continue
        if official_hash == sha256(candidate):
            failures.append(f"{chapter}: official chapter matches selected DeepSeek candidate hash {candidate.relative_to(ROOT)}")
        elif official_normalized and official_normalized == normalized_text(candidate):
            failures.append(
                f"{chapter}: official chapter matches selected DeepSeek candidate after whitespace normalization {candidate.relative_to(ROOT)}"
            )
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
        f"outline/chapter_briefs/{chapter}.md",
    }

    if record.get("chapter") != chapter:
        failures.append(f"{chapter}: landing record chapter mismatch")
    selected_direction = record.get("selected_direction", record.get("source"))
    if selected_direction not in {"Codex", "DeepSeek", "Mixed"}:
        failures.append(f"{chapter}: landing record has invalid selected_direction")
    if "selected_direction" in record and record.get("integrated_by") != "Codex":
        failures.append(f"{chapter}: landing record must have integrated_by Codex")
    if not str(record.get("attestation", "")).strip():
        failures.append(f"{chapter}: landing record missing attestation")
    if record.get("codex_integrated") is not True:
        failures.append(f"{chapter}: landing record must confirm codex_integrated")
    if record.get("not_direct_deepseek_copy") is not True:
        failures.append(f"{chapter}: landing record must confirm not_direct_deepseek_copy")

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


def chapter_evidence_failures(chapter: str) -> list[str]:
    failures: list[str] = []
    selection = read_json(ROOT / "state" / "selections" / f"{chapter}.json", {})

    failures.extend(validate_selection(chapter))
    failures.extend(validate_landing(chapter))
    failures.extend(validate_no_direct_deepseek_copy(chapter, selection))

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
