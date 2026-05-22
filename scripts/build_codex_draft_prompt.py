from __future__ import annotations

import argparse
import sys

from _common import ROOT, chapter_parts, read_text, write_blocked_by_locks, write_text
from candidate_style_requirements import build_prompt_manifest, prompt_paths, render_requirements, write_prompt_manifest
from context_governance import context_quality_path
from context_pack_quality import write_quality_report
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from drafting_prompt_context import filtered_brief_for_drafting, sanitize_context_pack_for_drafting


def drafting_brief_block(brief: str) -> str:
    return filtered_brief_for_drafting(brief)


def compose_prompt(chapter: str, style_block: str, brief: str, context: str) -> str:
    return "\n\n".join(
        [
            style_block.strip(),
            drafting_brief_block(brief),
            "# Context Pack\n\n" + sanitize_context_pack_for_drafting(context),
            "# Codex Candidate Draft Output Requirements\n\n"
            "- Write only the candidate chapter prose for this chapter.\n"
            "- Do not claim the text is canon or final.\n"
            "- Do not update canon, event ledger, state files, reviews, or chapter landing records.\n"
            "- Use only the Official Story Card, Hard Boundaries, and context pack, with the Candidate Style Requirements as the top-level voice constraint.\n"
            "- Begin from visible action, pressure, abnormality, misjudgment, or conflict.\n"
            "- The midpoint must change the situation; do not let the chapter proceed exactly as planned.\n"
            "- Deliver the reader reward promised in the Story Card with visible prose evidence.\n"
            "- Show world rules through choices, misuse, costs, or ordinary-person reactions instead of explanation blocks.\n"
            "- Do not narrate in terms like 本章、合同、证据、门禁、流程 unless those words naturally appear inside the story world.\n"
            "- If any required style, fact, or authorization input is missing or contradictory, stop and list the blocker instead of drafting.\n",
        ]
    ).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Codex candidate chapter draft prompt and manifest.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    if write_blocked_by_locks("Codex draft prompt generation"):
        return 1
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1

    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    for path in (context_path, brief_path):
        if not path.exists() or not read_text(path).strip():
            print(f"ERROR: missing non-empty input: {path.relative_to(ROOT)}", file=sys.stderr)
            return 1

    quality_path = context_quality_path(args.chapter)
    quality = write_quality_report(args.chapter)
    if quality.get("status") != "READY":
        print(
            f"ERROR: context pack quality is not READY: {quality_path.relative_to(ROOT)}. "
            "Run `python scripts/novel.py start ...` after fixing context inputs.",
            file=sys.stderr,
        )
        return 1

    style_result = render_requirements(args.chapter)
    prompt_path, manifest_path = prompt_paths(args.chapter, "Codex")
    prompt_text = compose_prompt(args.chapter, style_result["block"], read_text(brief_path), read_text(context_path))
    if style_result.get("status") != "READY":
        for blocker in style_result.get("blockers", []):
            print(f"ERROR: {blocker}", file=sys.stderr)
        return 1

    write_text(prompt_path, prompt_text)
    manifest = build_prompt_manifest(
        chapter=args.chapter,
        provider="Codex",
        prompt_path=prompt_path,
        prompt_text=prompt_text,
        style_result=style_result,
        candidate_written=False,
    )
    write_prompt_manifest(manifest_path, manifest)
    print(f"OK: wrote {prompt_path.relative_to(ROOT)}")
    print(f"OK: wrote {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
