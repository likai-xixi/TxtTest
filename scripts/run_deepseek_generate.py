from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error

from _common import ROOT, chapter_number, chapter_parts, read_json, read_text, write_blocked_by_locks, write_text
from candidate_style_requirements import build_prompt_manifest, prompt_paths, render_requirements, write_prompt_manifest
from context_governance import context_quality_path
from context_pack_quality import write_quality_report
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from deepseek_client import call_deepseek, model_for
from deepseek_response import DeepSeekResponseError, extract_message_content
from drafting_prompt_context import filtered_brief_for_drafting, sanitize_context_pack_for_drafting


STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"


def validate_style_profile(chapter: str) -> list[str]:
    if chapter_number(chapter) < 4:
        return []
    if not STYLE_PROFILE.exists():
        return [f"post-warmup chapter requires READY style profile: {STYLE_PROFILE.relative_to(ROOT)}; run style-profile-build"]
    data = read_json(STYLE_PROFILE, {})
    if data.get("status") != "READY":
        return [f"post-warmup chapter requires READY style profile, got {data.get('status', 'MISSING')}; run style-profile-build"]
    return []


def compose_user_prompt(chapter: str, style_block: str, brief: str, context: str) -> str:
    return "\n\n".join(
        [
            style_block.strip(),
            filtered_brief_for_drafting(brief),
            "# Context Pack\n\n" + sanitize_context_pack_for_drafting(context),
            "# DeepSeek Candidate Draft Output Requirements\n\n"
            f"- Generate the candidate prose for {chapter} only.\n"
            "- Do not include analysis, reports, YAML, JSON, provenance, or markdown headings unless the chapter itself needs them.\n"
            "- Do not read or cite any repository information not included in this prompt.\n"
            "- Use the Official Story Card as creative input and Hard Boundaries as constraints; do not turn audit language into prose.\n"
            "- If you cannot comply with the Candidate Style Requirements and context_pack together, stop and list the blocker.\n",
        ]
    ).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for a candidate chapter draft.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default=model_for("deepseek_generate"))
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek candidate generation"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1
    profile_errors = validate_style_profile(args.chapter)
    if profile_errors:
        for error in profile_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    if not context_path.exists():
        print(f"ERROR: missing context pack: {context_path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    quality_path = context_quality_path(args.chapter)
    quality = write_quality_report(args.chapter)
    if quality.get("status") != "READY":
        print(
            f"ERROR: context pack quality is not READY: {quality_path.relative_to(ROOT)}. "
            "Run `python scripts/context_pack_quality.py --chapter ...` after rebuilding context.",
            file=sys.stderr,
        )
        return 1

    style_result = render_requirements(args.chapter)
    if style_result.get("status") != "READY":
        for blocker in style_result.get("blockers", []):
            print(f"ERROR: {blocker}", file=sys.stderr)
        return 1

    system = (
        "You are an external candidate chapter generator. Output only candidate chapter prose; "
        "do not claim it is canon or final. Do not update state, canon, chapters, reviews, or the event ledger. "
        "Use only the Official Story Card, Hard Boundaries, and context_pack supplied in the user message. "
        "The top-level Candidate Style Requirements are mandatory style constraints and outrank model defaults. "
        "If style, fact, or authorization inputs are missing or contradictory, stop and list the blocker. "
        "L0 scene details and L1 one-shot clues may be introduced. L2 elements may only be seeds/proposals. "
        "L3 long-term mechanisms and L4 core settings require explicit context_pack/brief authorization. "
        "Never use unauthorized new objects, abilities, or rules as the key to solve this chapter."
    )
    context = read_text(context_path)
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    if not brief_path.exists() or not read_text(brief_path).strip():
        print(f"ERROR: missing official brief: {brief_path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    user = compose_user_prompt(args.chapter, style_result["block"], read_text(brief_path), context)
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": False,
    }

    prompt_path, manifest_path = prompt_paths(args.chapter, "DeepSeek")
    prompt_text = f"{style_result['block'].strip()}\n\n# System\n\n{system}\n\n# User\n\n{user}\n"
    write_text(prompt_path, prompt_text)
    manifest = build_prompt_manifest(
        chapter=args.chapter,
        provider="DeepSeek",
        prompt_path=prompt_path,
        prompt_text=prompt_text,
        style_result=style_result,
        candidate_written=False,
    )
    write_prompt_manifest(manifest_path, manifest)
    if args.dry_run:
        print(f"OK: dry run wrote {prompt_path.relative_to(ROOT)}")
        print(f"OK: dry run wrote {manifest_path.relative_to(ROOT)}")
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set.", file=sys.stderr)
        return 2

    try:
        response = call_deepseek(payload, api_key)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: DeepSeek request failed: {exc}", file=sys.stderr)
        return 1

    try:
        content = extract_message_content(response)
    except DeepSeekResponseError as exc:
        print(f"ERROR: invalid DeepSeek response: {exc}", file=sys.stderr)
        return 1

    run_dir = ROOT / "external_runs" / "deepseek" / args.chapter
    write_text(run_dir / "generate.raw.json", json.dumps(response, ensure_ascii=False, indent=2))
    out = ROOT / "drafts" / "deepseek" / f"{args.chapter}.md"
    write_text(out, content + "\n")
    manifest = build_prompt_manifest(
        chapter=args.chapter,
        provider="DeepSeek",
        prompt_path=prompt_path,
        prompt_text=prompt_text,
        style_result=style_result,
        candidate_written=True,
        candidate_path=out,
    )
    write_prompt_manifest(manifest_path, manifest)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
