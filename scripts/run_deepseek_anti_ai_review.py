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
from deepseek_run_manifest import write_run_manifest
from review_binding import markdown_review_with_hash
from review_context import write_review_context


REVIEW_INPUTS = (
    "state/project_style_contract.json",
    "state/project_style_contract.md",
    "bible/style_guide.md",
    "state/project_reader_promise.json",
    "state/project_reader_promise.md",
    "state/derived/personality/protagonist.json",
    "state/derived/protagonist_progression.json",
    "state/derived/world_reveal_ledger.json",
    "state/derived/suspense_ledger.json",
)
CATEGORIES = (
    "show_dont_tell",
    "rhythm_disorder",
    "emotional_risk",
    "gray_motive",
    "dialogue_agenda",
    "detail_economy",
    "setting_integration",
    "consequence_integrity",
)
SEVERITIES = {"P0", "P1", "P2", "P3"}


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
    brief = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    context = ROOT / "state" / "context_pack" / f"{chapter}.md"
    if not (ROOT / "state" / "context_pack" / f"{chapter}_review_context.md").exists():
        write_review_context(chapter)
    review_context_md = ROOT / "state" / "context_pack" / f"{chapter}_review_context.md"
    review_context_json = ROOT / "state" / "context_pack" / f"{chapter}_review_context.json"
    input_paths = [official, brief, context, review_context_md, review_context_json, *(ROOT / item for item in REVIEW_INPUTS)]
    system = (
        "You are DeepSeek acting as an independent anti-AI-taste fiction reviewer. "
        "You only inspect the supplied official chapter, brief, context pack, style contract, reader promise, and derived ledgers. "
        "Do not read Codex review files, Codex anti-AI reports, ai_taste reports, dialogue_function reports, or model disagreement reports. "
        "Do not modify repository files. Return one JSON object only."
    )
    user = "\n\n".join(
        [
            f"Review chapter {chapter} for AI-taste risk and human texture.",
            "Classify status as CLEAR, WARNING, or BLOCKED. Use BLOCKED for ship-stopping issues.",
            "Check these categories exactly: show_dont_tell, rhythm_disorder, emotional_risk, gray_motive, dialogue_agenda, detail_economy, setting_integration, consequence_integrity.",
            "Category meanings:",
            "- show_dont_tell: over-explained subtext, neat psychological summaries, telling readers what to think.",
            "- rhythm_disorder: over-regular short sentence runs, too much parallelism, too little oral roughness.",
            "- emotional_risk: emotions trapped in a safe middle range, no anger, pettiness, desire, shame, or private ugliness when the scene invites it.",
            "- gray_motive: protagonist or major characters lack self-interest, concealment, spite, bad bargains, or consequences for doing wrong.",
            "- dialogue_agenda: dialogue acts as theme delivery instead of information movement, pressure, concealment, relationship testing, or desire.",
            "- detail_economy: concrete details feel decorative, over-dense, or unearned by later narrative function.",
            "- setting_integration: genre/worldbuilding elements feel pasted on or generic rather than causing scene-specific constraints.",
            "- consequence_integrity: gray actions, revelations, and vivid details do not leave durable consequences or later obligations.",
            "For every category, return status, severity P0-P3, evidence_quotes copied from the official chapter, issue, and revision_actions.",
            "Also sample key dialogue or no-dialogue interaction moments. Each sample needs evidence_quote, function, character_goal, subtext_or_hidden_agenda, and status.",
            "The report may accept stylized institutional neatness only when the evidence shows it is doing character or world work.",
            "Return JSON with keys: status, action, summary, categories, dialogue_samples, blockers, warnings.",
            f"# Official Chapter\n\n{file_body(official, 16000)}",
            f"# Official Brief\n\n{file_body(brief, 7000)}",
            f"# Context Pack\n\n{file_body(context, 9000)}",
            f"# Review Context: Structured State And Key Quotes\n\n{file_body(review_context_md, 8000)}",
            "# Style Contract JSON\n\n" + file_body(ROOT / "state" / "project_style_contract.json", 5000),
            "# Human Style Contract\n\n" + file_body(ROOT / "state" / "project_style_contract.md", 4000),
            "# Style Guide\n\n" + file_body(ROOT / "bible" / "style_guide.md", 4000),
            "# Reader Promise\n\n"
            + file_body(ROOT / "state" / "project_reader_promise.json", 3000)
            + "\n"
            + file_body(ROOT / "state" / "project_reader_promise.md", 3000),
            "# Derived Reader Ledgers\n\n"
            + file_body(ROOT / "state" / "derived" / "personality" / "protagonist.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "protagonist_progression.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "world_reveal_ledger.json", 2500)
            + "\n"
            + file_body(ROOT / "state" / "derived" / "suspense_ledger.json", 2500),
        ]
    )
    return system, user, input_paths


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
            raise ValueError("DeepSeek anti-AI review did not return a JSON object") from None
        data = json.loads(stripped[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("DeepSeek anti-AI review JSON must be an object")
    return data


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().upper()
    if status in {"READY", "CLEAR", "SHIP", "PASS"}:
        return "CLEAR"
    if status in {"WARN", "WARNING", "ADVISORY"}:
        return "WARNING"
    if status in {"BLOCK", "BLOCKED", "NOT_READY", "REVISE", "REWRITE", "FAIL"}:
        return "BLOCKED"
    return "WARNING"


def normalize_severity(value: Any, status: str) -> str:
    severity = str(value or "").strip().upper()
    if severity in SEVERITIES:
        return severity
    return "P2" if status == "BLOCKED" else "P3"


def normalize_category(key: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "status": "BLOCKED",
            "severity": "P1",
            "evidence_quotes": [],
            "issue": f"DeepSeek response omitted required category {key}.",
            "revision_actions": [f"Regenerate the DeepSeek anti-AI review with category {key} filled."],
        }
    status = normalize_status(value.get("status"))
    actions = as_list(value.get("revision_actions") or value.get("actions"))
    issue = str(value.get("issue", "")).strip()
    if not issue:
        issue = "No issue text supplied." if status != "CLEAR" else "No ship-stopping issue found."
    if not actions:
        actions = ["No revision action needed."] if status == "CLEAR" else ["Revise this category before Ship."]
    return {
        "status": status,
        "severity": normalize_severity(value.get("severity"), status),
        "evidence_quotes": as_list(value.get("evidence_quotes") or value.get("quotes")),
        "issue": issue,
        "revision_actions": actions,
    }


def normalize_dialogue_samples(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    samples: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        samples.append(
            {
                "evidence_quote": str(item.get("evidence_quote", "")).strip(),
                "function": str(item.get("function", "")).strip(),
                "character_goal": str(item.get("character_goal", "")).strip(),
                "subtext_or_hidden_agenda": str(item.get("subtext_or_hidden_agenda", "")).strip(),
                "status": normalize_status(item.get("status")),
            }
        )
    return samples


def normalize_report(parsed: dict[str, Any], chapter: str, model: str, inputs: list[Path]) -> dict[str, Any]:
    category_source = parsed.get("categories")
    if not isinstance(category_source, dict):
        category_source = {}
    categories = {key: normalize_category(key, category_source.get(key)) for key in CATEGORIES}
    status = normalize_status(parsed.get("status"))
    if any(item["status"] == "BLOCKED" for item in categories.values()):
        status = "BLOCKED"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "model": model,
        "status": status,
        "action": str(parsed.get("action", "")).strip(),
        "official_chapter": input_ref(chapter_path(chapter)),
        "inputs": [input_ref(path) for path in inputs if path.exists()],
        "summary": str(parsed.get("summary", "")).strip(),
        "categories": categories,
        "dialogue_samples": normalize_dialogue_samples(parsed.get("dialogue_samples")),
        "blockers": as_list(parsed.get("blockers")),
        "warnings": as_list(parsed.get("warnings")),
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    quotes: list[str] = []
    categories = report.get("categories", {})
    if isinstance(categories, dict):
        for item in categories.values():
            if isinstance(item, dict):
                quotes.extend(str(quote).strip() for quote in item.get("evidence_quotes", []) if str(quote).strip())
    for sample in report.get("dialogue_samples", []):
        if isinstance(sample, dict) and str(sample.get("evidence_quote", "")).strip():
            quotes.append(str(sample["evidence_quote"]).strip())
    unique_quotes = list(dict.fromkeys(quotes))
    lines = [
        f"# DeepSeek Anti-AI Review: {report.get('chapter')}",
        "",
        f"status: {report.get('status')}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "review_sha256:",
        f"action: {report.get('action', '')}",
        "",
        "## Summary",
        "",
        str(report.get("summary", "")).strip() or "none",
        "",
        "## Categories",
        "",
    ]
    categories = report.get("categories", {})
    if isinstance(categories, dict):
        for key in CATEGORIES:
            item = categories.get(key, {})
            lines.extend(
                [
                    f"### {key}",
                    "",
                    f"- status: {item.get('status', '')}",
                    f"- severity: {item.get('severity', '')}",
                    f"- issue: {item.get('issue', '')}",
                    "- evidence_quotes:",
                ]
            )
            quotes = item.get("evidence_quotes", [])
            lines.extend(f"  - {quote}" for quote in quotes or ["none"])
            lines.append("- revision_actions:")
            lines.extend(f"  - {action}" for action in item.get("revision_actions", []) or ["none"])
            lines.append("")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        values = report.get(key, [])
        if values:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {item}" for item in values)
            lines.append("")
    lines.extend(["## Evidence Quotes", ""])
    lines.extend(f"- {quote}" for quote in unique_quotes or ["none"])
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_not_ready(message: str) -> None:
    print("# DeepSeek Anti-AI Review")
    print()
    print("status: NOT_READY")
    print()
    print(f"- {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for an independent anti-AI taste review.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default=model_for("deepseek_anti_ai_review"))
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek anti-AI review"):
        return 1
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    official = chapter_path(args.chapter)
    if not official.exists() or not read_text(official).strip():
        print_not_ready(f"missing official chapter text: {rel(official)}")
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
    prompt_path = run_dir / "anti_ai_review.prompt.md"
    raw_path = run_dir / "anti_ai_review.raw.json"
    out_json = ROOT / "reviews" / args.chapter / "deepseek_anti_ai_review.json"
    out_md = ROOT / "reviews" / args.chapter / "deepseek_anti_ai_review.md"
    write_text(prompt_path, f"# System\n\n{system}\n\n# User\n\n{user}\n")
    if args.dry_run:
        write_run_manifest(
            chapter=args.chapter,
            kind="anti_ai_review",
            model=args.model,
            dry_run=True,
            prompt_path=prompt_path,
            input_paths=inputs,
            isolation_attestation="Dry run only wrote the DeepSeek anti-AI prompt and did not read Codex review files or Codex anti-AI reports.",
        )
        print(f"OK: dry run wrote {prompt_path.relative_to(ROOT)}")
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
        print(f"ERROR: invalid DeepSeek anti-AI review response: {exc}", file=sys.stderr)
        return 1

    report = normalize_report(parsed, args.chapter, args.model, inputs)
    write_text(raw_path, json.dumps(response, ensure_ascii=False, indent=2) + "\n")
    write_text(out_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write_text(out_md, markdown_review_with_hash(render_markdown(report)))
    write_run_manifest(
        chapter=args.chapter,
        kind="anti_ai_review",
        model=args.model,
        dry_run=False,
        prompt_path=prompt_path,
        input_paths=inputs,
        raw_response_path=raw_path,
        output_path=out_json,
        isolation_attestation="DeepSeek anti-AI review was not given Codex reviews, Codex anti-AI reports, ai_taste, dialogue_function, or model disagreement files.",
    )
    print(f"OK: wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
