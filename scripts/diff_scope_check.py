from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, posix


ROLE_PATTERNS = {
    "brief": ["outline/chapter_briefs/{chapter}.md"],
    "draft": ["chapters/{volume}/{chapter_file}.md"],
    "candidate": [
        "drafts/codex/{chapter}.md",
        "drafts/deepseek/{chapter}.md",
        "external_runs/deepseek/{chapter}/**",
    ],
    "review": [
        "reviews/{chapter}/codex_integrated_review.md",
        "reviews/{chapter}/deepseek_integrated_review.md",
    ],
    "continuity": ["reviews/{chapter}/continuity.md"],
    "decision": [
        "reviews/{chapter}/model_disagreement.md",
        "reviews/{chapter}/decision.md",
    ],
    "revision": [
        "chapters/{volume}/{chapter_file}.md",
        "reviews/{chapter}/revision.md",
    ],
    "state": [
        "state/event_ledger.jsonl",
        "state/derived/**",
        "state/context_pack/**",
        "state/snapshots/**",
    ],
}


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def changed_files() -> list[str]:
    head = run_git(["rev-parse", "--verify", "HEAD"])
    files: set[str] = set()
    if head.returncode == 0:
        for args in (["diff", "--name-only", "HEAD"], ["diff", "--name-only", "--cached"]):
            result = run_git(args)
            if result.returncode == 0:
                files.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    else:
        result = run_git(["status", "--short"])
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.add(path)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that changed files fit a workflow role.")
    parser.add_argument("--role", required=True, choices=sorted(ROLE_PATTERNS))
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    volume, chapter_file = chapter_parts(args.chapter)
    patterns = [
        pattern.format(chapter=args.chapter, volume=volume, chapter_file=chapter_file)
        for pattern in ROLE_PATTERNS[args.role]
    ]
    files = changed_files()
    violations = [
        file for file in files
        if not any(fnmatch.fnmatch(posix(file), pattern) for pattern in patterns)
    ]

    if violations:
        print(f"ERROR: role {args.role} allows only:")
        for pattern in patterns:
            print(f"  - {pattern}")
        print("Changed files outside scope:")
        for file in violations:
            print(f"  - {file}")
        return 1

    print(f"OK: {len(files)} changed files fit role {args.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

