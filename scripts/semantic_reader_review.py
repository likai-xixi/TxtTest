from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from review_binding import (
    any_quote_matches_official,
    official_chapter_path,
    markdown_review_with_hash,
    sha256,
    validate_markdown_review_binding,
)


CATEGORIES = (
    "process_record_voice",
    "sermon_or_author_voice",
    "tool_character_risk",
    "information_without_drama",
)
SOURCE_STEMS = (
    ("codex_semantic_reader_review", "Codex semantic reader review"),
    ("deepseek_semantic_reader_review", "DeepSeek semantic reader review"),
)
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def collect_structured_quotes(data: dict[str, Any]) -> list[str]:
    quotes: list[str] = []
    categories = data.get("categories")
    if isinstance(categories, dict):
        for item in categories.values():
            if isinstance(item, dict):
                quotes.extend(as_list(item.get("evidence_quotes")))
    for sample_key in ("scene_samples", "dialogue_samples", "samples"):
        samples = data.get(sample_key)
        if isinstance(samples, list):
            for sample in samples:
                if isinstance(sample, dict):
                    quote = str(sample.get("evidence_quote", "")).strip()
                    if quote:
                        quotes.append(quote)
    return list(dict.fromkeys(quotes))


def validate_source(chapter: str, stem: str, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    review_dir = ROOT / "reviews" / chapter
    json_path = review_dir / f"{stem}.json"
    md_path = review_dir / f"{stem}.md"
    failures: list[str] = []
    if not md_path.exists() or not read_text(md_path).strip():
        failures.append(f"{chapter}: missing {label} Markdown {rel(md_path)}")
    else:
        failures.extend(validate_markdown_review_binding(chapter=chapter, review_path=md_path))
    if not json_path.exists():
        return None, failures + [f"{chapter}: missing {label} JSON {rel(json_path)}"]
    data = read_json(json_path, {})
    if not isinstance(data, dict):
        return None, failures + [f"{chapter}: {label} JSON must be an object"]

    official = official_chapter_path(chapter)
    recorded = data.get("official_chapter")
    if not isinstance(recorded, dict):
        failures.append(f"{chapter}: {stem}.json missing official_chapter")
    elif official.exists() and recorded.get("sha256") != sha256(official):
        failures.append(f"{chapter}: {stem}.json official_chapter hash is stale")
    status = str(data.get("status", "")).upper()
    if status not in {"CLEAR", "ACCEPTED_BY_HUMAN"}:
        failures.append(f"{chapter}: {stem}.json status is {status or 'MISSING'}; expected CLEAR or ACCEPTED_BY_HUMAN")
    categories = data.get("categories")
    if not isinstance(categories, dict):
        failures.append(f"{chapter}: {stem}.json missing categories")
    else:
        missing = sorted(set(CATEGORIES) - set(categories))
        failures.extend(f"{chapter}: {stem}.json missing category {item}" for item in missing)
        for key in CATEGORIES:
            item = categories.get(key)
            if not isinstance(item, dict):
                continue
            item_status = str(item.get("status", "")).upper()
            severity = str(item.get("severity", "")).upper()
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
    elif not any_quote_matches_official(quotes, official):
        failures.append(f"{chapter}: {stem}.json evidence quotes do not match the official chapter")
    return data, failures


def worst_severity(values: list[str]) -> str:
    valid = [value for value in values if value in SEVERITY_RANK]
    if not valid:
        return "P3"
    return sorted(valid, key=lambda value: SEVERITY_RANK[value])[0]


def merge_category(key: str, sources: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    statuses: list[str] = []
    severities: list[str] = []
    quotes: list[str] = []
    issues: list[str] = []
    actions: list[str] = []
    for label, data in sources:
        categories = data.get("categories") if isinstance(data, dict) else {}
        item = categories.get(key) if isinstance(categories, dict) else None
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).upper() or "BLOCKED"
        statuses.append(status)
        severities.append(str(item.get("severity", "")).upper())
        quotes.extend(as_list(item.get("evidence_quotes")))
        issue = str(item.get("issue", "")).strip()
        if issue:
            issues.append(f"{label}: {issue}")
        for action in as_list(item.get("revision_actions")):
            actions.append(f"{label}: {action}")
    blocked = any(status == "BLOCKED" for status in statuses)
    return {
        "status": "BLOCKED" if blocked else "CLEAR",
        "severity": worst_severity(severities),
        "evidence_quotes": list(dict.fromkeys(quotes)),
        "issue": " | ".join(issues) if issues else "Both LLM reviewers reported no ship-stopping semantic issue.",
        "revision_actions": list(dict.fromkeys(actions)) or ["none"],
    }


def evaluate(chapter: str) -> dict[str, Any]:
    path = official_path(chapter)
    if not path.exists() or not read_text(path).strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "reviewer": "codex_deepseek_semantic_reader_aggregate",
            "status": "NOT_READY",
            "official_chapter": {"path": rel(path), "sha256": ""},
            "source_reviews": {},
            "categories": {},
            "blockers": [f"missing official chapter: {rel(path)}"],
            "warnings": [],
            "human_acceptance": None,
        }

    loaded: list[tuple[str, dict[str, Any]]] = []
    source_reviews: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    for stem, label in SOURCE_STEMS:
        json_path = ROOT / "reviews" / chapter / f"{stem}.json"
        md_path = ROOT / "reviews" / chapter / f"{stem}.md"
        source_reviews[stem] = {"json": file_ref(json_path), "markdown": file_ref(md_path)}
        data, failures = validate_source(chapter, stem, label)
        blockers.extend(failures)
        if isinstance(data, dict):
            loaded.append((label, data))
            warnings.extend(f"{label}: {item}" for item in as_list(data.get("warnings")))
            blockers.extend(f"{label}: {item}" for item in as_list(data.get("blockers")) if data.get("status") != "ACCEPTED_BY_HUMAN")

    categories = {key: merge_category(key, loaded) for key in CATEGORIES}
    if len(loaded) < len(SOURCE_STEMS):
        status = "NOT_READY"
    elif blockers or any(item["status"] == "BLOCKED" for item in categories.values()):
        status = "BLOCKED"
    else:
        status = "CLEAR"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "reviewer": "codex_deepseek_semantic_reader_aggregate",
        "status": status,
        "official_chapter": {"path": rel(path), "sha256": sha256(path)},
        "source_reviews": source_reviews,
        "categories": categories,
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Semantic Reader Review: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "review_sha256:",
        "",
        "## Summary",
        "",
        "Codex and DeepSeek semantic reader reviews are both required. This aggregate does not perform keyword heuristics.",
        "",
        "## Source Reviews",
        "",
    ]
    for stem, refs in (report.get("source_reviews") or {}).items():
        json_ref = refs.get("json", {}) if isinstance(refs, dict) else {}
        md_ref = refs.get("markdown", {}) if isinstance(refs, dict) else {}
        lines.append(f"- {stem}: json={json_ref.get('path', '')} markdown={md_ref.get('path', '')}")
    lines.extend(["", "## Categories", ""])
    for name, item in (report.get("categories") or {}).items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- status: {item.get('status', '')}",
                f"- severity: {item.get('severity', '')}",
                f"- issue: {item.get('issue', '')}",
                "- revision_actions:",
            ]
        )
        lines.extend(f"  - {action}" for action in item.get("revision_actions", []) or ["none"])
        lines.append("")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend([f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {item}" for item in values) if values else lines.append("- none")
        lines.append("")
    lines.extend(["## Evidence Quotes", ""])
    quotes: list[str] = []
    for item in (report.get("categories") or {}).values():
        quotes.extend(str(quote).strip() for quote in item.get("evidence_quotes", []) if str(quote).strip())
    lines.extend(f"- {quote}" for quote in list(dict.fromkeys(quotes)) or ["none"])
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate real Codex and DeepSeek semantic reader reviews.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "semantic_reader_review.json", report)
        write_text(out_dir / "semantic_reader_review.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
