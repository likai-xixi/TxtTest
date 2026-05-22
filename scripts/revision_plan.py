from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from chapter_evidence import chapter_evidence_failures
from context_governance import sha256


SOURCE_FILES = (
    "codex_integrated_review.md",
    "deepseek_integrated_review.md",
    "model_disagreement.md",
    "continuity.md",
    "ai_taste.json",
    "dialogue_function.json",
    "emotion_relationship_gate.json",
    "codex_semantic_reader_review.json",
    "deepseek_semantic_reader_review.json",
    "semantic_reader_review.json",
    "memorable_scene.json",
    "codex_anti_ai_review.json",
    "deepseek_anti_ai_review.json",
    "review_arbitration.json",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def item(source: str, severity: str, issue: str, action: str, evidence_quote: str = "") -> dict[str, str]:
    return {
        "source": source,
        "severity": severity,
        "issue": issue.strip(),
        "revision_action": action.strip(),
        "evidence_quote": evidence_quote.strip(),
    }


def severity_from_text(text: str) -> str:
    match = re.search(r"\b(P[0-3])\b", text)
    return match.group(1) if match else "P2"


def markdown_findings(path: Path) -> list[dict[str, str]]:
    text = read_text(path)
    findings: list[dict[str, str]] = []
    for raw in text.splitlines():
        stripped_raw = raw.strip()
        if not stripped_raw or stripped_raw.startswith("#"):
            continue
        if all(action in stripped_raw for action in ("Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project")):
            continue
        line = stripped_raw.lstrip("-* ")
        if not line:
            continue
        lowered = line.lower()
        if "rewrite brief" in lowered or "kill chapter" in lowered or "pause project" in lowered:
            findings.append(item(rel(path), "P1", line, "Resolve this blocking review action before Ship."))
        elif "blocked" in lowered or re.search(r"\bP[01]\b", line):
            findings.append(item(rel(path), severity_from_text(line), line, "Revise the chapter or provide a legal human arbitration."))
        elif "warning" in lowered or re.search(r"\bP[23]\b", line):
            findings.append(item(rel(path), severity_from_text(line), line, "Review and revise if it weakens the reader promise."))
    return findings[:20]


def structured_findings(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    data = read_json(path, {})
    must: list[dict[str, str]] = []
    should: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return must, should
    status = str(data.get("status", "")).upper()
    source = rel(path)
    for blocker in data.get("blockers", []) if isinstance(data.get("blockers"), list) else []:
        must.append(item(source, "P1", str(blocker), "Fix this blocker and rerun the source review."))
    categories = data.get("categories", {})
    if isinstance(categories, dict):
        for name, value in categories.items():
            if not isinstance(value, dict):
                continue
            severity = str(value.get("severity") or "P2").upper()
            issue = str(value.get("issue") or name)
            action_values = value.get("revision_actions") or []
            action = "; ".join(map(str, action_values)) if isinstance(action_values, list) else str(action_values)
            quote_values = value.get("evidence_quotes") or []
            quote = str(quote_values[0]) if isinstance(quote_values, list) and quote_values else ""
            target = must if value.get("status") == "BLOCKED" or severity in {"P0", "P1"} else should
            target.append(item(source, severity, f"{name}: {issue}", action or "Revise this review category.", quote))
    samples = data.get("samples") or data.get("dialogue_samples")
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            if str(sample.get("status", "")).upper() == "BLOCKED":
                must.append(
                    item(
                        source,
                        "P1",
                        str(sample.get("evidence_quote") or sample.get("function") or "blocked dialogue sample"),
                        "Rewrite this dialogue beat so it has pressure, desire, concealment, or information movement.",
                        str(sample.get("evidence_quote") or ""),
                    )
                )
    if status in {"BLOCKED", "NOT_READY"} and not must:
        must.append(item(source, "P1", f"{source} status is {status}", "Resolve this source report before Ship."))
    return must, should


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_path(chapter)
    if not official.exists() or not read_text(official).strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": ref(official),
            "input_hashes": [],
            "must_fix": [item("official_chapter", "P1", f"missing official chapter: {rel(official)}", "Land the official chapter first.")],
            "should_fix": [],
            "human_acceptance_allowed": [],
        }

    review_dir = ROOT / "reviews" / chapter
    must_fix: list[dict[str, str]] = []
    should_fix: list[dict[str, str]] = []
    human_acceptance_allowed: list[dict[str, str]] = []
    input_hashes = [ref(official)]

    for name in SOURCE_FILES:
        path = review_dir / name
        if not path.exists():
            should_fix.append(item(rel(path), "P2", f"missing optional source for revision synthesis: {name}", f"Generate {name} if the chapter is being closed."))
            continue
        input_hashes.append(ref(path))
        if name.endswith(".json"):
            must, should = structured_findings(path)
            must_fix.extend(must)
            should_fix.extend(should)
        else:
            for found in markdown_findings(path):
                (must_fix if found["severity"] in {"P0", "P1"} else should_fix).append(found)

    for failure in chapter_evidence_failures(chapter, include_revision_closure=False):
        severity = "P1" if any(token in failure for token in ("missing", "BLOCKED", "P0", "P1", "hash", "stale")) else "P2"
        must_fix.append(item("chapter_evidence", severity, failure, "Fix the evidence blocker or rerun the affected workflow step."))

    for found in should_fix:
        if any(token in found["source"] for token in ("ai_taste", "dialogue_function", "series_style", "codex_anti_ai", "deepseek_anti_ai", "chapter_shape", "reader_feedback")):
            human_acceptance_allowed.append(
                item(found["source"], found["severity"], found["issue"], "Use accept-review only if the human editor intentionally accepts this taste risk.", found.get("evidence_quote", ""))
            )

    status = "NOT_READY" if must_fix else "READY"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": ref(official),
        "input_hashes": input_hashes,
        "must_fix": must_fix[:50],
        "should_fix": should_fix[:50],
        "human_acceptance_allowed": human_acceptance_allowed[:30],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Revision Plan: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        f"generated_at: {report['generated_at']}",
        "",
    ]
    for key, title in (
        ("must_fix", "Must Fix"),
        ("should_fix", "Should Fix"),
        ("human_acceptance_allowed", "Human Acceptance Allowed"),
    ):
        lines.extend([f"## {title}", ""])
        values = report.get(key, [])
        if not values:
            lines.append("- none")
        for entry in values:
            quote = f" quote={entry.get('evidence_quote')}" if entry.get("evidence_quote") else ""
            lines.append(
                f"- [{entry.get('severity')}] {entry.get('issue')} -> {entry.get('revision_action')} "
                f"(source={entry.get('source')}{quote})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a structured chapter revision plan from all review evidence.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "revision_plan.json", report)
        write_text(out_dir / "revision_plan.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
