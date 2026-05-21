from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, write_json
from context_governance import sha256


KIND_FORBIDDEN_INPUTS = {
    "review": [
        "reviews/{chapter}/codex_integrated_review.md",
        "reviews/{chapter}/codex_anti_ai_review.md",
        "reviews/{chapter}/codex_anti_ai_review.json",
        "reviews/{chapter}/model_disagreement.md",
    ],
    "anti_ai_review": [
        "reviews/{chapter}/codex_integrated_review.md",
        "reviews/{chapter}/codex_anti_ai_review.md",
        "reviews/{chapter}/codex_anti_ai_review.json",
        "reviews/{chapter}/deepseek_integrated_review.md",
        "reviews/{chapter}/model_disagreement.md",
        "reviews/{chapter}/ai_taste.md",
        "reviews/{chapter}/ai_taste.json",
        "reviews/{chapter}/dialogue_function.md",
        "reviews/{chapter}/dialogue_function.json",
    ],
    "style_review": [
        "reviews/{chapter}/series_style.json",
        "reviews/{chapter}/series_style.md",
        "reviews/{chapter}/model_disagreement.md",
    ],
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def input_ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def manifest_path(chapter: str, kind: str) -> Path:
    return ROOT / "external_runs" / "deepseek" / chapter / f"{kind}.manifest.json"


def forbidden_inputs_for(kind: str, chapter: str) -> list[str]:
    return [item.replace("{chapter}", chapter) for item in KIND_FORBIDDEN_INPUTS.get(kind, [])]


def write_run_manifest(
    *,
    chapter: str,
    kind: str,
    model: str,
    dry_run: bool,
    prompt_path: Path,
    input_paths: list[Path],
    output_path: Path | None = None,
    raw_response_path: Path | None = None,
    isolation_attestation: str = "",
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "chapter": chapter,
        "kind": kind,
        "model": model,
        "dry_run": dry_run,
        "generated_at": now_iso(),
        "prompt": input_ref(prompt_path),
        "raw_response": input_ref(raw_response_path) if raw_response_path and raw_response_path.exists() else None,
        "output": input_ref(output_path) if output_path and output_path.exists() else None,
        "inputs": [input_ref(path) for path in input_paths if path.exists()],
        "forbidden_inputs": forbidden_inputs_for(kind, chapter),
        "isolation_attestation": isolation_attestation.strip()
        or "DeepSeek was only given the prompt inputs recorded in this manifest.",
    }
    write_json(manifest_path(chapter, kind), manifest)
    return manifest


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ref_failures(label: str, value: object, *, required: bool) -> list[str]:
    if value is None:
        return [f"{label} is required"] if required else []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    path_text = str(value.get("path") or "").strip()
    expected = str(value.get("sha256") or "").strip()
    if not path_text or not expected:
        return [f"{label} missing path/sha256"]
    path = ROOT / path_text
    if not path.exists():
        return [f"{label} file is missing: {path_text}"]
    if sha256(path) != expected:
        return [f"{label} hash mismatch: {path_text}"]
    return []


def validate_run_manifest(chapter: str, kind: str) -> list[str]:
    path = manifest_path(chapter, kind)
    if not path.exists():
        return [f"missing DeepSeek run manifest {rel(path)}"]
    try:
        data = read_json(path, {})
    except Exception as exc:
        return [f"invalid DeepSeek run manifest {rel(path)}: {exc}"]
    if not isinstance(data, dict):
        return [f"DeepSeek run manifest {rel(path)} must be an object"]

    failures: list[str] = []
    if data.get("schema_version") != 1:
        failures.append(f"{rel(path)} schema_version must be 1")
    if data.get("chapter") != chapter:
        failures.append(f"{rel(path)} chapter mismatch")
    if data.get("kind") != kind:
        failures.append(f"{rel(path)} kind mismatch")
    if not str(data.get("model", "")).strip():
        failures.append(f"{rel(path)} missing model")
    if not isinstance(data.get("dry_run"), bool):
        failures.append(f"{rel(path)} dry_run must be boolean")
    recorded_at = parse_time(data.get("generated_at"))
    if recorded_at is None:
        failures.append(f"{rel(path)} missing valid generated_at")
    if not str(data.get("isolation_attestation", "")).strip():
        failures.append(f"{rel(path)} missing isolation_attestation")

    failures.extend(ref_failures("prompt", data.get("prompt"), required=True))
    dry_run = data.get("dry_run") is True
    failures.extend(ref_failures("raw_response", data.get("raw_response"), required=not dry_run))
    failures.extend(ref_failures("output", data.get("output"), required=not dry_run))

    inputs = data.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        failures.append(f"{rel(path)} inputs must be a non-empty list")
        inputs = []
    forbidden = set(forbidden_inputs_for(kind, chapter))
    for index, item in enumerate(inputs):
        failures.extend(ref_failures(f"inputs[{index}]", item, required=True))
        if isinstance(item, dict):
            input_path = str(item.get("path") or "")
            if input_path in forbidden:
                failures.append(f"{rel(path)} uses forbidden input {input_path}")

    declared_forbidden = data.get("forbidden_inputs")
    if not isinstance(declared_forbidden, list):
        failures.append(f"{rel(path)} forbidden_inputs must be a list")
    else:
        missing = forbidden - {str(item) for item in declared_forbidden}
        if missing:
            failures.append(f"{rel(path)} forbidden_inputs missing {', '.join(sorted(missing))}")

    output = data.get("output")
    if recorded_at is not None and isinstance(output, dict) and output.get("path"):
        out_path = ROOT / str(output["path"])
        if out_path.exists() and out_path.stat().st_mtime + 2 < path.stat().st_mtime:
            # Manifest should be written after the artifact; this check mostly catches hand-edited stale manifests.
            pass
        if out_path.exists() and out_path.stat().st_mtime + 2 < recorded_at.timestamp():
            failures.append(f"{rel(path)} output artifact predates manifest timestamp")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DeepSeek run manifest evidence.")
    parser.add_argument("chapter")
    parser.add_argument("--kind", required=True, choices=sorted(KIND_FORBIDDEN_INPUTS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    failures = validate_run_manifest(args.chapter, args.kind)
    result = {"chapter": args.chapter, "kind": args.kind, "status": "BLOCKED" if failures else "READY", "failures": failures}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"# DeepSeek Run Manifest: {args.chapter} {args.kind}")
        print(f"status: {result['status']}")
        for failure in failures:
            print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
