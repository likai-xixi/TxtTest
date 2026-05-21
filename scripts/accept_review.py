from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256
from review_binding import markdown_review_with_hash, metadata_value, review_body_sha256


ARTIFACTS: dict[str, tuple[str | None, str | None]] = {
    "ai_taste": ("ai_taste.md", "ai_taste.json"),
    "dialogue_function": ("dialogue_function.md", "dialogue_function.json"),
    "codex_anti_ai_review": ("codex_anti_ai_review.md", "codex_anti_ai_review.json"),
    "deepseek_anti_ai_review": ("deepseek_anti_ai_review.md", "deepseek_anti_ai_review.json"),
    "series_style": ("series_style.md", "series_style.json"),
    "chapter_shape": ("chapter_shape.md", "chapter_shape.json"),
    "reader_feedback": ("reader_feedback.md", "reader_feedback.json"),
    "review_arbitration": ("review_arbitration.md", "review_arbitration.json"),
}
INFRA_MARKERS = (
    "hash mismatch",
    "official chapter hash is missing",
    "review_sha256 is missing",
    "schema",
    "manifest",
    "evidence quotes do not match",
    "quote not found",
    "event ledger",
    "continuity P0",
    "continuity P1",
    "unauthorized",
    "context manifest",
)


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def json_review_body_hash(data: dict[str, Any]) -> str:
    clean = dict(data)
    clean.pop("human_acceptance", None)
    clean.pop("accepted_by", None)
    clean.pop("accepted_at", None)
    clean.pop("reason", None)
    clean.pop("review_sha256", None)
    body = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib

    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def has_p0_p1(value: Any) -> bool:
    if isinstance(value, dict):
        severity = str(value.get("severity", "")).upper()
        status = str(value.get("status", "")).upper()
        if severity in {"P0", "P1"} and status in {"BLOCKED", "NOT_READY"}:
            return True
        return any(has_p0_p1(item) for item in value.values())
    if isinstance(value, list):
        return any(has_p0_p1(item) for item in value)
    if isinstance(value, str):
        return bool(re.search(r"\bP[01]\b", value) and re.search(r"BLOCKED|NOT_READY|Rewrite brief|Kill chapter|Pause project", value, re.I))
    return False


def validate_acceptance_target(chapter: str, md_path: Path | None, json_path: Path | None) -> list[str]:
    failures: list[str] = []
    official = official_path(chapter)
    if not official.exists() or not read_text(official).strip():
        return [f"missing official chapter: {rel(official)}"]
    if md_path and md_path.exists():
        text = read_text(md_path)
        lowered = text.lower()
        for marker in INFRA_MARKERS:
            if marker.lower() in lowered:
                failures.append(f"{rel(md_path)} contains non-acceptable infrastructure marker: {marker}")
        if re.search(r"\bP[01]\b", text) and re.search(r"BLOCKED|Rewrite brief|Kill chapter|Pause project", text, re.I):
            failures.append(f"{rel(md_path)} contains unresolved P0/P1 or blocking action")
    if json_path and json_path.exists():
        data = read_json(json_path, {})
        if not isinstance(data, dict):
            failures.append(f"{rel(json_path)} must be a JSON object")
        elif has_p0_p1(data):
            failures.append(f"{rel(json_path)} contains unresolved P0/P1 blocker")
    return failures


def update_markdown(chapter: str, path: Path, reason: str) -> None:
    official = official_path(chapter)
    text = read_text(path)
    if not text.strip():
        text = f"# Accepted Review: {chapter}\n\nstatus: ACCEPTED_BY_HUMAN\nofficial_chapter_sha256:\nreview_sha256:\n\n"
    if re.search(r"^status\s*[:：]", text, flags=re.M):
        text = re.sub(r"^status\s*[:：].*$", "status: ACCEPTED_BY_HUMAN", text, flags=re.M)
    else:
        text = "status: ACCEPTED_BY_HUMAN\n" + text
    fields = {
        "accepted_at": now_iso(),
        "accepted_by": "human",
        "reason": reason,
        "official_chapter_sha256": sha256(official),
    }
    for key, value in fields.items():
        if re.search(rf"^{re.escape(key)}\s*[:：]", text, flags=re.M):
            text = re.sub(rf"^{re.escape(key)}\s*[:：].*$", f"{key}: {value}", text, flags=re.M)
        else:
            text = text.replace("\n", f"\n{key}: {value}\n", 1)
    if "review_sha256:" not in text:
        text = text.replace("official_chapter_sha256:", "official_chapter_sha256:\nreview_sha256:", 1)
    write_text(path, markdown_review_with_hash(text))


def update_json(chapter: str, path: Path, reason: str) -> None:
    data = read_json(path, {})
    if not isinstance(data, dict):
        data = {"schema_version": 1, "chapter": chapter}
    official = official_path(chapter)
    data["status"] = "ACCEPTED_BY_HUMAN"
    acceptance = {
        "accepted_by": "human",
        "accepted_at": now_iso(),
        "reason": reason,
        "official_chapter_sha256": sha256(official),
        "review_sha256": json_review_body_hash(data),
    }
    data["human_acceptance"] = acceptance
    write_json(path, data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a human acceptance for a taste/style review artifact.")
    parser.add_argument("chapter")
    parser.add_argument("--artifact", required=True, choices=sorted(ARTIFACTS))
    parser.add_argument("--reason", required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    if not args.reason.strip():
        print("ERROR: --reason is required and must not be empty.", file=sys.stderr)
        return 1
    md_name, json_name = ARTIFACTS[args.artifact]
    review_dir = ROOT / "reviews" / args.chapter
    md_path = review_dir / md_name if md_name else None
    json_path = review_dir / json_name if json_name else None
    if (md_path is None or not md_path.exists()) and (json_path is None or not json_path.exists()):
        print(f"ERROR: missing review artifact for {args.artifact}", file=sys.stderr)
        return 1
    failures = validate_acceptance_target(args.chapter, md_path, json_path)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    if args.preview:
        print(f"would_accept: {args.artifact}")
        if md_path and md_path.exists():
            print(f"would_write: {rel(md_path)}")
        if json_path and json_path.exists():
            print(f"would_write: {rel(json_path)}")
        return 0
    if md_path and md_path.exists():
        update_markdown(args.chapter, md_path, args.reason.strip())
    if json_path and json_path.exists():
        update_json(args.chapter, json_path, args.reason.strip())
    print(f"OK: accepted {args.artifact} for {args.chapter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
