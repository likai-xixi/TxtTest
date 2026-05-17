from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_json, write_blocked_by_locks, write_json, write_text


SOURCES = ["Codex", "DeepSeek", "Mixed"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def input_item(path: Path) -> dict:
    return {"path": rel(path), "sha256": sha256(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record provenance for the official chapter landing.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--source", required=True, choices=SOURCES)
    parser.add_argument("--attestation", required=True, help="Human/Codex note confirming the official chapter was integrated, not copied blindly.")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

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
    brief_path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    selection_path = ROOT / "state" / "selections" / f"{args.chapter}.json"

    required = [chapter_path, context_path, brief_path]
    missing = [path for path in required if not path.exists() or not path.read_text(encoding="utf-8").strip()]
    if missing:
        for path in missing:
            print(f"ERROR: missing landing input: {rel(path)}", file=sys.stderr)
        return 1

    inputs = [input_item(context_path), input_item(brief_path)]
    selection = read_json(selection_path, {})
    if selection_path.exists():
        inputs.append(input_item(selection_path))
    for item in selection.get("selected_candidates", []):
        candidate_path = ROOT / str(item.get("path", ""))
        if candidate_path.exists():
            inputs.append(input_item(candidate_path))

    official = input_item(chapter_path)
    record = {
        "chapter": args.chapter,
        "recorded_at": now_iso(),
        "source": args.source,
        "attestation": attestation,
        "notes": args.notes,
        "codex_integrated": True,
        "not_direct_deepseek_copy": True,
        "inputs": inputs,
        "official_chapter": official,
    }

    out_json = ROOT / "reviews" / args.chapter / "chapter_landing.json"
    out_md = ROOT / "reviews" / args.chapter / "chapter_landing.md"
    write_json(out_json, record)

    lines = [
        f"# Chapter Landing: {args.chapter}",
        "",
        f"source: {args.source}",
        "codex_integrated: true",
        "not_direct_deepseek_copy: true",
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
    if args.notes.strip():
        lines.extend(["", "## Notes", "", args.notes.strip()])
    write_text(out_md, "\n".join(lines) + "\n")
    print(f"OK: wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
