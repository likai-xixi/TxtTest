from __future__ import annotations

import os
import subprocess

from _common import ROOT, read_text


PLACEHOLDERS = ("待定", "待填")


def git_status() -> str:
    result = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        return "not a git repository"
    return result.stdout.strip() or "clean"


def has_placeholders(path: str) -> bool:
    text = read_text(ROOT / path)
    return any(marker in text for marker in PLACEHOLDERS)


def main() -> int:
    print("# Project Status")
    print()
    print(f"root: {ROOT}")
    print(f"git: {git_status()}")
    print(f"DEEPSEEK_API_KEY: {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'missing'}")
    print()
    print("## Setup")
    print(f"- premise placeholders: {'yes' if has_placeholders('outline/premise.md') else 'no'}")
    print(f"- c001 brief placeholders: {'yes' if has_placeholders('outline/chapter_briefs/v01_c001.md') else 'no'}")
    print(f"- event ledger exists: {'yes' if (ROOT / 'state/event_ledger.jsonl').exists() else 'no'}")
    print()
    print("## Next likely action")
    if has_placeholders("outline/premise.md"):
        print("Fill templates/questionnaire_answers.md, then run scripts/apply_questionnaire.py.")
    elif has_placeholders("outline/chapter_briefs/v01_c001.md"):
        print("Fill outline/chapter_briefs/v01_c001.md, then run scripts/start_chapter.py --chapter v01_c001.")
    else:
        print("Run scripts/start_chapter.py --chapter v01_c001.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

