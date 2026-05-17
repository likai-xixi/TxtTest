from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, gate_decision, read_text, unresolved_locks, write_text


REVIEW_TEMPLATES = [
    "candidate_selection.md",
    "codex_integrated_review.md",
    "deepseek_integrated_review.md",
    "continuity.md",
    "model_disagreement.md",
    "decision.md",
    "revision.md",
    "ai_taste.md",
    "web_satisfaction.md",
    "retention_risk.md",
    "originality.md",
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

    number = chapter_number(args.chapter)
    if number >= 4 and gate_decision("a") != "continue":
        print("ERROR: Gate A must be recorded as continue before creating chapter 4+.", file=sys.stderr)
        return 1
    if number >= 11 and gate_decision("b") != "continue":
        print("ERROR: Gate B must be recorded as continue before creating chapter 11+.", file=sys.stderr)
        return 1
    if number >= 26 and gate_decision("c") != "continue":
        print("ERROR: Gate C must be recorded as continue before creating chapter 26+.", file=sys.stderr)
        return 1
    if number >= 126 and gate_decision("e") != "continue":
        print("ERROR: Gate E must be recorded as continue before creating chapter 126+.", file=sys.stderr)
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

    for item in created:
        print(f"created: {item}")
    for item in skipped:
        print(f"skipped existing: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
