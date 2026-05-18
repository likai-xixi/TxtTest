from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, write_blocked_by_locks, write_json, write_text


CHOICES = ["Codex", "DeepSeek", "Mixed", "Manual", "Rewrite brief", "No usable brief"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_paths(chapter: str, choice: str) -> list[Path]:
    paths: list[Path] = []
    if choice in {"Codex", "Mixed"}:
        paths.append(ROOT / "drafts" / "codex" / f"{chapter}_brief.md")
    if choice in {"DeepSeek", "Mixed"}:
        paths.append(ROOT / "drafts" / "deepseek" / f"{chapter}_brief.md")
    return paths


def collect_candidates(chapter: str, choice: str) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    for path in candidate_paths(chapter, choice):
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing non-empty selected brief candidate: {path.relative_to(ROOT)}")
            continue
        candidates.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)})
    return candidates, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the human-selected chapter brief direction.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--adopt", default="")
    parser.add_argument("--reject", default="")
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("brief candidate selection recording"):
        return 1

    chapter_parts(args.chapter)
    candidates, errors = collect_candidates(args.chapter, args.choice)
    if args.choice == "Mixed" and not args.mixed_strategy.strip():
        errors.append("Mixed brief selection requires --mixed-strategy.")
    if args.choice in {"Codex", "DeepSeek", "Mixed"} and not candidates:
        errors.append("selected brief choice requires at least one brief candidate file.")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    selected_at = now_iso()
    record = {
        "chapter": args.chapter,
        "selected_at": selected_at,
        "choice": args.choice,
        "reason": args.reason,
        "adopt": args.adopt,
        "reject": args.reject,
        "mixed_strategy": args.mixed_strategy,
        "selected_candidates": candidates,
        "notes": args.notes.strip() or "无。",
        "human_decision_required": True,
        "official_brief_requires_landing": True,
    }
    lines = [
        f"# Brief Candidate Selection: {args.chapter}",
        "",
        f"selected_at: {selected_at}",
        f"choice: {args.choice}",
        "",
        "## Reason",
        "",
        args.reason,
        "",
        "## Selected Brief Candidates",
        "",
    ]
    if candidates:
        lines.extend(f"- `{item['path']}` sha256={item['sha256']}" for item in candidates)
    else:
        lines.append("无。")
    lines.extend(
        [
            "",
            "## Adopt",
            "",
            args.adopt.strip() or "无。",
            "",
            "## Reject",
            "",
            args.reject.strip() or "无。",
            "",
            "## Mixed Strategy",
            "",
            args.mixed_strategy.strip() or "无。",
            "",
            "## Notes",
            "",
            args.notes.strip() or "无。",
            "",
            "## Boundary",
            "",
            "- Codex / DeepSeek brief outputs are candidates only.",
            "- The official brief must be landed by Codex after human selection / mixed edit.",
            "- This record does not change canon, chapters, or event ledger.",
            "",
            "## Allowed Choices",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in CHOICES)
    out = ROOT / "reviews" / args.chapter / "brief_candidate_selection.md"
    write_text(out, "\n".join(lines) + "\n")
    write_json(ROOT / "state" / "selections" / f"{args.chapter}_brief.json", record)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
