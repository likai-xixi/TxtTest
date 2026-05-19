from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import ROOT


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def seed(repo: Path, chapters: int) -> str:
    events = []
    for number in range(1, chapters + 1):
        chapter = f"v01_c{number:03d}"
        write(Path(repo) / "chapters" / "v01" / f"c{number:03d}.md", f"Synthetic chapter {chapter}: tracked decision and anchor.\n")
        events.append(
            {
                "event_id": f"{chapter}_e001",
                "chapter": chapter,
                "type": "character_decision",
                "fact": f"{chapter} protagonist makes a tracked decision",
                "evidence_quote": "tracked decision",
                "consequence": "state changes",
                "verified_by": "human",
                "importance": "P1",
            }
        )
        events.append(
            {
                "event_id": f"{chapter}_e002",
                "chapter": chapter,
                "type": "chapter_anchor",
                "fact": f"{chapter} anchor is confirmed",
                "evidence_quote": "anchor",
                "consequence": "next chapter inherits visible state",
                "verified_by": "human",
                "importance": "P1",
                "anchor": {
                    "end_time": f"night {number}",
                    "end_location": "test location",
                    "present_characters": ["protagonist"],
                    "protagonist_state": "alert",
                    "carried_items": ["none"],
                    "unfinished_action": "continue investigation",
                    "next_required_continuity": "start from the anchor",
                },
            }
        )
    write(repo / "state/event_ledger.jsonl", "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n")
    write(repo / "bible/rules.md", "# Rules\n\nNo placeholders in synthetic longrun smoke.\n")
    target = f"v01_c{chapters:03d}"
    pack = "# Context Pack\n\n" + "\n".join(item["event_id"] for item in events[:-2]) + "\n"
    pack_rel = f"state/context_pack/{target}.md"
    manifest_rel = f"state/context_pack/{target}.manifest.json"
    write(repo / pack_rel, pack)
    sections = [
        {"id": "core_freeze", "body_chars": 20, "sources": [{"path": "bible/rules.md"}]},
        {"id": "chapter_brief", "body_chars": 20, "sources": [{"path": f"outline/chapter_briefs/{target}.md"}]},
        {"id": "chapter_anchor_continuity", "body_chars": 20, "sources": [{"event_id": events[-3]["event_id"]}]},
        {"id": "active_aftermath_obligations", "body_chars": 20, "sources": [{"path": "state/derived/pacing/aftermath_obligations.json"}]},
        {"id": "authorized_elements_full", "body_chars": 20, "sources": [{"path": f"outline/chapter_briefs/{target}.md"}]},
        {"id": "rules_and_boundaries", "body_chars": 20, "sources": [{"path": "bible/rules.md"}]},
        {"id": "recent_events", "body_chars": len(pack), "sources": [{"event_id": item["event_id"]} for item in events[:-2]]},
    ]
    manifest = {
        "schema_version": 2,
        "chapter": target,
        "generated_at": "2000-01-01T00:00:00+00:00",
        "budget_chars": 200000,
        "hard_max_chars": 300000,
        "allow_truncated": False,
        "pack_truncated": False,
        "pack_chars": len(pack),
        "object_ids": [],
        "ability_ids": [],
        "sections": sections,
        "input_hashes": [
            {"path": "state/event_ledger.jsonl", "sha256": sha(repo / "state/event_ledger.jsonl")},
            {"path": "bible/rules.md", "sha256": sha(repo / "bible/rules.md")},
        ],
        "context_pack": {"path": pack_rel, "sha256": sha(repo / pack_rel), "chars": len(pack)},
    }
    write(repo / manifest_rel, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write(repo / f"outline/chapter_briefs/{target}.md", "# Brief\n\nsynthetic brief for longrun smoke\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic long-run governance smoke in a temporary copy.")
    parser.add_argument("--chapters", type=int, default=10)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()
    if args.chapters < 1:
        print("ERROR: --chapters must be >= 1", file=sys.stderr)
        return 1
    temp = tempfile.mkdtemp(prefix="novel_longrun_")
    repo = Path(temp) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "backups", "exports"))
    target = seed(repo, args.chapters)
    steps = [
        ("derive", ("scripts/novel.py", "derive")),
        ("context-quality", ("scripts/novel.py", "context-quality", target)),
        ("pacing-dashboard", ("scripts/novel.py", "pacing-dashboard", target)),
        ("long-health", ("scripts/novel.py", "long-health", "--to", target)),
        ("gate-rehearsal", ("scripts/novel.py", "gate-rehearsal", "A")),
    ]
    ok = True
    for name, command in steps:
        result = run(repo, *command)
        status = "OK" if result.returncode == 0 else "FAIL"
        print(f"# {name}: {status}")
        if result.returncode != 0:
            ok = False
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
    if args.keep_temp:
        print(f"temp_repo: {repo}")
    else:
        shutil.rmtree(temp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
