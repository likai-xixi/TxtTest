from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_text, write_blocked_by_locks, write_text
from deepseek_client import call_deepseek, model_for
from deepseek_response import DeepSeekResponseError, extract_message_content


STYLE_INPUTS = (
    "state/project_style_contract.json",
    "state/project_style_contract.md",
    "bible/style_guide.md",
    "state/derived/style_profile.json",
    "state/project_reader_promise.json",
    "state/derived/personality/protagonist.json",
    "state/derived/protagonist_progression.json",
    "state/derived/world_reveal_ledger.json",
    "state/derived/suspense_ledger.json",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def file_body(path: Path, limit: int = 5000) -> str:
    if not path.exists():
        return f"[missing: {rel(path)}]"
    text = read_text(path)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def input_ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def prompt_for(chapter: str) -> tuple[str, str, list[Path]]:
    official = chapter_path(chapter)
    style_paths = [ROOT / item for item in STYLE_INPUTS]
    metrics = ROOT / "reviews" / chapter / "style_metrics.json"
    recent = sorted((ROOT / "reviews").glob("v??_c???/series_style.json"))[-3:]
    inputs = [official, metrics, *style_paths, *recent]
    system = (
        "You are an independent series-style reviewer. You only inspect the supplied chapter and style assets. "
        "Do not read Codex review files. Do not modify repository files. Return one JSON object only."
    )
    user = "\n\n".join(
        [
            f"Review chapter {chapter} for cross-chapter style consistency and series feel.",
            "Classify status as CLEAR, WARNING, or BLOCKED.",
            "BLOCKED means narration person, narration distance, protagonist voice, or two or more core rhythm/profile dimensions drift in a way that would make the series feel like a different book.",
            "WARNING means the drift is visible but can be accepted in early advisory chapters or fixed in revision.",
            "Return JSON with keys: status, action, findings, warnings, blockers, summary.",
            f"# Official Chapter\n\n{file_body(official, 12000)}",
            f"# Style Metrics\n\n{file_body(metrics, 4000)}",
            "# Style Contract\n\n" + file_body(ROOT / "state" / "project_style_contract.json", 4000),
            "# Human Style Contract\n\n" + file_body(ROOT / "state" / "project_style_contract.md", 3000),
            "# Style Guide\n\n" + file_body(ROOT / "bible" / "style_guide.md", 3000),
            "# Derived Style Profile\n\n" + file_body(ROOT / "state" / "derived" / "style_profile.json", 5000),
            "# Reader Promise\n\n" + file_body(ROOT / "state" / "project_reader_promise.json", 3000),
            "# Current Personality\n\n" + file_body(ROOT / "state" / "derived" / "personality" / "protagonist.json", 3000),
            "# Reader Experience Ledgers\n\n"
            + file_body(ROOT / "state" / "derived" / "protagonist_progression.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "world_reveal_ledger.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "suspense_ledger.json", 2500),
            "# Recent Series Style Reports\n\n" + "\n\n".join(file_body(path, 2000) for path in recent),
        ]
    )
    return system, user, inputs


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if "\n" in stripped:
            stripped = stripped.split("\n", 1)[1]
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("DeepSeek style review did not return a JSON object") from None
        data = json.loads(stripped[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("DeepSeek style review JSON must be an object")
    return data


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().upper()
    if status in {"READY", "CLEAR", "SHIP"}:
        return "CLEAR"
    if status in {"WARN", "WARNING", "ADVISORY"}:
        return "WARNING"
    if status in {"BLOCK", "BLOCKED", "NOT_READY", "REVISE", "REWRITE"}:
        return "BLOCKED"
    return "WARNING"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# DeepSeek Style Review: {report.get('chapter')}",
        "",
        f"status: {report.get('status')}",
        f"action: {report.get('action', '')}",
        "",
        "## Summary",
        "",
        str(report.get("summary", "")).strip() or "none",
        "",
    ]
    for key, title in (("findings", "Findings"), ("warnings", "Warnings"), ("blockers", "Blockers")):
        values = report.get(key, [])
        if values:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {item}" for item in values)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for an independent series-style review.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default=model_for("deepseek_style_review"))
    parser.add_argument("--max-tokens", type=int, default=2500)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek style review"):
        return 1
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    official = chapter_path(args.chapter)
    if not official.exists() or not read_text(official).strip():
        print(f"ERROR: missing official chapter text: {rel(official)}", file=sys.stderr)
        return 1

    system, user, inputs = prompt_for(args.chapter)
    payload = {
        "model": args.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "temperature": 0.2,
        "max_tokens": args.max_tokens,
        "stream": False,
    }

    run_dir = ROOT / "external_runs" / "deepseek" / args.chapter
    write_text(run_dir / "style_review.prompt.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    if args.dry_run:
        print(f"OK: dry run wrote {(run_dir / 'style_review.prompt.md').relative_to(ROOT)}")
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set.", file=sys.stderr)
        return 2

    try:
        response = call_deepseek(payload, api_key)
        content = extract_message_content(response)
        parsed = extract_json_object(content)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: DeepSeek request failed: {exc}", file=sys.stderr)
        return 1
    except (DeepSeekResponseError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: invalid DeepSeek style review response: {exc}", file=sys.stderr)
        return 1

    report = {
        "schema_version": 1,
        "chapter": args.chapter,
        "generated_at": now_iso(),
        "model": args.model,
        "status": normalize_status(parsed.get("status")),
        "action": str(parsed.get("action", "")).strip(),
        "official_chapter": input_ref(official),
        "inputs": [input_ref(path) for path in inputs if path.exists()],
        "findings": as_list(parsed.get("findings")),
        "warnings": as_list(parsed.get("warnings")),
        "blockers": as_list(parsed.get("blockers")),
        "summary": str(parsed.get("summary", "")).strip(),
    }

    write_text(run_dir / "style_review.raw.json", json.dumps(response, ensure_ascii=False, indent=2) + "\n")
    out_json = ROOT / "reviews" / args.chapter / "deepseek_style_review.json"
    out_md = ROOT / "reviews" / args.chapter / "deepseek_style_review.md"
    write_text(out_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write_text(out_md, render_markdown(report))
    print(f"OK: wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
