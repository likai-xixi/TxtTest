from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json
from style_contract import REQUIRED_FIELDS, validate_contract


HEADER = "# Candidate Style Requirements"
CONTRACT_JSON = ROOT / "state" / "project_style_contract.json"
CONTRACT_MD = ROOT / "state" / "project_style_contract.md"
STYLE_GUIDE = ROOT / "bible" / "style_guide.md"
STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"


PLACEHOLDERS = ("TODO", "TBD", "待定", "待填", "待评", "placeholder")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path, role: str) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "role": role, "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def has_placeholder_text(text: str) -> bool:
    lowered = text.lower()
    return not text.strip() or any(marker.lower() in lowered for marker in PLACEHOLDERS)


def render_value(value: Any, *, limit: int = 360) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value or "").strip()
    if len(text) > limit:
        return text[: limit - 18].rstrip() + " ...[truncated]"
    return text or "none"


def extract_declared_value(text: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(key)}\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip().strip("`")
    return value or None


def detect_conflicts(contract: dict[str, Any], texts: list[tuple[Path, str]]) -> list[str]:
    blockers: list[str] = []
    for key in REQUIRED_FIELDS:
        expected = render_value(contract.get(key), limit=200)
        if not expected or expected == "none":
            continue
        for path, text in texts:
            declared = extract_declared_value(text, key)
            if declared and declared != expected:
                blockers.append(f"{rel(path)} declares {key}={declared!r}, but style contract has {expected!r}")
    return blockers


def load_contract() -> tuple[dict[str, Any], list[str]]:
    if not CONTRACT_JSON.exists():
        return {}, [f"missing style contract: {rel(CONTRACT_JSON)}"]
    try:
        data = read_json(CONTRACT_JSON, {})
    except json.JSONDecodeError as exc:
        return {}, [f"invalid JSON in {rel(CONTRACT_JSON)}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{rel(CONTRACT_JSON)} must be a JSON object"]
    errors = validate_contract(data, official=True)
    if data.get("status") != "READY":
        errors.append(f"style contract status must be READY, got {data.get('status', 'MISSING')}")
    return data, errors


def profile_mode_for(chapter: str, blockers: list[str]) -> tuple[str, dict[str, Any]]:
    if not STYLE_PROFILE.exists():
        if chapter_number(chapter) < 4:
            return "warmup_not_hard_gate", {}
        blockers.append(f"post-warmup chapter requires READY style profile: {rel(STYLE_PROFILE)}")
        return "ready_profile_required", {}
    try:
        profile = read_json(STYLE_PROFILE, {})
    except json.JSONDecodeError as exc:
        blockers.append(f"invalid JSON in {rel(STYLE_PROFILE)}: {exc}")
        return "ready_profile_required" if chapter_number(chapter) >= 4 else "warmup_not_hard_gate", {}
    if not isinstance(profile, dict):
        blockers.append(f"{rel(STYLE_PROFILE)} must be a JSON object")
        return "ready_profile_required" if chapter_number(chapter) >= 4 else "warmup_not_hard_gate", {}
    if chapter_number(chapter) < 4:
        return "warmup_not_hard_gate", profile
    if profile.get("status") != "READY":
        blockers.append(
            f"post-warmup chapter requires READY style profile, got {profile.get('status', 'MISSING')}; run style-profile-build"
        )
    return "ready_profile_required", profile


def source_refs(include_profile: bool) -> list[dict[str, Any]]:
    refs = [
        file_ref(CONTRACT_JSON, "project_style_contract_json"),
        file_ref(CONTRACT_MD, "project_style_contract_markdown"),
        file_ref(STYLE_GUIDE, "style_guide"),
    ]
    if include_profile:
        refs.append(file_ref(STYLE_PROFILE, "derived_style_profile"))
    return refs


def context_pack_ref(chapter: str) -> tuple[dict[str, Any], list[str]]:
    path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    if not path.exists():
        return {"path": rel(path), "exists": False}, [f"missing context pack: {rel(path)}"]
    if not read_text(path).strip():
        return file_ref(path, "context_pack"), [f"context pack is empty: {rel(path)}"]
    return file_ref(path, "context_pack"), []


