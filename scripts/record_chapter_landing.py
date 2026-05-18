from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_json, write_blocked_by_locks, write_json, write_text
from context_governance import context_quality_path
from context_pack_quality import write_quality_report


SOURCES = ["Codex", "DeepSeek", "Mixed"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def input_item(path: Path) -> dict:
    return {"path": rel(path), "sha256": sha256(path)}


def normalized_text(path: Path) -> str:
    return "".join(path.read_text(encoding="utf-8").split())


def selected_deepseek_candidates(selection: dict) -> list[Path]:
    candidates: list[Path] = []
    for item in selection.get("selected_candidates", []):
        rel_path = str(item.get("path", ""))
        if rel_path.startswith("drafts/deepseek/"):
            candidates.append(ROOT / rel_path)
    return candidates


def chapter_matches_deepseek_candidate(chapter_path: Path, selection: dict) -> Path | None:
    chapter_hash = sha256(chapter_path)
    chapter_normalized = normalized_text(chapter_path)
    for candidate_path in selected_deepseek_candidates(selection):
        if not candidate_path.exists():
            continue
        if chapter_hash == sha256(candidate_path):
            return candidate_path
        if chapter_normalized and chapter_normalized == normalized_text(candidate_path):
            return candidate_path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Record provenance for the official chapter landing.")
    parser.add_argument("--chapter", required=True)
    direction = parser.add_mutually_exclusive_group(required=True)
    direction.add_argument("--selected-direction", choices=SOURCES)
    direction.add_argument("--source", choices=SOURCES, help="Legacy alias for --selected-direction.")
    parser.add_argument(
        "--attestation",
        required=True,
        help="Human/Codex note confirming why the official chapter can be landed.",
    )
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    selected_direction = args.selected_direction or args.source

    if write_blocked_by_locks("official chapter landing"):
        return 1

    try:
        volume, chapter_file = chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    attestation = args.attestation.strip()
    if not attestation:
        print("ERROR: --attestation must not be empty.", file=sys.stderr)
        return 1

    chapter_path = ROOT / "chapters" / volume / chapter_file
    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    quality_path = context_quality_path(args.chapter)
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    selection_path = ROOT / "state" / "selections" / f"{args.chapter}.json"

    required = [chapter_path, context_path, quality_path, brief_path]
    missing = [path for path in required if not path.exists() or not path.read_text(encoding="utf-8").strip()]
    if missing:
        for path in missing:
            print(f"ERROR: missing landing input: {rel(path)}", file=sys.stderr)
        return 1
    quality = write_quality_report(args.chapter)
    if quality.get("status") != "READY":
        print(f"ERROR: context quality is not READY: {rel(quality_path)}", file=sys.stderr)
        return 1

    inputs = [input_item(context_path), input_item(quality_path), input_item(brief_path)]
    selection = read_json(selection_path, {})
    if selection_path.exists():
        inputs.append(input_item(selection_path))
    for item in selection.get("selected_candidates", []):
        candidate_path = ROOT / str(item.get("path", ""))
        if candidate_path.exists():
            inputs.append(input_item(candidate_path))

    matched = chapter_matches_deepseek_candidate(chapter_path, selection)
    deepseek_direct_adoption = matched is not None
    if deepseek_direct_adoption and selection.get("choice") != "DeepSeek":
        print(
            f"ERROR: official chapter matches selected DeepSeek candidate {rel(matched)}; "
            'record the candidate choice as DeepSeek before direct adoption.',
            file=sys.stderr,
        )
        return 1
    if deepseek_direct_adoption and selected_direction != "DeepSeek":
        print(
            f"ERROR: official chapter matches selected DeepSeek candidate {rel(matched)}; "
            'use --selected-direction DeepSeek for direct adoption, or revise the official chapter before landing.',
            file=sys.stderr,
        )
        return 1

    official = input_item(chapter_path)
    record = {
        "chapter": args.chapter,
        "recorded_at": now_iso(),
        "selected_direction": selected_direction,
        "source": selected_direction,
        "official_source": selected_direction,
        "landed_by": "Codex",
        "integrated_by": "Codex",
        "integration_mode": "deepseek_direct" if deepseek_direct_adoption else "codex_integrated",
        "attestation": attestation,
        "notes": args.notes,
        "codex_integrated": not deepseek_direct_adoption,
        "deepseek_direct_adoption": deepseek_direct_adoption,
        "direct_deepseek_candidate": input_item(matched) if matched is not None else None,
        "inputs": inputs,
        "official_chapter": official,
    }

    out_json = ROOT / "reviews" / args.chapter / "chapter_landing.json"
    out_md = ROOT / "reviews" / args.chapter / "chapter_landing.md"
    write_json(out_json, record)

    lines = [
        f"# Chapter Landing: {args.chapter}",
        "",
        f"selected_direction: {selected_direction}",
        f"official_source: {selected_direction}",
        "landed_by: Codex",
        "integrated_by: Codex",
        f"integration_mode: {record['integration_mode']}",
        f"codex_integrated: {str(record['codex_integrated']).lower()}",
        f"deepseek_direct_adoption: {str(deepseek_direct_adoption).lower()}",
        "",
        "## Attestation",
        "",
        attestation,
        "",
        "## Official Chapter",
        "",
        f"- `{official['path']}` sha256={official['sha256']}",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- `{item['path']}` sha256={item['sha256']}" for item in inputs)
    if matched is not None:
        lines.extend(["", "## Direct DeepSeek Candidate", "", f"- `{rel(matched)}` sha256={sha256(matched)}"])
    if args.notes.strip():
        lines.extend(["", "## Notes", "", args.notes.strip()])
    write_text(out_md, "\n".join(lines) + "\n")
    print(f"OK: wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
