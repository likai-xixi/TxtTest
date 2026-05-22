from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from _common import ROOT, write_text


DIRS = [
    "bible",
    "outline/chapter_briefs",
    "chapters/v01",
    "drafts/codex",
    "drafts/deepseek",
    "external_runs/codex",
    "external_runs/deepseek",
    "reviews",
    "state/derived",
    "state/derived/personality",
    "state/derived/suspense",
    "state/derived/world_reveal",
    "state/derived/progression",
    "state/derived/reader_risk",
    "state/derived/prose_risk",
    "state/context_pack",
    "state/reader_promise",
    "state/snapshots",
    "state/gates",
    "state/idea_lab",
    "state/selections",
    "state/stops",
    "references",
    "ops",
    "schemas",
    "reader_tests",
    "reader_tests/responses",
    "reader_tests/chapter_feedback",
    "docs",
    "scripts",
    "templates",
    "exports",
    "backups",
]

GENERATED_PATTERNS = [
    "state/context_pack/*.md",
    "state/context_pack/*.json",
    "state/snapshots/*.md",
    "state/derived/*.md",
    "state/derived/*.yaml",
    "state/derived/personality/*.json",
    "state/derived/suspense/*.json",
    "state/derived/world_reveal/*.json",
    "state/derived/progression/*.json",
    "state/derived/protagonist_progression.json",
    "state/derived/reader_risk/*.json",
    "state/derived/reader_risk/*.md",
    "state/derived/prose_risk/*.json",
    "state/derived/prose_risk/*.md",
    "state/derived/concept_index.json",
    "state/derived/world_reveal_ledger.json",
    "state/derived/suspense_ledger.json",
    "state/idea_lab/*/*.md",
    "state/idea_lab/*/*.json",
    "external_runs/deepseek/*/*.prompt.md",
    "external_runs/deepseek/*/*.prompt.manifest.json",
    "external_runs/deepseek/*/*.manifest.json",
    "external_runs/deepseek/*/*.raw.json",
    "external_runs/codex/*/*.prompt.md",
    "external_runs/codex/*/*.manifest.json",
]


def ensure_gitkeep(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / ".gitkeep"
    if not marker.exists() and not any(directory.iterdir()):
        write_text(marker, "")


def clean_generated() -> int:
    removed = 0
    for pattern in GENERATED_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file() and ROOT in path.resolve().parents:
                path.unlink()
                removed += 1
    return removed


def maybe_init_git() -> bool:
    if (ROOT / ".git").exists():
        return False
    subprocess.run(["git", "init"], cwd=ROOT, check=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a copied template repository for a new novel project.")
    parser.add_argument("--project-name", default=None, help="Human-readable project name for setup_report.md.")
    parser.add_argument("--init-git", action="store_true", help="Run git init if this copy is not already a repo.")
    parser.add_argument("--clean-generated", action="store_true", help="Remove generated context/snapshot/prompt files.")
    args = parser.parse_args()

    for item in DIRS:
        ensure_gitkeep(ROOT / item)

    if not (ROOT / "state" / "event_ledger.jsonl").exists():
        write_text(ROOT / "state" / "event_ledger.jsonl", "")

    if not (ROOT / ".env.example").exists():
        write_text(ROOT / ".env.example", "DEEPSEEK_API_KEY=\n")
    if not (ROOT / "bible" / "objects.yaml").exists():
        write_text(ROOT / "bible" / "objects.yaml", "objects: []\n")
    if not (ROOT / "bible" / "abilities.yaml").exists():
        write_text(ROOT / "bible" / "abilities.yaml", "abilities: []\n")
    locks = ROOT / "state" / "stops" / "project_locks.json"
    if not locks.exists():
        write_text(locks, '{\n  "locks": []\n}\n')

    removed = clean_generated() if args.clean_generated else 0
    git_created = maybe_init_git() if args.init_git else False

    if args.project_name:
        report = ROOT / "setup_report.md"
        text = report.read_text(encoding="utf-8") if report.exists() else "# Setup Report\n"
        if "项目名：" not in text:
            text = text.replace("# Setup Report\n", f"# Setup Report\n\n项目名：{args.project_name}\n", 1)
        else:
            lines = [f"项目名：{args.project_name}" if line.startswith("项目名：") else line for line in text.splitlines()]
            text = "\n".join(lines) + "\n"
        write_text(report, text)

    print("OK: template project initialized")
    print(f"root: {ROOT}")
    print(f"generated files removed: {removed}")
    print(f"git initialized: {'yes' if git_created else 'no'}")
    print(f"DEEPSEEK_API_KEY: {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'missing'}")
    print(f"required agents: {'confirmed' if os.environ.get('CODEX_REQUIRED_AGENTS_READY') == '1' else 'unconfirmed'}")
    print("reader promise: v2 schema required before opening chapters")
    print("next: run `python scripts/novel.py opening-preflight --agents-ready`, then `python scripts/novel.py idea --text \"...\"`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