def render_requirements(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    contract, contract_errors = load_contract()
    blockers.extend(contract_errors)

    md_text = read_text(CONTRACT_MD)
    guide_text = read_text(STYLE_GUIDE)
    if not CONTRACT_MD.exists() or has_placeholder_text(md_text):
        blockers.append(f"missing or placeholder human style contract: {rel(CONTRACT_MD)}")
    if not STYLE_GUIDE.exists() or has_placeholder_text(guide_text):
        blockers.append(f"missing or placeholder style guide: {rel(STYLE_GUIDE)}")
    if contract:
        blockers.extend(detect_conflicts(contract, [(CONTRACT_MD, md_text), (STYLE_GUIDE, guide_text)]))

    profile_mode, profile = profile_mode_for(chapter, blockers)
    context_pack, context_errors = context_pack_ref(chapter)
    blockers.extend(context_errors)

    profile_status = str(profile.get("status", "MISSING")) if isinstance(profile, dict) and profile else "MISSING"
    include_profile_source = profile_mode == "ready_profile_required" or profile_status == "READY"
    if profile_mode == "warmup_not_hard_gate":
        warnings.append("Chapters 1-3 use the project style contract and style guide; derived series profile is not a hard gate yet.")

    lines = [
        HEADER,
        "",
        f"status: {'READY' if not blockers else 'BLOCKED'}",
        f"chapter: {chapter}",
        f"profile_mode: {profile_mode}",
        "",
        "## Priority",
        "",
        "- Brief, canon, event ledger, and context_pack facts outrank style guidance.",
        "- Candidate Style Requirements outrank model defaults and generic prose habits.",
        "- Style guidance must not introduce new facts, canon, event ledger entries, tools, abilities, or rules.",
        "- If style inputs are missing or contradictory, stop and report the blocker instead of drafting.",
        "",
        "## Project Voice",
        "",
    ]
    for key in REQUIRED_FIELDS:
        lines.append(f"- {key}: {render_value(contract.get(key) if contract else '')}")
    lines.extend(
        [
            "",
            "## Series Calibration",
            "",
            f"- profile_status: {profile_status}",
            f"- profile_mode: {profile_mode}",
        ]
    )
    if profile.get("baseline_policy"):
        lines.append(f"- baseline_policy: {render_value(profile.get('baseline_policy'))}")
    if profile.get("series_dimensions"):
        lines.append(f"- series_dimensions: {render_value(profile.get('series_dimensions'))}")
    if profile.get("allowed_ranges"):
        lines.append(f"- allowed_ranges: {render_value(profile.get('allowed_ranges'))}")
    lines.extend(
        [
            "",
            "## Source Trace",
            "",
            f"- context_pack: {context_pack.get('path')} sha256={context_pack.get('sha256', 'missing')}",
        ]
    )
    for item in source_refs(include_profile_source):
        lines.append(f"- {item['role']}: {item['path']} sha256={item.get('sha256', 'missing')}")
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)

    block = "\n".join(lines).rstrip() + "\n"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "READY" if not blockers else "BLOCKED",
        "profile_mode": profile_mode,
        "context_pack": context_pack,
        "style_sources": source_refs(include_profile_source),
        "candidate_style_requirements_present": block.startswith(HEADER),
        "block": block,
        "blockers": blockers,
        "warnings": warnings,
    }


def prompt_paths(chapter: str, provider: str) -> tuple[Path, Path]:
    if provider == "Codex":
        run_dir = ROOT / "external_runs" / "codex" / chapter
        return run_dir / "draft.prompt.md", run_dir / "draft.prompt.manifest.json"
    if provider == "DeepSeek":
        run_dir = ROOT / "external_runs" / "deepseek" / chapter
        return run_dir / "generate.prompt.md", run_dir / "generate.prompt.manifest.json"
    raise ValueError(f"unsupported provider: {provider}")


def top_level_requirements_present(prompt_text: str) -> bool:
    stripped = prompt_text.lstrip()
    return stripped.startswith(HEADER + "\n") or stripped.strip() == HEADER


