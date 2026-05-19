from __future__ import annotations

import argparse
import sys

from _common import ROOT, chapter_parts, read_text
from chapter_evidence import ALLOWED_AUXILIARY_STATUS, has_placeholder, status_value


def check(chapter: str) -> tuple[str, list[str], list[str]]:
    path = ROOT / "reviews" / chapter / "similarity_risk.md"
    if not path.exists() or not read_text(path).strip():
        return "WARNING", [], [f"missing reviews/{chapter}/similarity_risk.md"]
    text = read_text(path)
    blockers: list[str] = []
    warnings: list[str] = []
    status = status_value(text)
    if has_placeholder(path):
        warnings.append("similarity_risk still has placeholder text")
    if status in ALLOWED_AUXILIARY_STATUS:
        return ("WARNING" if warnings else "READY"), blockers, warnings
    if status in {"BLOCKED", "HIGH_RISK"}:
        warnings.append(f"similarity_risk status is {status}; chapter evidence will block Ship")
        return "WARNING", blockers, warnings
    warnings.append(f"similarity_risk status is {status or 'MISSING'}")
    return "WARNING", blockers, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize similarity risk advisory status.")
    parser.add_argument("chapter")
    args = parser.parse_args()
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    status, blockers, warnings = check(args.chapter)
    print(f"# Similarity Risk Check: {args.chapter}")
    print()
    print(f"status: {status}")
    if blockers:
        print()
        print("## Blockers")
        for item in blockers:
            print(f"- {item}")
    if warnings:
        print()
        print("## Warnings")
        for item in warnings:
            print(f"- {item}")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
