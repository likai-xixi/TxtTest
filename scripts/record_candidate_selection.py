from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, write_blocked_by_locks, write_json, write_text


CHOICES = ["Codex", "DeepSeek", "Mixed", "Rewrite brief", "No usable candidate"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_paths(chapter: str, choice: str) -> list[Path]:
    paths: list[Path] = []
    if choice in {"Codex", "Mixed"}:
        paths.append(ROOT / "drafts" / "codex" / f"{chapter}.md")
    if choice in {"DeepSeek", "Mixed"}:
        paths.append(ROOT / "drafts" / "deepseek" / f"{chapter}.md")
    return paths


def collect_candidates(chapter: str, choice: str) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    for path in candidate_paths(chapter, choice):
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing non-empty selected candidate: {path.relative_to(ROOT)}")
            continue
        candidates.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)})
    return candidates, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the human-selected candidate direction for a chapter.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--adopt", default="")
    parser.add_argument("--reject", default="")
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("candidate selection recording"):
        return 1

    chapter_parts(args.chapter)
    candidates, errors = collect_candidates(args.chapter, args.choice)
    if args.choice == "Mixed" and not args.mixed_strategy.strip():
        errors.append("Mixed selection requires --mixed-strategy.")
    if args.choice not in {"Rewrite brief", "No usable candidate"} and not candidates:
        errors.append("selected candidate choice requires at least one candidate file.")
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
        "deepseek_is_candidate_only": True,
    }
    lines = [
        f"# Candidate Selection: {args.chapter}",
        "",
        f"selected_at: {selected_at}",
        f"choice: {args.choice}",
        "",
        "## Reason",
        "",
        args.reason,
        "",
        "## Selected Candidates",
        "",
    ]
    if candidates:
        for candidate in candidates:
            lines.append(f"- `{candidate['path']}` sha256={candidate['sha256']}")
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
        ]
    )
    lines.extend([
        "## Notes",
        "",
        args.notes.strip() or "无。",
        "",
        "## Boundary",
        "",
        "- DeepSeek output remains candidate material.",
        "- Codex must integrate or rewrite before anything lands in `chapters/`.",
        "- This record does not change canon, state, or event ledger.",
        "",
        "## Allowed Choices",
        "",
    ])
    lines.extend(f"- {item}" for item in CHOICES)
    out = ROOT / "reviews" / args.chapter / "candidate_selection.md"
    write_text(out, "\n".join(lines) + "\n")
    write_json(ROOT / "state" / "selections" / f"{args.chapter}.json", record)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