def build_prompt_manifest(
    *,
    chapter: str,
    provider: str,
    prompt_path: Path,
    prompt_text: str,
    style_result: dict[str, Any],
    candidate_written: bool = False,
    candidate_path: Path | None = None,
) -> dict[str, Any]:
    prompt_ref = file_ref(prompt_path, "prompt")
    prompt_ref["sha256"] = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    candidate_ref = file_ref(candidate_path, "candidate_draft") if candidate_path is not None else None
    return {
        "schema_version": 1,
        "chapter": chapter,
        "status": style_result.get("status", "BLOCKED"),
        "generated_at": now_iso(),
        "provider": provider,
        "prompt_path": rel(prompt_path),
        "prompt_sha256": prompt_ref["sha256"],
        "context_pack": style_result.get("context_pack", {}),
        "style_sources": style_result.get("style_sources", []),
        "candidate_style_requirements_present": top_level_requirements_present(prompt_text),
        "profile_mode": style_result.get("profile_mode", ""),
        "candidate_written": candidate_written,
        "candidate_path": candidate_ref,
        "blockers": style_result.get("blockers", []),
        "warnings": style_result.get("warnings", []),
    }


def write_prompt_manifest(path: Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)


def validate_prompt_manifest(chapter: str, provider: str, *, require_candidate_written: bool = False) -> list[str]:
    prompt_path, manifest_path = prompt_paths(chapter, provider)
    label = f"{provider} candidate prompt evidence"
    if not manifest_path.exists():
        return [f"{chapter}: missing {label} manifest {rel(manifest_path)}"]
    data = read_json(manifest_path, {})
    failures: list[str] = []
    if not isinstance(data, dict):
        return [f"{chapter}: malformed {label} manifest {rel(manifest_path)}"]
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: {label} manifest chapter mismatch")
    if data.get("provider") != provider:
        failures.append(f"{chapter}: {label} manifest provider mismatch")
    if data.get("status") != "READY":
        failures.append(f"{chapter}: {label} status is {data.get('status', 'MISSING')}")
    if data.get("candidate_style_requirements_present") is not True:
        failures.append(f"{chapter}: {label} manifest does not confirm Candidate Style Requirements")
    if not prompt_path.exists():
        failures.append(f"{chapter}: missing {label} prompt {rel(prompt_path)}")
    else:
        prompt_text = read_text(prompt_path)
        if not top_level_requirements_present(prompt_text):
            failures.append(f"{chapter}: {label} prompt missing top-level Candidate Style Requirements")
        if data.get("prompt_path") != rel(prompt_path):
            failures.append(f"{chapter}: {label} prompt path mismatch")
        if data.get("prompt_sha256") != sha256(prompt_path):
            failures.append(f"{chapter}: {label} prompt hash mismatch")

    context = data.get("context_pack")
    if not isinstance(context, dict):
        failures.append(f"{chapter}: {label} context_pack ref is malformed")
    else:
        context_rel = str(context.get("path", "")).strip()
        context_sha = str(context.get("sha256", "")).strip()
        context_path = ROOT / context_rel
        expected_rel = f"state/context_pack/{chapter}.md"
        if context_rel != expected_rel:
            failures.append(f"{chapter}: {label} context_pack path mismatch")
        elif not context_path.exists():
            failures.append(f"{chapter}: {label} context_pack missing on disk")
        elif context_sha != sha256(context_path):
            failures.append(f"{chapter}: {label} context_pack hash is stale")

    sources = data.get("style_sources")
    if not isinstance(sources, list) or not sources:
        failures.append(f"{chapter}: {label} has no style_sources")
    else:
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                failures.append(f"{chapter}: {label} style_sources[{index}] is malformed")
                continue
            source_rel = str(item.get("path", "")).strip()
            expected_sha = str(item.get("sha256", "")).strip()
            if not source_rel or not expected_sha:
                failures.append(f"{chapter}: {label} style source missing path/sha256")
                continue
            source_path = ROOT / source_rel
            if not source_path.exists():
                failures.append(f"{chapter}: {label} style source missing on disk {source_rel}")
            elif sha256(source_path) != expected_sha:
                failures.append(f"{chapter}: {label} style source hash is stale for {source_rel}")

    if require_candidate_written and data.get("candidate_written") is not True:
        failures.append(f"{chapter}: {label} must confirm candidate_written")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the shared candidate chapter style requirements block.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = render_requirements(args.chapter)
    if args.json:
        payload = {key: value for key, value in result.items() if key != "block"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result["block"], end="")
    if result["status"] != "READY":
        for blocker in result.get("blockers", []):
            print(f"ERROR: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
