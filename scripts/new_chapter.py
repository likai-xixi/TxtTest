from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_text, unresolved_locks, write_json, write_text
from gate_policy import gate_errors_for_chapter
from migrate_anti_ai_reviews import ai_taste_draft, codex_anti_ai_draft, deepseek_anti_ai_draft, dialogue_draft


REVIEW_TEMPLATES = [
    "brief_candidate_selection.md",
    "candidate_selection.md",
    "codex_integrated_review.md",
    "deepseek_integrated_review.md",
    "continuity.md",
    "model_disagreement.md",
    "decision.md",
    "revision.md",
    "revision_plan.md",
    "review_arbitration.md",
    "gray_consequence.md",
    "chapter_shape.md",
    "prose_risk.md",
    "reader_reward_gate.md",
    "reader_feedback.md",
    "human_flavor.md",
    "highlights_review.md",
    "receive_chapter.md",
    "ai_taste.md",
    "dialogue_function.md",
    "emotion_relationship_gate.md",
    "semantic_reader_review.md",
    "codex_semantic_reader_review.md",
    "deepseek_semantic_reader_review.md",
    "memorable_scene.md",
    "codex_anti_ai_review.md",
    "deepseek_anti_ai_review.md",
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
]


def render_template(name: str, chapter: str) -> str:
    template_path = ROOT / "templates" / name
    text = read_text(template_path)
    if not text:
        raise FileNotFoundError(template_path)
    return text.replace("{chapter}", chapter)


