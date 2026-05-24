from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, read_json
from shadow_common import (
    MANIFEST_DIR,
    SOURCE_BOUNDARY,
    base_artifact,
    current_ref_failures,
    file_ref,
    load_shadow_json,
    shadow_markdown_path,
    shadow_paths,
    write_shadow_json,
    write_shadow_markdown,
)
from shadow_kg_edges import build as build_kg_edges, render_markdown as render_kg_markdown
from shadow_local_window import build as build_local_window, render_markdown as render_local_markdown
from shadow_rag_index import build as build_rag_index, render_markdown as render_rag_markdown
from shadow_route_signals import build as build_route_signals, render_markdown as render_route_markdown


ARTIFACTS = ("local_window", "rag_index", "kg_edges", "route_signals")


def dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for ref in refs:
        key = (str(ref.get("path") or ""), str(ref.get("event_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _write_artifact(chapter: str, key: str, data: dict[str, Any]) -> None:
    path = shadow_paths(chapter)[key]
    write_shadow_json(path, data)
    if key == "local_window":
        lines = render_local_markdown(data).splitlines()
        title = "Shadow Local Window"
    elif key == "rag_index":
        lines = render_rag_markdown(data)
        title = "Shadow RAG Index"
    elif key == "kg_edges":
        lines = render_kg_markdown(data)
        title = "Shadow KG Edges"
    else:
        lines = render_route_markdown(data)
        title = "Shadow Route Signals"
    write_shadow_markdown(shadow_markdown_path(path), title, data, lines)


def build_all(chapter: str, *, write: bool = False) -> dict[str, Any]:
    chapter_parts(chapter)
    artifacts = {
        "local_window": build_local_window(chapter),
        "rag_index": build_rag_index(chapter),
        "kg_edges": build_kg_edges(chapter),
    }
    if write:
        for key in ("local_window", "rag_index", "kg_edges"):
            _write_artifact(chapter, key, artifacts[key])
    artifacts["route_signals"] = build_route_signals(chapter)
    if write:
        _write_artifact(chapter, "route_signals", artifacts["route_signals"])
    blockers: list[str] = []
    warnings: list[str] = []
    source_refs: list[dict[str, Any]] = []
    for key, data in artifacts.items():
        blockers.extend(f"{key}: {item}" for item in data.get("blockers", []))
        warnings.extend(f"{key}: {item}" for item in data.get("warnings", []))
        source_refs.extend(ref for ref in data.get("source_refs", []) if isinstance(ref, dict))
    output_refs = {key: file_ref(path) for key, path in shadow_paths(chapter).items() if key != "manifest"}
    manifest = base_artifact(
        chapter,
        "manifest",
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        warnings=warnings,
        source_refs=dedupe_refs(source_refs),
    )
    manifest.update(
        {
            "artifacts": output_refs,
            "artifact_statuses": {key: artifacts[key].get("status", "MISSING") for key in ARTIFACTS},
            "route": artifacts["route_signals"].get("route", "heavy"),
            "can_downgrade_route": False,
            "can_satisfy_ship_without_chapter_evidence": False,
            "rebuild_command": f"python scripts/novel.py shadow-build {chapter} --write",
            "check_command": f"python scripts/novel.py shadow-check {chapter}",
        }
    )
    if write:
        path = shadow_paths(chapter)["manifest"]
        write_shadow_json(path, manifest)
        write_shadow_markdown(
            shadow_markdown_path(path),
            "Shadow Manifest",
            manifest,
            [
                "## Artifacts",
                *[f"- {key}: {ref.get('path')} status={manifest['artifact_statuses'].get(key)}" for key, ref in output_refs.items()],
            ],
        )
    return manifest


def check_artifact(path: Path, key: str, chapter: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return [f"missing shadow artifact: {path.relative_to(ROOT).as_posix()}"], warnings
    try:
        data = read_json(path, {})
    except Exception as exc:
        return [f"{path.relative_to(ROOT).as_posix()} invalid JSON: {exc}"], warnings
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT).as_posix()} must be a JSON object"], warnings
    if data.get("chapter") != chapter:
        blockers.append(f"{key} chapter mismatch")
    if data.get("artifact") != key:
        blockers.append(f"{key} artifact name mismatch")
    if data.get("source_boundary") != SOURCE_BOUNDARY:
        blockers.append(f"{key} source_boundary must be {SOURCE_BOUNDARY}")
    if data.get("can_write_canon") is not False or data.get("can_write_event_ledger") is not False:
        blockers.append(f"{key} must not be allowed to write canon or event ledger")
    if data.get("status") == "BLOCKED":
        blockers.extend(f"{key}: {item}" for item in data.get("blockers", []))
    elif data.get("status") != "READY":
        warnings.append(f"{key} status is {data.get('status', 'MISSING')}")
    for index, ref in enumerate(data.get("source_refs", []) if isinstance(data.get("source_refs"), list) else [], start=1):
        for failure in current_ref_failures(ref):
            blockers.append(f"{key} source_refs[{index}]: {failure}")
    if key == "route_signals":
        if data.get("can_downgrade_route") is not False:
            blockers.append("route_signals must explicitly forbid route downgrade")
        if data.get("must_not_skip_ship_evidence") is not True:
            blockers.append("route_signals must assert Ship evidence is mandatory")
    return blockers, warnings


def evaluate(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    paths = shadow_paths(chapter)
    checked: list[str] = []
    for key in ARTIFACTS:
        checked.append(paths[key].relative_to(ROOT).as_posix())
        artifact_blockers, artifact_warnings = check_artifact(paths[key], key, chapter)
        blockers.extend(artifact_blockers)
        warnings.extend(artifact_warnings)
    manifest_path = paths["manifest"]
    checked.append(manifest_path.relative_to(ROOT).as_posix())
    if not manifest_path.exists():
        blockers.append(f"missing shadow manifest: {manifest_path.relative_to(ROOT).as_posix()}")
        manifest = {}
    else:
        manifest = load_shadow_json(manifest_path)
        if manifest.get("chapter") != chapter:
            blockers.append("shadow manifest chapter mismatch")
        if manifest.get("artifact") != "manifest":
            blockers.append("shadow manifest artifact name mismatch")
        for index, ref in enumerate(manifest.get("source_refs", []) if isinstance(manifest.get("source_refs"), list) else [], start=1):
            for failure in current_ref_failures(ref):
                blockers.append(f"manifest source_refs[{index}]: {failure}")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            blockers.append("shadow manifest missing artifacts")
        else:
            for key in ARTIFACTS:
                for failure in current_ref_failures(artifacts.get(key)):
                    blockers.append(f"manifest artifacts.{key}: {failure}")
    return {
        "schema_version": 1,
        "chapter": chapter,
        "status": "BLOCKED" if blockers else "READY",
        "source_boundary": SOURCE_BOUNDARY,
        "checked": checked,
        "blockers": blockers,
        "warnings": warnings,
        "route": manifest.get("route") if isinstance(manifest, dict) else "unknown",
    }


def chapter_candidates() -> list[str]:
    chapters: set[str] = set()
    for base in (ROOT / "outline" / "chapter_briefs", ROOT / "state" / "context_pack", ROOT / "reviews", ROOT / "state" / "shadow" / "manifests"):
        if not base.exists():
            continue
        for item in base.iterdir():
            name = item.name
            if item.is_dir() and name.startswith("v") and "_c" in name:
                chapters.add(name)
            elif name.startswith("v") and "_c" in name and name.endswith(".json"):
                chapters.add(name.removesuffix(".json"))
            elif name.startswith("v") and "_c" in name and name.endswith(".md"):
                chapters.add(name.removesuffix(".md"))
    return sorted(chapters)


def audit() -> dict[str, Any]:
    results = [evaluate(chapter) for chapter in chapter_candidates()]
    blockers = [f"{item['chapter']}: {blocker}" for item in results for blocker in item.get("blockers", [])]
    return {
        "schema_version": 1,
        "status": "BLOCKED" if blockers else "READY",
        "chapter_count": len(results),
        "blockers": blockers,
        "results": results,
    }


def print_text(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status')}")
    if "chapter" in data:
        print(f"chapter: {data.get('chapter')}")
    if data.get("route"):
        print(f"route: {str(data.get('route')).upper()}")
    for blocker in data.get("blockers", []):
        print(f"- {blocker}")
    for warning in data.get("warnings", []):
        print(f"- warning: {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build, check, diff, or audit shadow-memory artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "check", "diff"):
        p = sub.add_parser(command)
        p.add_argument("chapter")
        p.add_argument("--json", action="store_true")
        if command == "build":
            p.add_argument("--write", action="store_true")
    p = sub.add_parser("audit")
    p.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "build":
            data = build_all(args.chapter, write=args.write)
        elif args.command in {"check", "diff"}:
            data = evaluate(args.chapter)
        else:
            data = audit()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_text(data)
    return 0 if data.get("status") == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
