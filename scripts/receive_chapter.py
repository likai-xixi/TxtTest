from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256
from product_kernel import (
    context_manifest_path,
    event_ledger_path,
    file_ref,
    official_brief_path,
    review_json_stale_failures,
    review_route_path,
    route_artifact_status,
)


ROUTED_STEP_KEYS = {
    "style-check": {"style_voice"},
    "series-style-check": {"series_style", "style_voice"},
    "ai-taste-check": {"ai_taste"},
    "dialogue-function-check": {"dialogue_function"},
    "emotion-relationship-gate": {"emotion_relationship"},
    "semantic-reader-review": {"semantic_reader"},
    "memorable-scene-check": {"memorable_scene"},
    "compare": {"codex_integrated", "deepseek_integrated"},
    "review-arbitration": {"review_arbitration"},
    "gray-consequence": {"review_arbitration"},
    "chapter-shape-check": {"long_health"},
    "prose-risk-check": {"prose_risk"},
    "prose-risk-index": {"prose_risk"},
    "reader-reward-check": {"reader_reward"},
    "reader-reward-index": {"reader_reward"},
    "long-health": {"long_health"},
    "reader-feedback": {"reader_risk"},
    "reader-risk-index": {"reader_risk"},
    "revision-plan": {"revision_plan"},
    "revision-closure": {"revision_plan"},
    "codex_anti_ai_start": {"codex_anti_ai"},
    "codex_anti_ai_review": {"codex_anti_ai"},
    "codex_semantic_reader_review_start": {"codex_semantic"},
    "codex_semantic_reader_review": {"codex_semantic"},
    "deepseek_review": {"deepseek_integrated"},
    "deepseek_anti_ai": {"deepseek_anti_ai"},
    "deepseek_semantic_reader_review": {"deepseek_semantic"},
}

