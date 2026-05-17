from __future__ import annotations

import argparse
import subprocess
import sys

from _common import ROOT, chapter_number, chapter_parts, gate_decision, non_ws_count, read_text, unresolved_locks


PLACEHOLDERS = ("待定", "待填", "TODO")


def run(args: list[str]) -> int:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True)
    return result.returncode


def validate_brief(chapter: str, allow_placeholders: bool) -> list[str]:
    chapter_parts(chapter)
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    errors: list[str] = []
    if not brief.exists():
        return [f"missing brief: {brief.relative_to(ROOT)}"]
    text = read_text(brief)
    count = non_ws_count(text)
    if not allow_placeholders and count < 300:
        errors.append(f"brief too short for pilot rule: {count} < 300 non-whitespace chars")
    if not allow_placeholders and count > 800:
        errors.append(f"brief too long for pilot rule: {count} > 800 non-whitespace chars")
    if not allow_placeholders and any(marker in text for marker in PLACEHOLDERS):
        errors.append("brief still contains placeholders")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a chapter for drafting.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--allow-placeholders", action="store_true", help="Allow placeholder brief text; useful for template smoke tests.")
    parser.add_argument("--deepseek-dry-run", action="store_true", help="Build DeepSeek prompt without calling API.")
    args = parser.parse_args()

    locks = unresolved_locks()
    if locks:
        print("ERROR: unresolved stop locks block chapter start:", file=sys.stderr)
        for lock in locks:
            print(f"  - {lock.get('id')}: {lock.get('reason')}", file=sys.stderr)
        return 1

    number = chapter_number(args.chapter)
    if number >= 4 and gate_decision("a") != "continue":
        print("ERROR: Gate A must be recorded as continue before starting chapter 4+.", file=sys.stderr)
        return 1
    if number >= 11 and gate_decision("b") != "continue":
        print("ERROR: Gate B must be recorded as continue before starting chapter 11+.", file=sys.stderr)
        return 1
    if number >= 26 and gate_decision("c") != "continue":
        print("ERROR: Gate C must be recorded as continue before starting chapter 26+.", file=sys.stderr)
        return 1
    if number >= 126 and gate_decision("e") != "continue":
        print("ERROR: Gate E must be recorded as continue before starting chapter 126+.", file=sys.stderr)
        return 1

    errors = validate_brief(args.chapter, args.allow_placeholders)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not args.allow_placeholders:
        code = run(["scripts/brief_check.py", "--chapter", args.chapter])
        if code != 0:
            return code

    for step in [
        ["scripts/build_derived_state.py"],
        ["scripts/build_context_pack.py", "--chapter", args.chapter],
    ]:
        code = run(step)
        if code != 0:
            return code

    if args.deepseek_dry_run:
        return run(["scripts/run_deepseek_generate.py", "--chapter", args.chapter, "--dry-run"])

    print(f"OK: chapter {args.chapter} is ready for candidate drafting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
