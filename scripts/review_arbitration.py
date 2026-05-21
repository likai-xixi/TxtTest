from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from context_governance import sha256
from review_binding import markdown_review_with_hash


ACTIONS = ("Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project")
BLOCKING_ACTIONS = {"Rewrite brief", "Kill chapter", "Pause project"}
SOURCE_NAMES = (
    "codex_integrated_review.md",
    "deepseek_integrated_review.md",
    "model_disagreement.md",
    "continuity.md",
    "ai_taste.json",
    "dialogue_function.json",
    "codex_anti_ai_review.json",
    "deepseek_anti_ai_review.json",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def extract_action(text: str) -> str | None:
    for action in ACTIONS:
        if re.search(re.escape(action), text, re.I):
            return action
    return None


def review_action(path: Path) -> str | None:
    text = read_text(path)
    for line in text.splitlines():
        if "action" in line.lower() or "decision" in line.lower() or "suggest" in line.lower():
            found = extract_action(line)
            if found:
                return found
    return extract_action(text)


def json_blockers(path: Path) -> list[str]:
    data = read_json(path, {})
    blockers: list[str] = []
    if not isinstance(data, dict):
        return [f"{rel(path)} is malformed"]
    status = str(data.get("status", "")).upper()
    if status in {"BLOCKED", "NOT_READY"}:
        blockers.append(f"{rel(path)} status is {status}")
    if isinstance(data.get("blockers"), list):
        blockers.extend(f"{rel(path)} blocker: {item}" for item in data["blockers"])
    for container_name in ("categories",):
        container = data.get(container_name)
        if not isinstance(container, dict):
            continue
        for name, item in container.items():
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "")).upper()
            item_status = str(item.get("status", "")).upper()
            if item_status == "BLOCKED" or severity in {"P0", "P1"}:
                blockers.append(f"{rel(path)} {name} {item_status or severity}: {item.get('issue', '')}")
    for sample_key in ("samples", "dialogue_samples"):
        samples = data.get(sample_key)
        if not isinstance(samples, list):
            continue
        for index, sample in enumerate(samples, 1):
            if isinstance(sample, dict) and str(sample.get("status", "")).upper() == "BLOCKED":
                blockers.append(f"{rel(path)} {sample_key} #{index} is BLOCKED")
    return blockers


def text_blockers(path: Path) -> list[str]:
    text = read_text(path)
    blockers: list[str] = []
    if re.search(r"\bP[01]\b", text) and re.search(r"BLOCKED|Rewrite brief|Kill chapter|Pause project|NOT_READY", text, re.I):
        blockers.append(f"{rel(path)} contains unresolved P0/P1 or blocking action")
    action = review_action(path)
    if action in BLOCKING_ACTIONS:
        blockers.append(f"{rel(path)} recommends {action}")
    status_match = re.search(r"^status\s*[:：]\s*(.+?)\s*$", text, re.I | re.M)
    if status_match and status_match.group(1).strip() in {"CONFLICT", "NEEDS_HUMAN", "BLOCKED"}:
        blockers.append(f"{rel(path)} status is {status_match.group(1).strip()}")
    return blockers


def evaluate(chapter: str) -> dict[str, Any]:
    official = official_path(chapter)
    review_dir = ROOT / "reviews" / chapter
    sources = []
    blockers: list[str] = []
    warnings: list[str] = []
    actions: dict[str, str | None] = {}

    if not official.exists() or not read_text(official).strip():
        blockers.append(f"missing official chapter: {rel(official)}")

    for name in SOURCE_NAMES:
        path = review_dir / name
        if not path.exists():
            blockers.append(f"missing review source: {rel(path)}")
            continue
        sources.append(ref(path))
        if name.endswith(".json"):
            blockers.extend(json_blockers(path))
        else:
            blockers.extend(text_blockers(path))
            if name in {"codex_integrated_review.md", "deepseek_integrated_review.md"}:
                actions[name.removesuffix(".md")] = review_action(path)

    codex_action = actions.get("codex_integrated_review")
    deepseek_action = actions.get("deepseek_integrated_review")
    if codex_action and deepseek_action and codex_action != deepseek_action:
        blockers.append(f"Codex and DeepSeek actions conflict: Codex={codex_action}, DeepSeek={deepseek_action}")
    elif not codex_action or not deepseek_action:
        blockers.append("Codex and DeepSeek actions must both be identifiable before Ship.")
    if codex_action == deepseek_action and codex_action == "Ship" and not blockers:
        status = "READY"
        recommendation = "Ship"
    elif any(action in BLOCKING_ACTIONS for action in (codex_action, deepseek_action)):
        status = "BLOCKED"
        recommendation = "Human arbitration required before Ship."
    elif blockers:
        status = "NEEDS_HUMAN"
        recommendation = "Resolve blockers or record a legal human acceptance."
    else:
        status = "READY"
        recommendation = codex_action or deepseek_action or "Ship"

    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "recommendation": recommendation,
        "official_chapter": ref(official),
        "input_hashes": [ref(official), *sources] if official.exists() else sources,
        "codex_action": codex_action or "UNKNOWN",
        "deepseek_action": deepseek_action or "UNKNOWN",
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    quote = ""
    official = official_path(report["chapter"])
    if official.exists():
        for line in read_text(official).splitlines():
            if line.strip():
                quote = line.strip()[:140]
                break
    lines = [
        f"# Review Arbitration: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "review_sha256:",
        f"codex_action: {report.get('codex_action')}",
        f"deepseek_action: {report.get('deepseek_action')}",
        f"recommendation: {report.get('recommendation')}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("blockers") or ["none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["none"])
    lines.extend(["", "## Evidence Quotes", ""])
    lines.append(f"- {quote}" if quote else "- none")
    lines.extend(["", "## Human Arbitration", "", "- Required when status is NEEDS_HUMAN or BLOCKED."])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Arbitrate Codex and DeepSeek chapter review conflicts.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "review_arbitration.json", report)
        write_text(out_dir / "review_arbitration.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