PRE_ROUTE_PREVIEW_STEPS = {
    "selection",
    "landing",
    "codex_review",
    "review_context",
    "context-quality",
    "human-flavor-check",
    "highlights-review",
    "ai-taste-check",
    "prose-risk-check",
    "route-reviews",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def has_chapter_anchor(chapter: str) -> bool:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("chapter") == chapter and entry.get("type") == "chapter_anchor" and entry.get("verified_by") == "human":
            return True
    return False


def file_status(path: Path, label: str) -> dict[str, Any]:
    exists = path.exists() and bool(read_text(path).strip() if path.suffix == ".md" else path.read_bytes())
    return {
        "name": label,
        "command": [],
        "status": "READY" if exists else "NOT_READY",
        "returncode": 0 if exists else 1,
        "output": f"found {rel(path)}" if exists else f"missing {rel(path)}",
        "artifacts": [rel(path)],
    }


def run_command(name: str, args: list[str]) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts" / "novel.py"), *args]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
    output = (result.stdout or "") + (result.stderr or "")
    return {
        "name": name,
        "command": ["python", "scripts/novel.py", *args],
        "status": "READY" if result.returncode == 0 else "NOT_READY",
        "returncode": result.returncode,
        "output": output.strip(),
        "artifacts": [],
    }


def current_ref_failures(ref: Any, label: str, expected_path: Path | None = None) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{label} missing file reference"]
    path_text = str(ref.get("path") or "")
    if not path_text:
        return [f"{label} file reference missing path"]
    if expected_path is not None and path_text != rel(expected_path):
        return [f"{label} path mismatch: expected {rel(expected_path)}"]
    source = ROOT / path_text
    if ref.get("exists") is False:
        return [f"{label} recorded source missing but it now exists: {path_text}"] if source.exists() else []
    if not source.exists():
        return [f"{label} recorded source is missing: {path_text}"]
    expected = str(ref.get("sha256") or "")
    if not expected:
        return [f"{label} file reference missing sha256: {path_text}"]
    if sha256(source) != expected:
        return [f"{label} hash changed: {path_text}"]
    return []


def chapter_number_safe(chapter: Any) -> int:
    try:
        return chapter_number(str(chapter))
    except Exception:
        return 0


def derived_artifact_failures(name: str, primary: Path, chapter: str) -> list[str]:
    if name == "context-quality":
        data = read_json(primary, {}) if primary.exists() else {}
        if not isinstance(data, dict) or not data:
            return ["context-quality is not a JSON object"]
        failures: list[str] = []
        pack = ROOT / "state" / "context_pack" / f"{chapter}.md"
        manifest = ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"
        if not pack.exists():
            failures.append(f"context-quality source pack is missing: {rel(pack)}")
        elif data.get("context_pack_sha256") != sha256(pack):
            failures.append("context-quality context_pack_sha256 is stale")
        if not manifest.exists():
            failures.append(f"context-quality source manifest is missing: {rel(manifest)}")
        elif data.get("manifest_sha256") != sha256(manifest):
            failures.append("context-quality manifest_sha256 is stale")
        if data.get("status") != "READY":
            failures.append(f"context-quality status is {data.get('status', 'MISSING')}")
        return failures
    if name not in {"reader-reward-index", "reader-risk-index", "prose-risk-index", "long-health"}:
        return []
    data = read_json(primary, {}) if primary.exists() else {}
    if not isinstance(data, dict) or not data:
        return [f"{name} is not a JSON object"]
    failures: list[str] = []
    if name == "reader-reward-index":
        failures.extend(current_ref_failures(data.get("source_policy"), "reader_reward_index source_policy", ROOT / "ops" / "reader_reward_policy.json"))
        failures.extend(current_ref_failures(data.get("source_reader_promise"), "reader_reward_index source_reader_promise", ROOT / "state" / "project_reader_promise.json"))
        for item in data.get("chapters", []):
            if isinstance(item, dict):
                failures.extend(current_ref_failures(item.get("gate"), f"reader_reward_index {item.get('chapter') or 'chapter'} gate"))
            else:
                failures.append("reader_reward_index chapter entry is not an object")
        return failures

    through = str(data.get("through") or "")
    if chapter_number_safe(through) < chapter_number_safe(chapter):
        failures.append(f"{name} only covers {through or 'none'}, not {chapter}")
    failures.extend(current_ref_failures(data.get("source_event_ledger"), f"{name} source_event_ledger", ROOT / "state" / "event_ledger.jsonl"))
    if name == "prose-risk-index":
        for item in data.get("chapters", []):
            if not isinstance(item, dict):
                failures.append("prose_risk chapter entry is not an object")
                continue
            item_chapter = item.get("chapter") or "chapter"
            for key in ("prose_risk", "chapter_shape"):
                if key in item:
                    failures.extend(current_ref_failures(item.get(key), f"prose_risk {item_chapter} {key}"))
        return failures

    failures.extend(current_ref_failures(data.get("source_reader_promise"), f"{name} source_reader_promise", ROOT / "state" / "project_reader_promise.json"))

    if name == "reader-risk-index":
        for item in data.get("chapters", []):
            if not isinstance(item, dict):
                failures.append("reader_risk chapter entry is not an object")
                continue
            item_chapter = item.get("chapter") or "chapter"
            for key in ("reader_reward_gate", "chapter_shape", "reader_feedback"):
                if key in item:
                    failures.extend(current_ref_failures(item.get(key), f"reader_risk {item_chapter} {key}"))
    else:
        for item in data.get("rolling_input_refs", []):
            if not isinstance(item, dict):
                failures.append("long_health rolling input entry is not an object")
                continue
            item_chapter = item.get("chapter") or "chapter"
            for key in ("reader_reward_gate", "chapter_shape"):
                if key in item:
                    failures.extend(current_ref_failures(item.get(key), f"long_health {item_chapter} {key}"))
    return failures


def control_input_hashes(chapter: str) -> list[dict[str, Any]]:
    return [
        file_ref(official_path(chapter)),
        file_ref(official_brief_path(chapter)),
        file_ref(context_manifest_path(chapter)),
        file_ref(event_ledger_path()),
        file_ref(review_route_path(chapter)),
    ]


def should_skip(primary: Path | None, resume: bool, *, name: str = "", chapter: str = "") -> tuple[bool, str]:
    if not (resume and primary and primary.exists()):
        return False, ""
    if name == "route-reviews" and chapter:
        _route, failures, _data = route_artifact_status(chapter)
        if failures:
            return False, "; ".join(failures[:3])
    review_json_names = {
        "human-flavor-check": "human_flavor.json",
        "highlights-review": "highlights_review.json",
        "ai-taste-check": "ai_taste.json",
        "prose-risk-check": "prose_risk.json",
    }
    if name in review_json_names and chapter:
        failures = review_json_stale_failures(chapter, review_json_names[name])
        if failures:
            return False, "; ".join(failures[:3])
    failures = derived_artifact_failures(name, primary, chapter)
    if failures:
        return False, "; ".join(failures[:3])
    return True, ""


def planned_steps(chapter: str, *, run_deepseek: bool) -> list[dict[str, Any]]:
    steps = [
        {"name": "selection", "command": [], "writes": []},
        {"name": "landing", "command": [], "writes": []},
        {"name": "codex_review", "command": [], "writes": []},
        {"name": "review_context", "command": ["review-context", chapter, "--write"], "writes": [f"state/context_pack/{chapter}_review_context.json"]},
        {"name": "human-flavor-check", "command": ["human-flavor-check", chapter, "--write"], "writes": [f"reviews/{chapter}/human_flavor.json"]},
        {"name": "highlights-review", "command": ["highlights-review", chapter, "--write"], "writes": [f"reviews/{chapter}/highlights_review.json"]},
        {"name": "ai-taste-check", "command": ["ai-taste-check", chapter], "writes": [f"reviews/{chapter}/ai_taste.json"]},
        {"name": "prose-risk-check", "command": ["prose-risk-check", chapter, "--write"], "writes": [f"reviews/{chapter}/prose_risk.json"]},
        {"name": "route-reviews", "command": ["route-reviews", chapter, "--write"], "writes": [f"reviews/{chapter}/review_route.json"]},
        {"name": "codex_anti_ai_start", "command": ["codex-anti-ai-review-start", chapter], "writes": [f"reviews/{chapter}/codex_anti_ai_review_manifest.json"]},
        {"name": "codex_anti_ai_review", "command": [], "writes": [f"reviews/{chapter}/codex_anti_ai_review.json"]},
        {"name": "codex_semantic_reader_review_start", "command": ["codex-semantic-reader-review-start", chapter], "writes": [f"reviews/{chapter}/codex_semantic_reader_review_manifest.json"]},
        {"name": "codex_semantic_reader_review", "command": [], "writes": [f"reviews/{chapter}/codex_semantic_reader_review.json"]},
        {"name": "deepseek_review", "command": ["review", chapter, "--deepseek"] if run_deepseek else [], "writes": [f"reviews/{chapter}/deepseek_integrated_review.md"]},
        {"name": "deepseek_anti_ai", "command": ["deepseek-anti-ai-review", chapter] if run_deepseek else [], "writes": [f"reviews/{chapter}/deepseek_anti_ai_review.json"]},
        {"name": "deepseek_semantic_reader_review", "command": ["deepseek-semantic-reader-review", chapter] if run_deepseek else [], "writes": [f"reviews/{chapter}/deepseek_semantic_reader_review.json"]},
        {"name": "context-quality", "command": ["context-quality", chapter], "writes": [f"state/derived/context_quality/{chapter}.json"]},
        {"name": "style-check", "command": ["style-check", chapter], "writes": [f"reviews/{chapter}/style_metrics.json"]},
        {"name": "series-style-check", "command": ["series-style-check", chapter], "writes": [f"reviews/{chapter}/series_style.json"]},
        {"name": "dialogue-function-check", "command": ["dialogue-function-check", chapter], "writes": [f"reviews/{chapter}/dialogue_function.json"]},
        {"name": "emotion-relationship-gate", "command": ["emotion-relationship-gate", chapter, "--write"], "writes": [f"reviews/{chapter}/emotion_relationship_gate.json"]},
        {"name": "semantic-reader-review", "command": ["semantic-reader-review", chapter, "--write"], "writes": [f"reviews/{chapter}/semantic_reader_review.json"]},
        {"name": "memorable-scene-check", "command": ["memorable-scene-check", chapter, "--write"], "writes": [f"reviews/{chapter}/memorable_scene.json"]},
        {"name": "continuity", "command": ["continuity", chapter], "writes": [f"reviews/{chapter}/continuity.md"]},
        {"name": "compare", "command": ["compare", chapter], "writes": [f"reviews/{chapter}/model_disagreement.md"]},
        {"name": "fact-cards", "command": ["fact-cards", chapter, "--write"], "writes": [f"reviews/{chapter}/fact_cards.json"]},
        {"name": "review-arbitration", "command": ["review-arbitration", chapter], "writes": [f"reviews/{chapter}/review_arbitration.json"]},
        {"name": "gray-consequence", "command": ["gray-consequence", chapter, "--write"], "writes": [f"reviews/{chapter}/gray_consequence.json"]},
        {"name": "chapter-shape-check", "command": ["chapter-shape-check", chapter, "--write"], "writes": [f"reviews/{chapter}/chapter_shape.json"]},
        {"name": "prose-risk-index", "command": ["prose-risk-index", "--to", chapter, "--write"], "writes": ["state/derived/prose_risk/latest.json"]},
        {"name": "reader-reward-check", "command": ["reader-reward-check", chapter, "--write"], "writes": [f"reviews/{chapter}/reader_reward_gate.json"]},
        {"name": "reader-reward-index", "command": ["reader-reward-index", "--write"], "writes": ["state/derived/pacing/reader_reward_index.json"]},
        {"name": "reader-feedback", "command": ["reader-feedback", "summarize", chapter], "writes": [f"reviews/{chapter}/reader_feedback.json"]},
        {"name": "reader-risk-index", "command": ["reader-risk-index", "--to", chapter, "--write"], "writes": ["state/derived/reader_risk/latest.json"]},
        {"name": "revision-plan", "command": ["revision-plan", chapter], "writes": [f"reviews/{chapter}/revision_plan.json"]},
        {"name": "revision-closure", "command": ["revision-closure", chapter], "writes": []},
        {"name": "review-summary", "command": ["review-summary", chapter, "--write"], "writes": [f"reviews/{chapter}/review_summary.json"]},
        {"name": "chapter-evidence", "command": ["evidence", chapter], "writes": []},
    ]
    if chapter_number(chapter) >= 10:
        revision_index = next((index for index, step in enumerate(steps) if step["name"] == "revision-plan"), len(steps) - 1)
        steps.insert(revision_index, {"name": "long-health", "command": ["long-health", "--to", chapter, "--write"], "writes": ["state/derived/long_health/latest.json"]})
    return steps


def route_aware_preview_steps(chapter: str, *, run_deepseek: bool) -> tuple[list[dict[str, Any]], str]:
    steps = planned_steps(chapter, run_deepseek=run_deepseek)
    route, failures, route_data = route_artifact_status(chapter)
    if failures or not route_data:
        pending = {
            "name": "route-dependent-steps",
            "command": [],
            "writes": [],
            "status": "PENDING",
            "reason": "; ".join(failures[:3]) if failures else "route artifact is not ready",
        }
        return [step for step in steps if step.get("name") in PRE_ROUTE_PREVIEW_STEPS] + [pending], "route-dependent steps pending until review_route.json is READY"

    route_reviews = set(route_data.get("additional_literary_reviews", [])) if isinstance(route_data, dict) else set()
    route_name = str(route_data.get("route", route)).lower() if isinstance(route_data, dict) else route
    filtered: list[dict[str, Any]] = []
    for step in steps:
        name = str(step.get("name", ""))
        required_keys = ROUTED_STEP_KEYS.get(name)
        if required_keys is not None and not (route_reviews & required_keys) and route_name not in {"heavy", "gate"}:
            continue
        filtered.append(step)
    return filtered, f"route-aware preview using {route_name.upper()} route"


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    chapter_parts(args.chapter)
    review_dir = ROOT / "reviews" / args.chapter
    steps: list[dict[str, Any]] = []

    if args.preview:
        steps, preview_note = route_aware_preview_steps(args.chapter, run_deepseek=args.run_deepseek)
        if not getattr(args, "verbose", False):
            return {
                "schema_version": 1,
                "chapter": args.chapter,
                "generated_at": now_iso(),
                "status": "PREVIEW",
                "mode": "compact",
                "input_hashes": control_input_hashes(args.chapter),
                "editor_lines": [
                    "status: PREVIEW",
                    preview_note,
                    "ship_gates: always required; route cannot skip them",
                    "next: run receive-chapter without --preview, or add --verbose for the full step plan",
                    "writes: none in preview",
                ],
                "hidden_step_count": len(steps),
                "next_action": "Run without --preview when ready, or add --verbose to inspect the route-aware step plan.",
            }
        return {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "PREVIEW",
            "mode": "verbose",
            "input_hashes": control_input_hashes(args.chapter),
            "route_note": preview_note,
            "steps": steps,
            "next_action": "Run without --preview when ready to execute local checks.",
        }

    prerequisites = [
        (ROOT / "state" / "selections" / f"{args.chapter}.json", "candidate_selection"),
        (review_dir / "chapter_landing.json", "chapter_landing"),
        (official_path(args.chapter), "official_chapter"),
    ]
    for path, label in prerequisites:
        steps.append(file_status(path, label))

    pre_route_steps = [
        ("review-context", ["review-context", args.chapter, "--write"], ROOT / "state" / "context_pack" / f"{args.chapter}_review_context.json"),
        ("context-quality", ["context-quality", args.chapter], ROOT / "state" / "derived" / "context_quality" / f"{args.chapter}.json"),
        ("human-flavor-check", ["human-flavor-check", args.chapter, "--write"], review_dir / "human_flavor.json"),
        ("highlights-review", ["highlights-review", args.chapter, "--write"], review_dir / "highlights_review.json"),
        ("ai-taste-check", ["ai-taste-check", args.chapter], review_dir / "ai_taste.json"),
        ("prose-risk-check", ["prose-risk-check", args.chapter, "--write"], review_dir / "prose_risk.json"),
        ("route-reviews", ["route-reviews", args.chapter, "--write"], review_dir / "review_route.json"),
    ]
    for name, command, primary in pre_route_steps:
        skip, stale_reason = should_skip(primary, args.resume, name=name, chapter=args.chapter)
        if skip:
            steps.append({"name": name, "command": ["python", "scripts/novel.py", *command], "status": "SKIPPED", "returncode": 0, "output": f"resume kept {rel(primary)}", "artifacts": [rel(primary)]})
            continue
        result = run_command(name, command)
        if stale_reason:
            result["output"] = f"resume reran because {stale_reason}\n{result['output']}".strip()
        steps.append(result)

    try:
        route_data = read_json(review_dir / "review_route.json", {})
    except Exception:
        route_data = {}
    route_reviews = set(route_data.get("additional_literary_reviews", [])) if isinstance(route_data, dict) else set()
    route_name = str(route_data.get("route", "heavy")).lower() if isinstance(route_data, dict) else "heavy"
    if not route_reviews:
        route_reviews = {
            "style_voice",
            "ai_taste",
            "dialogue_function",
            "emotion_relationship",
            "memorable_scene",
            "reader_reward",
            "reader_risk",
            "codex_integrated",
            "deepseek_integrated",
            "codex_anti_ai",
            "deepseek_anti_ai",
            "codex_semantic",
            "deepseek_semantic",
            "semantic_reader",
            "review_arbitration",
            "revision_plan",
            "series_style",
            "long_health",
        }

    if "codex_integrated" in route_reviews:
        steps.append(file_status(review_dir / "codex_integrated_review.md", "codex_integrated_review"))
    if "codex_anti_ai" in route_reviews:
        steps.append(file_status(review_dir / "codex_anti_ai_review.json", "codex_anti_ai_review"))
    if "codex_semantic" in route_reviews:
        steps.append(file_status(review_dir / "codex_semantic_reader_review.json", "codex_semantic_reader_review"))

    if args.run_deepseek:
        if "deepseek_integrated" in route_reviews:
            skip, _reason = should_skip(review_dir / "deepseek_integrated_review.md", args.resume)
            if not skip:
                steps.append(run_command("deepseek_review", ["review", args.chapter, "--deepseek"]))
        if "deepseek_anti_ai" in route_reviews:
            skip, _reason = should_skip(review_dir / "deepseek_anti_ai_review.json", args.resume)
            if not skip:
                steps.append(run_command("deepseek_anti_ai", ["deepseek-anti-ai-review", args.chapter]))
        if "deepseek_semantic" in route_reviews:
            skip, _reason = should_skip(review_dir / "deepseek_semantic_reader_review.json", args.resume)
            if not skip:
                steps.append(run_command("deepseek_semantic_reader_review", ["deepseek-semantic-reader-review", args.chapter]))
    else:
        if "deepseek_integrated" in route_reviews:
            steps.append(file_status(review_dir / "deepseek_integrated_review.md", "deepseek_integrated_review"))
        if "deepseek_anti_ai" in route_reviews:
            steps.append(file_status(review_dir / "deepseek_anti_ai_review.json", "deepseek_anti_ai_review"))
        if "deepseek_semantic" in route_reviews:
            steps.append(file_status(review_dir / "deepseek_semantic_reader_review.json", "deepseek_semantic_reader_review"))

    command_steps = [
        ("style-check", ["style-check", args.chapter], review_dir / "style_metrics.json"),
        ("series-style-check", ["series-style-check", args.chapter], review_dir / "series_style.json"),
        ("dialogue-function-check", ["dialogue-function-check", args.chapter], review_dir / "dialogue_function.json"),
        ("emotion-relationship-gate", ["emotion-relationship-gate", args.chapter, "--write"], review_dir / "emotion_relationship_gate.json"),
        ("semantic-reader-review", ["semantic-reader-review", args.chapter, "--write"], review_dir / "semantic_reader_review.json"),
        ("memorable-scene-check", ["memorable-scene-check", args.chapter, "--write"], review_dir / "memorable_scene.json"),
        ("continuity", ["continuity", args.chapter], review_dir / "continuity.md"),
        ("compare", ["compare", args.chapter], review_dir / "model_disagreement.md"),
        ("fact-cards", ["fact-cards", args.chapter, "--write"], review_dir / "fact_cards.json"),
        ("review-arbitration", ["review-arbitration", args.chapter], review_dir / "review_arbitration.json"),
        ("gray-consequence", ["gray-consequence", args.chapter, "--write"], review_dir / "gray_consequence.json"),
        ("chapter-shape-check", ["chapter-shape-check", args.chapter, "--write"], review_dir / "chapter_shape.json"),
        ("prose-risk-index", ["prose-risk-index", "--to", args.chapter, "--write"], ROOT / "state" / "derived" / "prose_risk" / "latest.json"),
        ("reader-reward-check", ["reader-reward-check", args.chapter, "--write"], review_dir / "reader_reward_gate.json"),
        ("reader-reward-index", ["reader-reward-index", "--write"], ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json"),
        *(
            [("long-health", ["long-health", "--to", args.chapter, "--write"], ROOT / "state" / "derived" / "long_health" / "latest.json")]
            if chapter_number(args.chapter) >= 10
            else []
        ),
        ("reader-feedback", ["reader-feedback", "summarize", args.chapter], review_dir / "reader_feedback.json"),
        ("reader-risk-index", ["reader-risk-index", "--to", args.chapter, "--write"], ROOT / "state" / "derived" / "reader_risk" / "latest.json"),
        ("revision-plan", ["revision-plan", args.chapter], review_dir / "revision_plan.json"),
        ("revision-closure", ["revision-closure", args.chapter], None),
        ("review-summary", ["review-summary", args.chapter, "--write"], review_dir / "review_summary.json"),
        ("chapter-evidence", ["evidence", args.chapter], None),
    ]
    for name, command, primary in command_steps:
        required_keys = ROUTED_STEP_KEYS.get(name)
        if required_keys is not None and not (route_reviews & required_keys) and route_name not in {"heavy", "gate"}:
            steps.append({"name": name, "command": ["python", "scripts/novel.py", *command], "status": "SKIPPED", "returncode": 0, "output": f"route {route_name.upper()} skipped routed literary step", "artifacts": [rel(primary)] if primary else []})
            continue
        skip, stale_reason = should_skip(primary, args.resume, name=name, chapter=args.chapter)
        if skip:
            steps.append({"name": name, "command": ["python", "scripts/novel.py", *command], "status": "SKIPPED", "returncode": 0, "output": f"resume kept {rel(primary)}", "artifacts": [rel(primary)]})
            continue
        result = run_command(name, command)
        if stale_reason:
            result["output"] = f"resume reran because {stale_reason}\n{result['output']}".strip()
        if name == "reader-feedback" and result["returncode"] != 0:
            result["status"] = "WARNING"
        steps.append(result)

    if not has_chapter_anchor(args.chapter):
        steps.append(
            {
                "name": "chapter_anchor",
                "command": [],
                "status": "NOT_READY",
                "returncode": 1,
                "output": "missing human-verified chapter_anchor event",
                "artifacts": ["state/event_ledger.jsonl"],
            }
        )

    failed = [step for step in steps if step["status"] not in {"READY", "SKIPPED", "WARNING"}]
    return {
        "schema_version": 1,
        "chapter": args.chapter,
        "generated_at": now_iso(),
        "status": "READY" if not failed else "NOT_READY",
        "input_hashes": control_input_hashes(args.chapter),
        "steps": steps,
        "next_action": next_action(args.chapter, failed),
    }


def next_action(chapter: str, failed: list[dict[str, Any]]) -> str:
    if not failed:
        return f"Run `python scripts/novel.py close {chapter} --decision Ship ...` after human editor confirms."
    first = failed[0]["name"]
    mapping = {
        "candidate_selection": f"Run `python scripts/novel.py select-candidate {chapter} --choice ...`.",
        "chapter_landing": f"Run `python scripts/novel.py land {chapter} --selected-direction ... --attestation ...`.",
        "codex_integrated_review": f"Run `python scripts/novel.py codex-review-start {chapter}`, then write the independent Codex review.",
        "codex_anti_ai_review": f"Run `python scripts/novel.py codex-anti-ai-review-start {chapter}`, then complete the isolated Codex anti-AI review.",
        "codex_semantic_reader_review": f"Run `python scripts/novel.py codex-semantic-reader-review-start {chapter}`, then complete the isolated Codex semantic reader review.",
        "deepseek_integrated_review": f"Run `python scripts/novel.py review {chapter} --deepseek`.",
        "deepseek_anti_ai_review": f"Run `python scripts/novel.py deepseek-anti-ai-review {chapter}`.",
        "deepseek_semantic_reader_review": f"Run `python scripts/novel.py deepseek-semantic-reader-review {chapter}`.",
        "chapter_anchor": f"Run `python scripts/novel.py event {chapter} --type chapter_anchor ...`.",
    }
    return mapping.get(first, f"Fix `{first}` and rerun `python scripts/novel.py receive-chapter {chapter} --resume`.")


def render_markdown(report: dict[str, Any], *, verbose: bool = False) -> str:
    failed = [step for step in report.get("steps", []) if step.get("status") not in {"READY", "SKIPPED", "WARNING"}]
    if not verbose:
        first = failed[0]["name"] if failed else "none"
        route = "UNKNOWN"
        route_path = ROOT / "reviews" / report["chapter"] / "review_route.json"
        if route_path.exists():
            try:
                route_data = read_json(route_path, {})
                if isinstance(route_data, dict):
                    route = str(route_data.get("route", "unknown")).upper()
            except Exception:
                route = "INVALID"
        return "\n".join(
            [
                f"status: {report['status']}",
                f"route: {route}",
                f"first_blocker: {first}",
                f"next: {report.get('next_action', '')}",
                f"failed_steps: {len(failed)}",
            ]
        ).rstrip() + "\n"
    lines = [
        f"# Receive Chapter: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"next_action: {report.get('next_action', '')}",
        "",
        "## Steps",
        "",
    ]
    for step in report.get("steps", []):
        command = " ".join(step.get("command") or [])
        lines.append(f"- {step.get('name')}: {step.get('status')} rc={step.get('returncode')} command={command or 'n/a'}")
        output = str(step.get("output", "")).strip().splitlines()
        if output:
            lines.append(f"  output: {output[0][:180]}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full receive-chapter control plane without auto-shipping.")
    parser.add_argument("chapter")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Show the full receive step plan in preview output.")
    parser.add_argument("--run-deepseek", action="store_true", help="Call live DeepSeek review steps when their artifacts are missing.")
    args = parser.parse_args()
    report = evaluate(args)
    if args.preview:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    out_dir = ROOT / "reviews" / args.chapter
    write_json(out_dir / "receive_chapter.json", report)
    write_text(out_dir / "receive_chapter.md", render_markdown(report, verbose=args.verbose))
    print(render_markdown(report, verbose=args.verbose), end="")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
