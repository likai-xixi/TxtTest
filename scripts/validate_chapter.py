from __future__ import annotations

import argparse
import sys

from _common import ROOT, chapter_parts, non_ws_count, read_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a drafted chapter file.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--min-chars", type=int, default=0)
    parser.add_argument("--max-chars", type=int, default=0)
    args = parser.parse_args()

    volume, chapter_file = chapter_parts(args.chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    errors: list[str] = []

    if not chapter_path.exists():
        errors.append(f"missing chapter: {chapter_path.relative_to(ROOT)}")
    else:
        text = read_text(chapter_path)
        count = non_ws_count(text)
        if not text.strip():
            errors.append("chapter is empty")
        if args.min_chars and count < args.min_chars:
            errors.append(f"chapter too short: {count} < {args.min_chars}")
        if args.max_chars and count > args.max_chars:
            errors.append(f"chapter too long: {count} > {args.max_chars}")
        if "待定" in text or "TODO" in text:
            errors.append("chapter contains placeholder text")

    if not context_path.exists():
        errors.append(f"missing context pack: {context_path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {chapter_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

