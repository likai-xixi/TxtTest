from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, read_json, read_text
from context_governance import sha256
from workflow_errors import issue


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def _json(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not path.exists():
        return None, None
    try:
        data = read_json(path, {})
    except Exception as exc:
        return None, issue("SCHEMA", f"invalid JSON: {exc}", rel(path))
    if not isinstance(data, dict):
        return None, issue("SCHEMA", "top-level value must be an object", rel(path))
    return data, None


def chapter_candidates() -> list[str]:
    chapters: set[str] = set()
    for base in [
        ROOT / "outline" / "chapter_briefs",
        ROOT / "state" / "context_pack",
        ROOT / "state" / "derived" / "context_quality",
        ROOT / "reviews",
    ]:
        if not base.exists():
            continue
        for item in base.iterdir():
            name = item.name
            if name.endswith(".manifest.json"):
                chapters.add(name.removesuffix(".manifest.json"))
            elif name.endswith("_brief.md"):
                chapters.add(name.removesuffix("_brief.md"))
            elif name.endswith(".md") or name.endswith(".json"):
                chapters.add(name.rsplit(".", 1)[0])
            elif item.is_dir() and name.startswith("v"):
                chapters.add(name)
    return sorted(chapter for chapter in chapters if chapter.startswith("v") and "_c" in chapter)


def check_input_hashes(path: Path, data: dict[str, Any], key: str = "input_hashes") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    values = data.get(key, [])
    if isinstance(values, dict):
        values = [{"path": path_text, "sha256": hash_text} for path_text, hash_text in values.items()]
    if not isinstance(values, list):
        return [issue("SCHEMA", f"{key} must be a list or object", rel(path))]
    for item in values:
        if not isinstance(item, dict):
            issues.append(issue("SCHEMA", f"{key} entry must be an object", rel(path)))
            continue
        path_text = str(item.get("path") or "")
        expected = str(item.get("sha256") or "")
        if not path_text or not expected:
            issues.append(issue("SCHEMA", f"{key} entry missing path/sha256", rel(path)))
            continue
        source = ROOT / path_text
        if not source.exists():
            issues.append(issue("MISSING", "recorded source input is missing", path_text))
        elif sha256(source) != expected:
            issues.append(issue("STALE", "recorded source input hash changed", path_text))
    return issues


def check_nested_review_inputs(path: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if "inputs" in data:
        issues.extend(check_input_hashes(path, data, "inputs"))
    for reviewer in ("codex", "deepseek"):
        value = data.get(reviewer)
        if isinstance(value, dict) and "inputs" in value:
            issues.extend(check_input_hashes(path, value, "inputs"))
    return issues


def check_chapter(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    issues: list[dict[str, Any]] = []
    checked: list[str] = []

    ledger = ROOT / "state" / "event_ledger.jsonl"
    derived = ROOT / "state" / "derived" / "current_state.yaml"
    if ledger.exists() and derived.exists() and _mtime(derived) + 0.001 < _mtime(ledger):
        issues.append(issue("STALE", "derived current_state is older than event ledger", rel(derived)))
    checked.append(rel(derived))
    needs_reader_derived = any(
        path.exists()
        for path in (
            ROOT / "state" / "context_pack" / f"{chapter}.md",
            ROOT / "state" / "context_pack" / f"{chapter}.manifest.json",
            ROOT / "state" / "derived" / "context_quality" / f"{chapter}.json",
        )
    )
    for generated in [
        ROOT / "state" / "derived" / "personality" / "protagonist.json",
        ROOT / "state" / "derived" / "protagonist_progression.json",
        ROOT / "state" / "derived" / "concept_index.json",
        ROOT / "state" / "derived" / "world_reveal_ledger.json",
        ROOT / "state" / "derived" / "suspense_ledger.json",
    ]:
        if needs_reader_derived and not generated.exists():
            issues.append(issue("MISSING", "reader/personality derived state is missing", rel(generated)))
        elif ledger.exists() and generated.exists() and _mtime(generated) + 0.001 < _mtime(ledger):
            issues.append(issue("STALE", "reader/personality derived state is older than event ledger", rel(generated)))
        checked.append(rel(generated))

    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    brief_pack = ROOT / "state" / "context_pack" / f"{chapter}_brief.md"
    if brief.exists() and brief_pack.exists() and _mtime(brief_pack) + 0.001 < _mtime(brief):
        issues.append(issue("STALE", "brief pack is older than official brief", rel(brief_pack)))
    checked.append(rel(brief_pack))

    manifest_path = ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"
    manifest, manifest_error = _json(manifest_path)
    if manifest_error:
        issues.append(manifest_error)
    elif manifest:
        issues.extend(check_input_hashes(manifest_path, manifest))
        pack = ROOT / "state" / "context_pack" / f"{chapter}.md"
        pack_record = manifest.get("context_pack", {})
        if isinstance(pack_record, dict) and pack_record.get("sha256") and pack.exists() and pack_record["sha256"] != sha256(pack):
            issues.append(issue("STALE", "manifest context_pack hash does not match current pack", rel(pack)))
    checked.append(rel(manifest_path))

    quality_path = ROOT / "state" / "derived" / "context_quality" / f"{chapter}.json"
    quality, quality_error = _json(quality_path)
    if quality_error:
        issues.append(quality_error)
    elif quality:
        pack = ROOT / "state" / "context_pack" / f"{chapter}.md"
        manifest_file = ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"
        if quality.get("context_pack_sha256") and pack.exists() and quality["context_pack_sha256"] != sha256(pack):
            issues.append(issue("STALE", "context quality context_pack_sha256 is stale", rel(quality_path)))
        if quality.get("manifest_sha256") and manifest_file.exists() and quality["manifest_sha256"] != sha256(manifest_file):
            issues.append(issue("STALE", "context quality manifest_sha256 is stale", rel(quality_path)))
        issues.extend(check_input_hashes(quality_path, quality))
    checked.append(rel(quality_path))

    for manifest_name in ("review_manifest.json", "codex_review_manifest.json"):
        path = ROOT / "reviews" / chapter / manifest_name
        data, error = _json(path)
        if error:
            issues.append(error)
        elif data:
            issues.extend(check_nested_review_inputs(path, data))
        checked.append(rel(path))

    for review_name in (
        "opening_retention.md",
        "personality_drift.md",
        "hook_retention.md",
        "protagonist_charm.md",
        "world_reveal.md",
        "suspense_ladder.md",
        "language_memorability.md",
        "genre_fit.md",
    ):
        path = ROOT / "reviews" / chapter / review_name
        if path.exists():
            text = read_text(path)
            official = ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"
            if "official_chapter_sha256:" in text and official.exists() and sha256(official) not in text:
                issues.append(issue("STALE", f"{review_name} does not reference current official chapter sha", rel(path)))
        checked.append(rel(path))

    for landing_name in ("brief_landing.json", "chapter_landing.json"):
        path = ROOT / "reviews" / chapter / landing_name
        data, error = _json(path)
        if error:
            issues.append(error)
        elif data:
            issues.extend(check_input_hashes(path, data, "inputs"))
        checked.append(rel(path))

    categories = {item["category"] for item in issues}
    if "SCHEMA" in categories:
        status = "SCHEMA"
    elif "MISSING" in categories:
        status = "MISSING"
    elif "STALE" in categories:
        status = "STALE"
    else:
        status = "CLEAR"
    return {"chapter": chapter, "status": status, "checked": checked, "issues": issues}


def stale_summary(chapter: str | None = None) -> dict[str, Any]:
    chapters = [chapter] if chapter else chapter_candidates()[:10]
    results = [check_chapter(item) for item in chapters]
    issue_count = sum(len(item["issues"]) for item in results)
    stale_count = sum(1 for item in results if item["status"] == "STALE")
    schema_count = sum(1 for item in results if item["status"] == "SCHEMA")
    return {
        "status": "SCHEMA" if schema_count else "STALE" if stale_count else "MISSING" if any(item["status"] == "MISSING" for item in results) else "CLEAR",
        "checked_chapters": [item["chapter"] for item in results],
        "issue_count": issue_count,
        "stale_chapter_count": stale_count,
        "schema_chapter_count": schema_count,
    }


def print_text(result: dict[str, Any]) -> None:
    if "results" in result:
        print("# Stale Check")
        print(f"status: {result['summary']['status']}")
        print(f"checked_chapters: {', '.join(result['summary']['checked_chapters']) or 'none'}")
        print(f"issue_count: {result['summary']['issue_count']}")
        print()
        for item in result["results"]:
            print(f"## {item['chapter']} ({item['status']})")
            if not item["issues"]:
                print("- no stale inputs detected")
            for found in item["issues"]:
                text = f"{found['category']}: {found['message']}"
                if found.get("path"):
                    text += f" ({found['path']})"
                print(f"- {text}")
            print()
        return
    print(f"# Stale Check: {result['chapter']}")
    print(f"status: {result['status']}")
    print()
    if not result["issues"]:
        print("- no stale inputs detected")
    for found in result["issues"]:
        text = f"{found['category']}: {found['message']}"
        if found.get("path"):
            text += f" ({found['path']})"
        print(f"- {text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale workflow state without rebuilding it.")
    parser.add_argument("chapter", nargs="?")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.chapter:
        result = check_chapter(args.chapter)
    else:
        chapters = chapter_candidates()
        results = [check_chapter(chapter) for chapter in chapters[:10]]
        result = {"summary": stale_summary(), "results": results}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 1 if (result.get("status") == "SCHEMA" or result.get("summary", {}).get("status") == "SCHEMA") else 0


if __name__ == "__main__":
    raise SystemExit(main())
