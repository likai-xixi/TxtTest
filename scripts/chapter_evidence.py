from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from _common import ROOT, chapter_parts, read_json, read_text


PLACEHOLDERS = ("待定", "待评", "待生成", "待人类裁决", "TODO", "待填")
CHOICES = {"Codex", "DeepSeek", "Mixed", "Rewrite brief", "No usable candidate"}


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
    if record.get("source") not in {"Codex", "DeepSeek", "Mixed"}:
        failures.append(f"{chapter}: landing record has invalid source")
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
    required = [
        "## 双方一致的问题",
        "## Codex 独有问题",
        "## DeepSeek 独有问题",
        "## 冲突判断",
        "## 需要人类裁决事项",
        "## 建议动作",
    ]
    for heading in required:
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


def chapter_evidence_failures(chapter: str) -> list[str]:
    failures: list[str] = []

    failures.extend(validate_selection(chapter))
    failures.extend(validate_landing(chapter))

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
