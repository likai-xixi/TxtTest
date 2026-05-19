from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from element_usage import authorized_ids
from style_contract import BLOCKER_MARKERS, WARNING_MARKERS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def start_polish(chapter: str) -> int:
    official = chapter_path(chapter)
    if not official.exists() or not read_text(official).strip():
        print(f"ERROR: missing non-empty official chapter: {rel(official)}", file=sys.stderr)
        return 1
    text = read_text(official)
    draft = ROOT / "drafts" / "polish" / f"{chapter}.md"
    report = ROOT / "reviews" / chapter / "polish_report.md"
    manifest_path = ROOT / "reviews" / chapter / "polish_manifest.json"
    write_text(draft, text)
    manifest = {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "advisory_only": True,
        "writes_chapters": False,
        "writes_canon": False,
        "writes_event_ledger": False,
        "official_chapter": {"path": rel(official), "sha256": sha256(official)},
        "polish_draft": {"path": rel(draft), "sha256": sha256(draft)},
        "status": "CANDIDATE",
    }
    write_json(manifest_path, manifest)
    write_text(
        report,
        "\n".join(
            [
                f"# Polish Report: {chapter}",
                "",
                "status: CANDIDATE",
                "",
                "## Boundary",
                "",
                "- polish is advisory only",
                "- does not write chapters/",
                "- does not write canon",
                "- does not write event_ledger",
                "- adoption requires select-candidate + land + evidence again",
                "",
            ]
        ),
    )
    print(f"OK: wrote {rel(draft)}")
    return 0


def markers(text: str, kind: str) -> set[str]:
    import re

    return set(re.findall(rf"\[{kind}:([A-Za-z0-9_.-]+)\]", text))


def check_polish(chapter: str) -> tuple[str, list[str], list[str]]:
    draft = ROOT / "drafts" / "polish" / f"{chapter}.md"
    manifest_path = ROOT / "reviews" / chapter / "polish_manifest.json"
    if not draft.exists() and not manifest_path.exists():
        return "INFO", [], [f"no polish candidate for {chapter}"]
    blockers: list[str] = []
    warnings: list[str] = []
    official = chapter_path(chapter)
    manifest = read_json(manifest_path, {})
    if not manifest:
        blockers.append(f"missing polish manifest reviews/{chapter}/polish_manifest.json")
    else:
        for flag in ("writes_chapters", "writes_canon", "writes_event_ledger"):
            if manifest.get(flag) is not False:
                blockers.append(f"polish manifest must not set {flag}=true")
        official_info = manifest.get("official_chapter", {})
        if isinstance(official_info, dict) and official.exists() and official_info.get("sha256") != sha256(official):
            blockers.append("official chapter changed after polish manifest; rerun selection/landing/evidence before Ship")
    if not draft.exists() or not read_text(draft).strip():
        blockers.append(f"missing non-empty polish draft drafts/polish/{chapter}.md")
    elif official.exists():
        draft_text = read_text(draft)
        official_text = read_text(official)
        objects, abilities = authorized_ids(chapter)
        new_objects = markers(draft_text, "object") - markers(official_text, "object") - objects
        new_abilities = markers(draft_text, "ability") - markers(official_text, "ability") - abilities
        if new_objects:
            blockers.append("polish draft introduces unauthorized object markers: " + ", ".join(sorted(new_objects)))
        if new_abilities:
            blockers.append("polish draft introduces unauthorized ability markers: " + ", ".join(sorted(new_abilities)))
        if len(draft_text) > len(official_text) * 1.5:
            warnings.append("polish candidate is much longer than official chapter; review style drift")
        for marker, message in BLOCKER_MARKERS.items():
            if marker in draft_text and marker not in official_text:
                blockers.append(f"polish draft changes protected style dimension: {message}")
        for marker, message in WARNING_MARKERS.items():
            if marker in draft_text and marker not in official_text:
                warnings.append(f"polish draft may drift style: {message}")
    if blockers:
        return "BLOCKED", blockers, warnings
    if warnings:
        return "WARNING", blockers, warnings
    return "READY", blockers, warnings


def print_check(chapter: str) -> int:
    status, blockers, warnings = check_polish(chapter)
    print(f"# Polish Check: {chapter}")
    print()
    print(f"status: {status}")
    if blockers:
        print()
        print("## Blockers")
        for item in blockers:
            print(f"- {item}")
    if warnings:
        print()
        print("## Notes")
        for item in warnings:
            print(f"- {item}")
    return 1 if blockers else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or check an advisory polish candidate.")
    parser.add_argument("chapter")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.check:
        return print_check(args.chapter)
    return start_polish(args.chapter)


if __name__ == "__main__":
    raise SystemExit(main())
