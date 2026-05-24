from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, read_json, read_text
from context_governance import sha256
from deepseek_run_manifest import validate_run_manifest
from review_binding import review_hash_is_current, review_status
from shadow_check import evaluate as evaluate_shadow
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


def check_file_ref(path: Path, ref: Any, label: str, expected_path: Path | None = None) -> list[dict[str, Any]]:
    if not isinstance(ref, dict):
        return [issue("SCHEMA", f"{label} missing file reference", rel(path))]
    path_text = str(ref.get("path") or "")
    if not path_text:
        return [issue("SCHEMA", f"{label} file reference missing path", rel(path))]
    if expected_path is not None and path_text != rel(expected_path):
        return [issue("STALE", f"{label} path mismatch; expected {rel(expected_path)}", path_text)]
    source = ROOT / path_text
    recorded_exists = ref.get("exists")
    if recorded_exists is False:
        if source.exists():
            return [issue("STALE", f"{label} recorded source missing but it now exists", path_text)]
        return []
    if not source.exists():
        return [issue("MISSING", f"{label} recorded source is missing", path_text)]
    expected = str(ref.get("sha256") or "")
    if not expected:
        return [issue("SCHEMA", f"{label} file reference missing sha256", path_text)]
    if sha256(source) != expected:
        return [issue("STALE", f"{label} hash is stale", path_text)]
    return []


def chapter_number_safe(chapter: Any) -> int:
    text = str(chapter or "")
    try:
        return int(text[-3:])
    except ValueError:
        return 0


def check_reader_reward_index(chapter: str) -> tuple[list[str], list[dict[str, Any]]]:
    path = ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json"
    checked = [rel(path)]
    issues: list[dict[str, Any]] = []
    required = (ROOT / "reviews" / chapter / "reader_reward_gate.json").exists()
    data, error = _json(path)
    if error:
        issues.append(error)
    elif data:
        issues.extend(check_file_ref(path, data.get("source_policy"), "reader_reward_index source_policy", ROOT / "ops" / "reader_reward_policy.json"))
        issues.extend(check_file_ref(path, data.get("source_reader_promise"), "reader_reward_index source_reader_promise", ROOT / "state" / "project_reader_promise.json"))
        for item in data.get("chapters", []):
            if isinstance(item, dict):
                gate_ref = item.get("gate")
                issues.extend(check_file_ref(path, gate_ref, f"reader_reward_index {item.get('chapter') or 'chapter'} gate"))
            else:
                issues.append(issue("SCHEMA", "reader_reward_index chapter entry must be an object", rel(path)))
    elif required:
        issues.append(issue("MISSING", "reader_reward_index is missing after reader_reward_gate exists", rel(path)))
    return checked, issues


def check_reader_risk_index(chapter: str) -> tuple[list[str], list[dict[str, Any]]]:
    path = ROOT / "state" / "derived" / "reader_risk" / "latest.json"
    checked = [rel(path), rel(path.with_suffix(".md"))]
    issues: list[dict[str, Any]] = []
    required = any(
        (ROOT / "reviews" / chapter / name).exists()
        for name in ("reader_reward_gate.json", "chapter_shape.json", "reader_feedback.json")
    )
    data, error = _json(path)
    if error:
        issues.append(error)
    elif data:
        through = str(data.get("through") or "")
        if chapter_number_safe(through) < chapter_number_safe(chapter):
            issues.append(issue("STALE", f"reader_risk latest only covers {through or 'none'}, not {chapter}", rel(path)))
        issues.extend(check_file_ref(path, data.get("source_reader_promise"), "reader_risk latest source_reader_promise", ROOT / "state" / "project_reader_promise.json"))
        issues.extend(check_file_ref(path, data.get("source_event_ledger"), "reader_risk latest source_event_ledger", ROOT / "state" / "event_ledger.jsonl"))
        for item in data.get("chapters", []):
            if not isinstance(item, dict):
                issues.append(issue("SCHEMA", "reader_risk chapter entry must be an object", rel(path)))
                continue
            item_chapter = item.get("chapter") or "chapter"
            for key in ("reader_reward_gate", "chapter_shape", "reader_feedback"):
                if key in item:
                    issues.extend(check_file_ref(path, item.get(key), f"reader_risk {item_chapter} {key}"))
    elif required:
        issues.append(issue("MISSING", "reader_risk latest is missing after reader experience reports exist", rel(path)))
    return checked, issues


