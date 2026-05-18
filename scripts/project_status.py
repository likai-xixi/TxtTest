from __future__ import annotations

import os
import subprocess

from _common import ROOT, gate_decision, read_text, unresolved_locks
from core_setting_freeze import validate_freeze


PLACEHOLDERS = ("待定", "待填", "待评", "待生成", "待人类裁决", "寰呭畾", "寰呭～", "寰呰瘎", "TODO")


IDEA_READY_FILES = (
    "original_idea.md",
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "agent_review_manifest.json",
    "codex_synthesis.md",
)
AGENT_REVIEW_FILES = (
    "original_idea.md",
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
)


def git_status() -> str:
    result = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        return "not a git repository"
    return result.stdout.strip() or "clean"


def has_placeholders(path: str) -> bool:
    text = read_text(ROOT / path)
    return any(marker in text for marker in PLACEHOLDERS)


def ready_idea_labs() -> list[str]:
    root = ROOT / "state" / "idea_lab"
    if not root.exists():
        return []
    labs = []
    for lab in root.iterdir():
        if not lab.is_dir():
            continue
        required = [lab / name for name in IDEA_READY_FILES]
        if all(path.exists() and read_text(path).strip() for path in required):
            latest_mtime = max(path.stat().st_mtime for path in required)
            labs.append((latest_mtime, lab.name))
    return [name for _, name in sorted(labs, reverse=True)]


def labs_needing_agent_manifest() -> list[str]:
    root = ROOT / "state" / "idea_lab"
    if not root.exists():
        return []
    labs = []
    for lab in root.iterdir():
        if not lab.is_dir() or (lab / "agent_review_manifest.json").exists():
            continue
        required = [lab / name for name in AGENT_REVIEW_FILES]
        if all(path.exists() and read_text(path).strip() for path in required):
            latest_mtime = max(path.stat().st_mtime for path in required)
            labs.append((latest_mtime, lab.name))
    return [name for _, name in sorted(labs, reverse=True)]


def main() -> int:
    labs = ready_idea_labs()
    manifest_labs = labs_needing_agent_manifest()
    unselected_labs = [lab for lab in labs if not (ROOT / "state" / "idea_lab" / lab / "selection.json").exists()]
    selected_labs = [lab for lab in labs if (ROOT / "state" / "idea_lab" / lab / "selection.json").exists()]

    print("# Project Status")
    print()
    print(f"root: {ROOT}")
    print(f"git: {git_status()}")
    print(f"DEEPSEEK_API_KEY: {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'missing'}")
    print()
    print("## Setup")
    freeze_errors = validate_freeze()
    print(f"- core setting freeze: {'ready' if not freeze_errors else 'missing'}")
    print(f"- premise placeholders: {'yes' if has_placeholders('outline/premise.md') else 'no'}")
    print(f"- c001 brief placeholders: {'yes' if has_placeholders('outline/chapter_briefs/v01_c001.md') else 'no'}")
    print(f"- event ledger exists: {'yes' if (ROOT / 'state/event_ledger.jsonl').exists() else 'no'}")
    print()
    print("## Workflow Gates")
    print(f"- open stop locks: {len(unresolved_locks())}")
    print(f"- Gate A decision: {gate_decision('a') or 'not recorded'}")
    print(f"- Gate B decision: {gate_decision('b') or 'not recorded'}")
    print()
    print("## Next likely action")
    if freeze_errors:
        if manifest_labs:
            print(f"Run `python scripts/novel.py idea-agent-manifest --id {manifest_labs[0]}` to record multi-agent provenance.")
        elif unselected_labs:
            print(f"Run `python scripts/novel.py idea-select --id {unselected_labs[0]} --choice A` to lock core settings.")
        else:
            print("Say `想法：...` / `开书实验`, or run `python scripts/novel.py idea --text \"...\"`; chapters cannot open until core settings are frozen.")
    elif unselected_labs:
        print(f"Run `python scripts/novel.py idea-select --id {unselected_labs[0]} --choice A` to record the human-selected direction.")
    elif selected_labs and has_placeholders("outline/chapter_briefs/v01_c001.md"):
        print("Say `写下一章`; Codex/DeepSeek should first produce brief candidates before the official brief is landed.")
    elif has_placeholders("outline/premise.md"):
        print("Say `继续`, or ask Codex to update outline/premise.md from core_setting_freeze.")
    elif has_placeholders("outline/chapter_briefs/v01_c001.md"):
        print("Say `写下一章`; brief candidates must be selected and landed before context pack generation.")
    else:
        print("Say `写下一章`, or run `python scripts/novel.py write v01_c001`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
