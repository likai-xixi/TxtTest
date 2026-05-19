from __future__ import annotations

import argparse
import sys

from _common import chapter_parts
from chapter_evidence import validate_fact_cards


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize fact card acceptance status.")
    parser.add_argument("chapter")
    args = parser.parse_args()
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    failures = validate_fact_cards(args.chapter)
    print(f"# Fact Card Check: {args.chapter}")
    print()
    if failures:
        print("status: WARNING")
        print()
        print("## Warnings")
        for failure in failures:
            print(f"- {failure}")
        return 0
    print("status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