def check_long_health(chapter: str) -> tuple[list[str], list[dict[str, Any]]]:
    path = ROOT / "state" / "derived" / "long_health" / "latest.json"
    checked = [rel(path), rel(path.with_suffix(".md"))]
    issues: list[dict[str, Any]] = []
    required = chapter_number_safe(chapter) >= 10
    data, error = _json(path)
    if error:
        issues.append(error)
    elif data:
        through = str(data.get("through") or "")
        if chapter_number_safe(through) < chapter_number_safe(chapter):
            issues.append(issue("STALE", f"long_health latest only covers {through or 'none'}, not {chapter}", rel(path)))
        issues.extend(check_file_ref(path, data.get("source_reader_promise"), "long_health latest source_reader_promise", ROOT / "state" / "project_reader_promise.json"))
        issues.extend(check_file_ref(path, data.get("source_event_ledger"), "long_health latest source_event_ledger", ROOT / "state" / "event_ledger.jsonl"))
        for item in data.get("rolling_input_refs", []):
            if not isinstance(item, dict):
                issues.append(issue("SCHEMA", "long_health rolling_input_refs entry must be an object", rel(path)))
                continue
            item_chapter = item.get("chapter") or "chapter"
            for key in ("reader_reward_gate", "chapter_shape"):
                if key in item:
                    issues.extend(check_file_ref(path, item.get(key), f"long_health {item_chapter} {key}"))
    elif required:
        issues.append(issue("MISSING", "long_health latest is missing for chapter 10+", rel(path)))
    return checked, issues


def check_shadow_memory(chapter: str) -> tuple[list[str], list[dict[str, Any]]]:
    paths = [
        ROOT / "state" / "shadow" / "local_window" / f"{chapter}.json",
        ROOT / "state" / "shadow" / "rag_index" / f"{chapter}.json",
        ROOT / "state" / "shadow" / "kg_edges" / f"{chapter}.json",
        ROOT / "state" / "shadow" / "route_signals" / f"{chapter}.json",
        ROOT / "state" / "shadow" / "manifests" / f"{chapter}.json",
    ]
    checked = [rel(path) for path in paths]
    required = (ROOT / "state" / "context_pack" / f"{chapter}.manifest.json").exists()
    if not required and not any(path.exists() for path in paths):
        return checked, []
    report = evaluate_shadow(chapter)
    issues = []
    for blocker in report.get("blockers", []):
        lowered = blocker.lower()
        if "missing" in lowered:
            category = "MISSING"
        elif "stale" in lowered or "hash" in lowered:
            category = "STALE"
        elif "json" in lowered or "schema" in lowered:
            category = "SCHEMA"
        else:
            category = "POLICY"
        issues.append(issue(category, blocker, "state/shadow"))
    return checked, issues