def write_if_allowed(path: Path, text: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    write_text(path, text)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Create brief/review workspace for a chapter.")
    parser.add_argument("--chapter", required=True, help="Chapter id like v01_c002.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    args = parser.parse_args()

    locks = unresolved_locks()
    if locks:
        print("ERROR: unresolved stop locks block new chapters:", file=sys.stderr)
        for lock in locks:
            print(f"  - {lock.get('id')}: {lock.get('reason')}", file=sys.stderr)
        return 1

    gate_errors = gate_errors_for_chapter(args.chapter, "creating")
    if gate_errors:
        for error in gate_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    volume, _chapter_file = chapter_parts(args.chapter)
    created: list[str] = []
    skipped: list[str] = []

    for directory in [
        ROOT / "chapters" / volume,
        ROOT / "drafts" / "codex",
        ROOT / "drafts" / "deepseek",
        ROOT / "external_runs" / "deepseek" / args.chapter,
        ROOT / "reviews" / args.chapter,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    brief = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    if write_if_allowed(brief, render_template("chapter_brief.md", args.chapter), args.force):
        created.append(str(brief.relative_to(ROOT)))
    else:
        skipped.append(str(brief.relative_to(ROOT)))

    for name in REVIEW_TEMPLATES:
        path = ROOT / "reviews" / args.chapter / name
        if write_if_allowed(path, render_template(name, args.chapter), args.force):
            created.append(str(path.relative_to(ROOT)))
        else:
            skipped.append(str(path.relative_to(ROOT)))

    for name, data in {
        "ai_taste.json": ai_taste_draft(args.chapter),
        "dialogue_function.json": dialogue_draft(args.chapter),
        "emotion_relationship_gate.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "checks": {},
            "evidence_quotes": [],
            "blockers": ["run emotion-relationship-gate after landing the official chapter"],
            "warnings": [],
            "human_acceptance": None,
        },
        "semantic_reader_review.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "reviewer": "codex_deepseek_semantic_reader_aggregate",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "source_reviews": {},
            "categories": {},
            "blockers": ["run codex-semantic-reader-review-start, complete Codex semantic review, run deepseek-semantic-reader-review, then run semantic-reader-review"],
            "warnings": [],
            "human_acceptance": None,
        },
        "codex_semantic_reader_review.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "reviewer": "codex_semantic_reader_subagent",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "categories": {},
            "scene_samples": [],
            "blockers": ["run codex-semantic-reader-review-start and complete the isolated Codex LLM semantic review"],
            "warnings": [],
            "human_acceptance": None,
        },
        "deepseek_semantic_reader_review.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "reviewer": "deepseek_semantic_reader",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "categories": {},
            "scene_samples": [],
            "blockers": ["run deepseek-semantic-reader-review after landing the official chapter"],
            "warnings": [],
            "human_acceptance": None,
        },
        "memorable_scene.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "checks": {},
            "evidence_quotes": [],
            "blockers": ["run memorable-scene-check after landing the official chapter"],
            "warnings": [],
            "human_acceptance": None,
        },
        "codex_anti_ai_review.json": codex_anti_ai_draft(args.chapter),
        "deepseek_anti_ai_review.json": deepseek_anti_ai_draft(args.chapter),
        "revision_plan.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "input_hashes": [],
            "must_fix": [],
            "should_fix": [],
            "human_acceptance_allowed": [],
        },
        "review_arbitration.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NEEDS_HUMAN",
            "recommendation": "Human arbitration required.",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "input_hashes": [],
            "codex_action": "UNKNOWN",
            "deepseek_action": "UNKNOWN",
            "blockers": [],
            "warnings": [],
            "human_acceptance": None,
        },
        "gray_consequence.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "gray_markers": [],
            "high_impact_markers": [],
            "obligations": [],
            "blockers": [],
            "warnings": [],
        },
        "chapter_shape.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "shape": {},
            "shape_key": "",
            "repeat_count": 0,
            "blockers": [],
            "warnings": [],
            "human_acceptance": None,
        },
        "prose_risk.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "official_brief": {"path": f"outline/chapter_briefs/{args.chapter}.md", "sha256": ""},
            "input_hashes": [],
            "categories": {},
            "metrics": {},
            "blockers": ["run prose-risk-check after landing the official chapter"],
            "warnings": [],
            "human_acceptance": None,
        },
        "reader_reward_gate.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "BLOCKED",
            "reader_reward_intensity": "R0",
            "configured_intensity": "",
            "intensity_source": "",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "official_brief": {"path": f"outline/chapter_briefs/{args.chapter}.md", "sha256": ""},
            "input_hashes": [],
            "policy_rules": {},
            "contract": {},
            "evidence_quotes": [],
            "matched_evidence_quotes": [],
            "blockers": ["Run reader-reward-check after official brief and chapter exist."],
            "warnings": [],
            "human_acceptance": None,
        },
        "reader_feedback.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "WARNING",
            "response_count": 0,
            "stuck_points": [],
            "continue_reasons": [],
            "reader_promise_gaps": [],
            "risk": "No chapter reader feedback recorded yet.",
            "recommendation": "Use feedback only as reader-experience evidence.",
            "human_acceptance": None,
        },
        "human_flavor.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "official_brief": {"path": f"outline/chapter_briefs/{args.chapter}.md", "sha256": ""},
            "input_hashes": [],
            "signals": {},
            "window": {},
            "evidence_quotes": [],
            "warnings": [],
            "blockers": ["run human-flavor-check after landing the official chapter"],
        },
        "highlights_review.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "sha256": ""},
            "input_hashes": [],
            "protected_highlights": [],
            "warnings": [],
            "blockers": ["run highlights-review after landing the official chapter"],
        },
        "review_route.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "route": "heavy",
            "route_version": 1,
            "generated_at": now_iso(),
            "status": "BLOCKED",
            "official_chapter": {"path": f"chapters/{volume}/c{args.chapter[-3:]}.md", "exists": False, "sha256": ""},
            "official_brief": {"path": f"outline/chapter_briefs/{args.chapter}.md", "exists": False, "sha256": ""},
            "context_manifest": {"path": f"state/context_pack/{args.chapter}.manifest.json", "exists": False, "sha256": ""},
            "source_event_ledger": {"path": "state/event_ledger.jsonl", "exists": False, "sha256": ""},
            "routing_inputs": [],
            "fail_closed": True,
            "always_required_ship_gates": [],
            "additional_literary_reviews": [],
            "reasons": [],
            "warnings": [],
            "blockers": ["run route-reviews after official chapter, brief, context manifest, and ledger exist"],
        },
        "review_summary.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "暂停",
            "route": "HEAVY",
            "ship_gates": "BLOCKED",
            "one_line_decision": "轻审可先运行 review-summary --preview-route；Ship 前必须落 review_route.json。",
            "must_fix": [],
            "must_preserve": [],
            "ai_risk": {"status": "MISSING", "sources": [], "issues": ["run review-summary after route reviews"]},
            "input_hashes": [],
        },
        "receive_chapter.json": {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "input_hashes": [],
            "steps": [],
            "next_action": "Run receive-chapter after official chapter landing.",
        },
    }.items():
        path = ROOT / "reviews" / args.chapter / name
        if path.exists() and not args.force:
            skipped.append(str(path.relative_to(ROOT)))
        else:
            write_json(path, data)
            created.append(str(path.relative_to(ROOT)))

    for item in created:
        print(f"created: {item}")
    for item in skipped:
        print(f"skipped existing: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
