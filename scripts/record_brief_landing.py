from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_json, write_blocked_by_locks, write_json, write_text
from brief_check import check_brief


SOURCES = ["Codex", "DeepSeek", "Mixed", "Manual"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def input_item(path: Path) -> dict:
    return {"path": rel(path), "sha256": sha256(path)}


def candidate_path(chapter: str, source: str) -> Path:
    return ROOT / "drafts" / source.lower() / f"{chapter}_brief.md"


def normalized_text(path: Path) -> str:
    return "".join(path.read_text(encoding="utf-8").split())


def matching_candidate(brief: Path, selection: dict) -> Path | None:
    official_hash = sha256(brief)
    official_normalized = normalized_text(brief)
    for item in selection.get("selected_candidates", []):
        path = ROOT / str(item.get("path", ""))
        if not path.exists():
            continue
        if sha256(path) == official_hash or normalized_text(path) == official_normalized:
            return path
    return None


def validate_selection_source(source: str, selection: dict) -> list[str]:
    choice = selection.get("choice")
    if choice in {"Rewrite brief", "No usable brief"}:
        return [f"brief selection choice {choice!r} cannot be landed"]
    if source == "Manual":
        return [] if choice in {"Manual", "Mixed", "Codex", "DeepSeek"} else ["invalid brief selection for manual landing"]
    if source == "Mixed":
        return [] if choice == "Mixed" else ["Mixed brief landing requires Mixed brief selection"]
    return [] if choice in {source, "Mixed"} else [f"{source} brief landing requires {source} or Mixed brief selection"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Record provenance for the official chapter brief landing.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--source", required=True, choices=SOURCES)
    parser.add_argument("--from-candidate", choices=["Codex", "DeepSeek"], default=None)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("official brief landing"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    attestation = args.attestation.strip()
    if not attestation:
        print("ERROR: --attestation must not be empty.", file=sys.stderr)
        return 1

    brief = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    selection_path = ROOT / "state" / "selections" / f"{args.chapter}_brief.json"
    if not selection_path.exists():
        print(f"ERROR: missing brief selection: {selection_path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    selection = read_json(selection_path, {})
    for error in validate_selection_source(args.source, selection):
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    copied_from: Path | None = None
    if args.from_candidate:
        copied_from = candidate_path(args.chapter, args.from_candidate)
        if not copied_from.exists() or not copied_from.read_text(encoding="utf-8").strip():
            print(f"ERROR: missing brief candidate: {copied_from.relative_to(ROOT)}", file=sys.stderr)
            return 1
        write_text(brief, copied_from.read_text(encoding="utf-8"))

    failures = check_brief(brief)
    if failures:
        for failure in failures:
            print(f"ERROR: official brief is not ready: {failure}", file=sys.stderr)
        return 1

    inputs: list[dict] = []
    pack = ROOT / "state" / "context_pack" / f"{args.chapter}_brief.md"
    if pack.exists():
        inputs.append(input_item(pack))
    inputs.append(input_item(selection_path))
    for item in selection.get("selected_candidates", []):
        path = ROOT / str(item.get("path", ""))
        if path.exists():
            inputs.append(input_item(path))

    matched = matching_candidate(brief, selection)
    official = input_item(brief)
    record = {
        "chapter": args.chapter,
        "recorded_at": now_iso(),
        "source": args.source,
        "landed_by": "Codex",
        "attestation": attestation,
        "notes": args.notes,
        "copied_from_candidate": input_item(copied_from) if copied_from is not None else None,
        "direct_candidate_match": input_item(matched) if matched is not None else None,
        "inputs": inputs,
        "official_brief": official,
    }
    out_json = ROOT / "reviews" / args.chapter / "brief_landing.json"
    out_md = ROOT / "reviews" / args.chapter / "brief_landing.md"
    write_json(out_json, record)

    lines = [
        f"# Brief Landing: {args.chapter}",
        "",
        f"source: {args.source}",
        "landed_by: Codex",
        "",
        "## Attestation",
        "",
        attestation,
        "",
        "## Official Brief",
        "",
        f"- `{official['path']}` sha256={official['sha256']}",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- `{item['path']}` sha256={item['sha256']}" for item in inputs)
    if copied_from is not None:
        lines.extend(["", "## Copied From Candidate", "", f"- `{rel(copied_from)}` sha256={sha256(copied_from)}"])
    if args.notes.strip():
        lines.extend(["", "## Notes", "", args.notes.strip()])
    write_text(out_md, "\n".join(lines) + "\n")
    print(f"OK: wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
