from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, read_json
from context_governance import sha256
from workflow_errors import issue


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def expected_inputs(chapter: str) -> list[Path]:
    return [
        ROOT / "outline" / "chapter_briefs" / f"{chapter}.md",
        ROOT / "state" / "event_ledger.jsonl",
        ROOT / "state" / "derived" / "current_state.yaml",
        ROOT / "state" / "derived" / "pacing" / "progress_index.json",
        ROOT / "state" / "derived" / "pacing" / "aftermath_obligations.json",
        ROOT / "bible" / "objects.yaml",
        ROOT / "bible" / "abilities.yaml",
        ROOT / "state" / "idea_lab" / "selected.json",
    ]


def compare_manifest(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    manifest_path = ROOT / "state" / "context_pack" / f"{chapter}.manifest.json"
    pack_path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    result: dict[str, Any] = {
        "chapter": chapter,
        "manifest": rel(manifest_path),
        "context_pack": rel(pack_path),
        "status": "CLEAR",
        "missing": [],
        "added_inputs": [],
        "removed_inputs": [],
        "changed_inputs": [],
        "stale_inputs": [],
        "issues": [],
    }
    if not manifest_path.exists():
        result["status"] = "MISSING"
        result["issues"].append(issue("MISSING", "context manifest is missing", rel(manifest_path)))
        return result
    if not pack_path.exists():
        result["status"] = "MISSING"
        result["issues"].append(issue("MISSING", "context pack is missing", rel(pack_path)))

    try:
        manifest = read_json(manifest_path, {})
    except Exception as exc:
        result["status"] = "SCHEMA"
        result["issues"].append(issue("SCHEMA", f"manifest JSON is invalid: {exc}", rel(manifest_path)))
        return result
    input_hashes = manifest.get("input_hashes", [])
    if not isinstance(input_hashes, list):
        result["status"] = "SCHEMA"
        result["issues"].append(issue("SCHEMA", "manifest input_hashes must be a list", rel(manifest_path)))
        return result

    recorded: dict[str, str] = {}
    for item in input_hashes:
        if not isinstance(item, dict):
            result["issues"].append(issue("SCHEMA", "input_hashes entry must be an object", rel(manifest_path)))
            continue
        path_text = str(item.get("path") or "")
        expected_hash = str(item.get("sha256") or "")
        if path_text and expected_hash:
            recorded[path_text] = expected_hash

    current_paths = {rel(path): path for path in expected_inputs(chapter) if path.exists()}
    for path_text, expected_hash in sorted(recorded.items()):
        path = ROOT / path_text
        if not path.exists():
            result["removed_inputs"].append(path_text)
            result["issues"].append(issue("MISSING", "recorded context input is missing", path_text))
            continue
        current_hash = sha256(path)
        if current_hash != expected_hash:
            item = {"path": path_text, "recorded": expected_hash, "current": current_hash}
            result["changed_inputs"].append(item)
            result["stale_inputs"].append(path_text)
            result["issues"].append(issue("STALE", "recorded context input hash changed", path_text))

    for path_text in sorted(set(current_paths) - set(recorded)):
        result["added_inputs"].append(path_text)

    if result["issues"]:
        categories = {item["category"] for item in result["issues"]}
        result["status"] = "STALE" if "STALE" in categories else next(iter(categories))
    return result


def print_text(result: dict[str, Any]) -> None:
    print(f"# Context Diff: {result['chapter']}")
    print(f"status: {result['status']}")
    print()
    if result["issues"]:
        print("## Issues")
        for item in result["issues"]:
            text = f"{item['category']}: {item['message']}"
            if item.get("path"):
                text += f" ({item['path']})"
            print(f"- {text}")
        print()
    for key, title in [
        ("changed_inputs", "Changed Inputs"),
        ("removed_inputs", "Removed Inputs"),
        ("added_inputs", "New Current Inputs Not In Manifest"),
    ]:
        print(f"## {title}")
        values = result.get(key) or []
        if not values:
            print("- none")
        else:
            for item in values:
                print(f"- {item['path'] if isinstance(item, dict) else item}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare context manifest hashes with current inputs without rebuilding.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = compare_manifest(args.chapter)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
