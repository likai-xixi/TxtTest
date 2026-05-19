from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys

from _common import ROOT, chapter_parts, non_ws_count, read_json, read_text, unresolved_locks
from context_governance import load_process_budget
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from gate_policy import gate_errors_for_chapter


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
    chars = load_process_budget()["pilot"]["chapter_brief_chars"]
    minimum = int(chars["min"])
    maximum = int(chars["max"])
    if not allow_placeholders and count < minimum:
        errors.append(f"brief too short for pilot rule: {count} < {minimum} non-whitespace chars")
    if not allow_placeholders and count > maximum:
        errors.append(f"brief too long for pilot rule: {count} > {maximum} non-whitespace chars")
    if not allow_placeholders and any(marker in text for marker in PLACEHOLDERS):
        errors.append("brief still contains placeholders")
    return errors


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_brief_landing(chapter: str) -> list[str]:
    path = ROOT / "reviews" / chapter / "brief_landing.json"
    if not path.exists():
        return [
            f"missing brief landing record: {path.relative_to(ROOT)}; "
            "run select-brief and land-brief before start"
        ]
    record = read_json(path, {})
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    official = record.get("official_brief")
    errors: list[str] = []
    if record.get("chapter") != chapter:
        errors.append("brief landing record chapter mismatch")
    if record.get("landed_by") != "Codex":
        errors.append("brief landing record must have landed_by Codex")
    if not str(record.get("attestation", "")).strip():
        errors.append("brief landing record missing attestation")
    if not isinstance(official, dict):
        errors.append("brief landing record missing official_brief")
    else:
        if official.get("path") != f"outline/chapter_briefs/{chapter}.md":
            errors.append("brief landing official brief path mismatch")
        if not brief.exists():
            errors.append(f"brief landing official brief missing on disk: {brief.relative_to(ROOT)}")
        elif official.get("sha256") != sha256(brief):
            errors.append("brief landing official brief hash mismatch")
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

    gate_errors = gate_errors_for_chapter(args.chapter, "starting")
    if gate_errors:
        for error in gate_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not ensure_core_setting_freeze():
        return 1

    errors = validate_brief(args.chapter, args.allow_placeholders)
    if not args.allow_placeholders:
        errors.extend(validate_brief_landing(args.chapter))
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
        ["scripts/context_pack_quality.py", "--chapter", args.chapter],
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
