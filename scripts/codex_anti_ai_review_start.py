from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_text, write_blocked_by_locks, write_json, write_text
from context_governance import sha256
from review_context import write_review_context


REVIEW_INPUTS = (
    "state/project_style_contract.json",
    "state/project_style_contract.md",
    "bible/style_guide.md",
    "state/project_reader_promise.json",
    "state/project_reader_promise.md",
    "state/derived/personality/protagonist.json",
    "state/derived/protagonist_progression.json",
    "state/derived/world_reveal_ledger.json",
    "state/derived/suspense_ledger.json",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def file_body(path: Path, limit: int = 5000) -> str:
    if not path.exists():
        return f"[missing: {rel(path)}]"
    text = read_text(path)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def input_paths(chapter: str) -> list[Path]:
    return [
        chapter_path(chapter),
        ROOT / "outline" / "chapter_briefs" / f"{chapter}.md",
        ROOT / "state" / "context_pack" / f"{chapter}.md",
        ROOT / "state" / "context_pack" / f"{chapter}_review_context.md",
        ROOT / "state" / "context_pack" / f"{chapter}_review_context.json",
        *(ROOT / item for item in REVIEW_INPUTS),
    ]


def prompt_for(chapter: str) -> str:
    official = chapter_path(chapter)
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    context = ROOT / "state" / "context_pack" / f"{chapter}.md"
    review_context = ROOT / "state" / "context_pack" / f"{chapter}_review_context.md"
    return "\n\n".join(
        [
            f"# Codex Anti-AI Subagent Prompt: {chapter}",
            "You are a Codex subagent acting as an independent anti-AI-taste fiction reviewer.",
            "Read only the supplied official chapter, official brief, context pack, review context, style contract, reader promise, and derived ledgers.",
            "Do not read DeepSeek reviews, Codex integrated review, ai_taste reports, dialogue_function reports, model_disagreement, review_arbitration, or revision_plan.",
            "Do not modify chapter, canon, event ledger, or candidate files.",
            "Return two artifacts:",
            f"- reviews/{chapter}/codex_anti_ai_review.json",
            f"- reviews/{chapter}/codex_anti_ai_review.md",
            "JSON shape must match schemas/codex_anti_ai_review.schema.json.",
            "Markdown must include status, official_chapter_sha256, review_sha256, Summary, Categories, and Evidence Quotes.",
            "Use BLOCKED for ship-stopping issues. CLEAR requires at least one evidence quote copied from the official chapter.",
            "Check exactly these categories: show_dont_tell, rhythm_disorder, emotional_risk, gray_motive, dialogue_agenda, detail_economy, setting_integration, consequence_integrity.",
            f"# Official Chapter\n\n{file_body(official, 18000)}",
            f"# Official Brief\n\n{file_body(brief, 7000)}",
            f"# Context Pack\n\n{file_body(context, 9000)}",
            f"# Review Context: Structured State And Key Quotes\n\n{file_body(review_context, 8000)}",
            "# Style Contract JSON\n\n" + file_body(ROOT / "state" / "project_style_contract.json", 5000),
            "# Human Style Contract\n\n" + file_body(ROOT / "state" / "project_style_contract.md", 4000),
            "# Style Guide\n\n" + file_body(ROOT / "bible" / "style_guide.md", 4000),
            "# Reader Promise\n\n"
            + file_body(ROOT / "state" / "project_reader_promise.json", 3000)
            + "\n"
            + file_body(ROOT / "state" / "project_reader_promise.md", 3000),
            "# Derived Reader Ledgers\n\n"
            + file_body(ROOT / "state" / "derived" / "personality" / "protagonist.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "protagonist_progression.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "world_reveal_ledger.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "suspense_ledger.json", 2500),
        ]
    ).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an isolated Codex subagent anti-AI review prompt and manifest.")
    parser.add_argument("chapter")
    args = parser.parse_args()

    if write_blocked_by_locks("Codex anti-AI subagent review start"):
        return 1
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    official = chapter_path(args.chapter)
    if not official.exists() or not read_text(official).strip():
        print(f"ERROR: missing official chapter text: {rel(official)}")
        return 1

    write_review_context(args.chapter)
    prompt_path = ROOT / "reviews" / args.chapter / "codex_anti_ai_review_prompt.md"
    manifest_path = ROOT / "reviews" / args.chapter / "codex_anti_ai_review_manifest.json"
    write_text(prompt_path, prompt_for(args.chapter))
    inputs = [path for path in input_paths(args.chapter) if path.exists()]
    manifest = {
        "schema_version": 1,
        "chapter": args.chapter,
        "reviewer": "codex_anti_ai_subagent",
        "generated_at": now_iso(),
        "prompt": ref(prompt_path),
        "inputs": [ref(path) for path in inputs],
        "forbidden_inputs": [
            f"reviews/{args.chapter}/codex_integrated_review.md",
            f"reviews/{args.chapter}/deepseek_integrated_review.md",
            f"reviews/{args.chapter}/deepseek_anti_ai_review.md",
            f"reviews/{args.chapter}/deepseek_anti_ai_review.json",
            f"reviews/{args.chapter}/ai_taste.md",
            f"reviews/{args.chapter}/ai_taste.json",
            f"reviews/{args.chapter}/dialogue_function.md",
            f"reviews/{args.chapter}/dialogue_function.json",
            f"reviews/{args.chapter}/model_disagreement.md",
            f"reviews/{args.chapter}/review_arbitration.md",
            f"reviews/{args.chapter}/review_arbitration.json",
        ],
        "outputs_expected": [
            f"reviews/{args.chapter}/codex_anti_ai_review.json",
            f"reviews/{args.chapter}/codex_anti_ai_review.md",
        ],
        "isolation_attestation": "Codex anti-AI subagent prompt excludes other review reports and uses only chapter, brief, context, review_context, style, reader, and derived state inputs.",
    }
    write_json(manifest_path, manifest)
    print(f"OK: wrote {rel(prompt_path)}")
    print(f"OK: wrote {rel(manifest_path)}")
    print(f"next: run an isolated Codex subagent with {rel(prompt_path)} and write codex_anti_ai_review.md/json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