def check_derived_ledger(path: Path, chapter: str, label: str) -> tuple[list[str], list[dict[str, Any]]]:
    checked = [rel(path)]
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return checked, issues
    data, error = _json(path)
    if error:
        issues.append(error)
        return checked, issues
    if not data:
        return checked, issues
    through = str(data.get("through") or "")
    if through and chapter_number_safe(through) < chapter_number_safe(chapter):
        issues.append(issue("STALE", f"{label} only covers {through}, not {chapter}", rel(path)))
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if ledger.exists() and _mtime(path) + 0.001 < _mtime(ledger):
        issues.append(issue("STALE", f"{label} is older than event ledger", rel(path)))
    issues.extend(check_file_ref(path, data.get("source_event_ledger"), f"{label} source_event_ledger", ledger))
    chapters = data.get("chapters", [])
    if chapters is not None:
        if not isinstance(chapters, list):
            issues.append(issue("SCHEMA", f"{label} chapters must be a list", rel(path)))
        else:
            for chapter_index, item in enumerate(chapters, start=1):
                if not isinstance(item, dict):
                    issues.append(issue("SCHEMA", f"{label} chapters[{chapter_index}] must be an object", rel(path)))
                    continue
                refs = item.get("source_refs")
                if refs is None:
                    continue
                if not isinstance(refs, list):
                    issues.append(issue("SCHEMA", f"{label} chapters[{chapter_index}].source_refs must be a list", rel(path)))
                    continue
                item_chapter = item.get("chapter") or f"chapter#{chapter_index}"
                for ref_index, ref in enumerate(refs, start=1):
                    issues.extend(check_file_ref(path, ref, f"{label} {item_chapter} source_refs[{ref_index}]"))
    return checked, issues


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

    review_context_json = ROOT / "state" / "context_pack" / f"{chapter}_review_context.json"
    review_context_md = ROOT / "state" / "context_pack" / f"{chapter}_review_context.md"
    review_context, review_context_error = _json(review_context_json)
    if review_context_error:
        issues.append(review_context_error)
    elif review_context:
        issues.extend(check_input_hashes(review_context_json, review_context))
    checked.append(rel(review_context_json))
    checked.append(rel(review_context_md))

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

    shadow_checked, shadow_issues = check_shadow_memory(chapter)
    checked.extend(shadow_checked)
    issues.extend(shadow_issues)

    for manifest_name in ("review_manifest.json", "codex_review_manifest.json"):
        path = ROOT / "reviews" / chapter / manifest_name
        data, error = _json(path)
        if error:
            issues.append(error)
        elif data:
            issues.extend(check_nested_review_inputs(path, data))
        checked.append(rel(path))

    for review_name in (
        "ai_taste.md",
        "dialogue_function.md",
        "emotion_relationship_gate.md",
        "codex_semantic_reader_review.md",
        "deepseek_semantic_reader_review.md",
        "semantic_reader_review.md",
        "memorable_scene.md",
        "codex_anti_ai_review.md",
        "deepseek_anti_ai_review.md",
        "review_arbitration.md",
        "revision_plan.md",
        "gray_consequence.md",
        "chapter_shape.md",
        "reader_reward_gate.md",
        "reader_feedback.md",
        "receive_chapter.md",
        "web_satisfaction.md",
        "retention_risk.md",
        "originality.md",
        "similarity_risk.md",
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
            if review_status(text) in {"CLEAR", "ACCEPTED_BY_HUMAN"} and "review_sha256:" in text and not review_hash_is_current(text, path):
                issues.append(issue("STALE", f"{review_name} review_sha256 does not match current review body", rel(path)))
        checked.append(rel(path))

    for review_json in (
        "ai_taste.json",
        "dialogue_function.json",
        "emotion_relationship_gate.json",
        "codex_semantic_reader_review.json",
        "deepseek_semantic_reader_review.json",
        "semantic_reader_review.json",
        "memorable_scene.json",
        "codex_anti_ai_review.json",
        "deepseek_anti_ai_review.json",
        "revision_plan.json",
        "review_arbitration.json",
        "gray_consequence.json",
        "chapter_shape.json",
        "reader_reward_gate.json",
        "reader_feedback.json",
        "receive_chapter.json",
    ):
        path = ROOT / "reviews" / chapter / review_json
        data, error = _json(path)
        if error:
            issues.append(error)
        elif data:
            official = ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"
            recorded = data.get("official_chapter")
            if isinstance(recorded, dict) and official.exists() and recorded.get("sha256") != sha256(official):
                issues.append(issue("STALE", f"{review_json} official_chapter sha is stale", rel(path)))
            issues.extend(check_input_hashes(path, data))
        checked.append(rel(path))

    for kind in ("review", "anti_ai_review", "semantic_reader_review", "style_review"):
        manifest_path = ROOT / "external_runs" / "deepseek" / chapter / f"{kind}.manifest.json"
        if manifest_path.exists():
            for message in validate_run_manifest(chapter, kind):
                issues.append(issue("STALE", message, rel(manifest_path)))
        checked.append(rel(manifest_path))

    for landing_name in ("brief_landing.json", "chapter_landing.json"):
        path = ROOT / "reviews" / chapter / landing_name
        data, error = _json(path)
        if error:
            issues.append(error)
        elif data:
            issues.extend(check_input_hashes(path, data, "inputs"))
        checked.append(rel(path))

    codex_anti_manifest = ROOT / "reviews" / chapter / "codex_anti_ai_review_manifest.json"
    data, error = _json(codex_anti_manifest)
    if error:
        issues.append(error)
    elif data:
        issues.extend(check_nested_review_inputs(codex_anti_manifest, data))
    checked.append(rel(codex_anti_manifest))

    codex_semantic_manifest = ROOT / "reviews" / chapter / "codex_semantic_reader_review_manifest.json"
    data, error = _json(codex_semantic_manifest)
    if error:
        issues.append(error)
    elif data:
        issues.extend(check_nested_review_inputs(codex_semantic_manifest, data))
    checked.append(rel(codex_semantic_manifest))

    for extra_checked, extra_issues in (
        check_reader_reward_index(chapter),
        check_reader_risk_index(chapter),
        check_long_health(chapter),
        check_derived_ledger(ROOT / "state" / "derived" / "thread_debt_ledger.json", chapter, "thread_debt_ledger"),
        check_derived_ledger(ROOT / "state" / "derived" / "character_arc_ledger.json", chapter, "character_arc_ledger"),
        check_derived_ledger(ROOT / "state" / "derived" / "style_voice_ledger.json", chapter, "style_voice_ledger"),
    ):
        checked.extend(extra_checked)
        issues.extend(extra_issues)

    categories = {item["category"] for item in issues}
    if "SCHEMA" in categories:
        status = "SCHEMA"
    elif "STALE" in categories:
        status = "STALE"
    elif "MISSING" in categories:
        status = "MISSING"
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero for STALE or MISSING results as well as SCHEMA errors.",
    )
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
    status = result.get("status") or result.get("summary", {}).get("status")
    blocking = {"SCHEMA", "STALE", "MISSING"} if args.strict else {"SCHEMA"}
    return 1 if status in blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
