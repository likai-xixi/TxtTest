from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json, read_text, write_json, write_text


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def has_chapter_anchor(chapter: str) -> bool:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("chapter") == chapter and entry.get("type") == "chapter_anchor" and entry.get("verified_by") == "human":
            return True
    return False


def file_status(path: Path, label: str) -> dict[str, Any]:
    exists = path.exists() and bool(read_text(path).strip() if path.suffix == ".md" else path.read_bytes())
    return {
        "name": label,
        "command": [],
        "status": "READY" if exists else "NOT_READY",
        "returncode": 0 if exists else 1,
        "output": f"found {rel(path)}" if exists else f"missing {rel(path)}",
        "artifacts": [rel(path)],
    }


def run_command(name: str, args: list[str]) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts" / "novel.py"), *args]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
    output = (result.stdout or "") + (result.stderr or "")
    return {
        "name": name,
        "command": ["python", "scripts/novel.py", *args],
        "status": "READY" if result.returncode == 0 else "NOT_READY",
        "returncode": result.returncode,
        "output": output.strip(),
        "artifacts": [],
    }


def should_skip(primary: Path | None, resume: bool) -> bool:
    return bool(resume and primary and primary.exists())


def planned_steps(chapter: str, *, run_deepseek: bool) -> list[dict[str, Any]]:
    return [
        {"name": "selection", "command": [], "writes": []},
        {"name": "landing", "command": [], "writes": []},
        {"name": "codex_review", "command": [], "writes": []},
        {"name": "review_context", "command": ["review-context", chapter, "--write"], "writes": [f"state/context_pack/{chapter}_review_context.json"]},
        {"name": "codex_anti_ai_start", "command": ["codex-anti-ai-review-start", chapter], "writes": [f"reviews/{chapter}/codex_anti_ai_review_manifest.json"]},
        {"name": "codex_anti_ai_review", "command": [], "writes": [f"reviews/{chapter}/codex_anti_ai_review.json"]},
        {"name": "deepseek_review", "command": ["review", chapter, "--deepseek"] if run_deepseek else [], "writes": [f"reviews/{chapter}/deepseek_integrated_review.md"]},
        {"name": "deepseek_anti_ai", "command": ["deepseek-anti-ai-review", chapter] if run_deepseek else [], "writes": [f"reviews/{chapter}/deepseek_anti_ai_review.json"]},
        {"name": "context-quality", "command": ["context-quality", chapter], "writes": []},
        {"name": "style-check", "command": ["style-check", chapter], "writes": [f"reviews/{chapter}/style_metrics.json"]},
        {"name": "series-style-check", "command": ["series-style-check", chapter], "writes": [f"reviews/{chapter}/series_style.json"]},
        {"name": "ai-taste-check", "command": ["ai-taste-check", chapter], "writes": [f"reviews/{chapter}/ai_taste.json"]},
        {"name": "dialogue-function-check", "command": ["dialogue-function-check", chapter], "writes": [f"reviews/{chapter}/dialogue_function.json"]},
        {"name": "continuity", "command": ["continuity", chapter], "writes": [f"reviews/{chapter}/continuity.md"]},
        {"name": "compare", "command": ["compare", chapter], "writes": [f"reviews/{chapter}/model_disagreement.md"]},
        {"name": "fact-cards", "command": ["fact-cards", chapter, "--write"], "writes": [f"reviews/{chapter}/fact_cards.json"]},
        {"name": "review-arbitration", "command": ["review-arbitration", chapter], "writes": [f"reviews/{chapter}/review_arbitration.json"]},
        {"name": "revision-plan", "command": ["revision-plan", chapter], "writes": [f"reviews/{chapter}/revision_plan.json"]},
        {"name": "gray-consequence", "command": ["gray-consequence", chapter, "--write"], "writes": [f"reviews/{chapter}/gray_consequence.json"]},
        {"name": "chapter-shape-check", "command": ["chapter-shape-check", chapter, "--write"], "writes": [f"reviews/{chapter}/chapter_shape.json"]},
        {"name": "reader-reward-check", "command": ["reader-reward-check", chapter, "--write"], "writes": [f"reviews/{chapter}/reader_reward_gate.json"]},
        {"name": "reader-reward-index", "command": ["reader-reward-index", "--write"], "writes": ["state/derived/pacing/reader_reward_index.json"]},
        {"name": "reader-feedback", "command": ["reader-feedback", "summarize", chapter], "writes": [f"reviews/{chapter}/reader_feedback.json"]},
        {"name": "chapter-evidence", "command": ["evidence", chapter], "writes": []},
    ]


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    chapter_parts(args.chapter)
    review_dir = ROOT / "reviews" / args.chapter
    steps: list[dict[str, Any]] = []

    if args.preview:
        return {
            "schema_version": 1,
            "chapter": args.chapter,
            "generated_at": now_iso(),
            "status": "PREVIEW",
            "steps": planned_steps(args.chapter, run_deepseek=args.run_deepseek),
            "next_action": "Run without --preview when ready to execute local checks.",
        }

    prerequisites = [
        (ROOT / "state" / "selections" / f"{args.chapter}.json", "candidate_selection"),
        (review_dir / "chapter_landing.json", "chapter_landing"),
        (official_path(args.chapter), "official_chapter"),
        (review_dir / "codex_integrated_review.md", "codex_integrated_review"),
        (review_dir / "codex_anti_ai_review.json", "codex_anti_ai_review"),
    ]
    for path, label in prerequisites:
        steps.append(file_status(path, label))

    if args.run_deepseek:
        if not should_skip(review_dir / "deepseek_integrated_review.md", args.resume):
            steps.append(run_command("deepseek_review", ["review", args.chapter, "--deepseek"]))
        if not should_skip(review_dir / "deepseek_anti_ai_review.json", args.resume):
            steps.append(run_command("deepseek_anti_ai", ["deepseek-anti-ai-review", args.chapter]))
    else:
        steps.append(file_status(review_dir / "deepseek_integrated_review.md", "deepseek_integrated_review"))
        steps.append(file_status(review_dir / "deepseek_anti_ai_review.json", "deepseek_anti_ai_review"))

    command_steps = [
        ("review-context", ["review-context", args.chapter, "--write"], ROOT / "state" / "context_pack" / f"{args.chapter}_review_context.json"),
        ("context-quality", ["context-quality", args.chapter], None),
        ("style-check", ["style-check", args.chapter], review_dir / "style_metrics.json"),
        ("series-style-check", ["series-style-check", args.chapter], review_dir / "series_style.json"),
        ("ai-taste-check", ["ai-taste-check", args.chapter], review_dir / "ai_taste.json"),
        ("dialogue-function-check", ["dialogue-function-check", args.chapter], review_dir / "dialogue_function.json"),
        ("continuity", ["continuity", args.chapter], review_dir / "continuity.md"),
        ("compare", ["compare", args.chapter], review_dir / "model_disagreement.md"),
        ("fact-cards", ["fact-cards", args.chapter, "--write"], review_dir / "fact_cards.json"),
        ("review-arbitration", ["review-arbitration", args.chapter], review_dir / "review_arbitration.json"),
        ("revision-plan", ["revision-plan", args.chapter], review_dir / "revision_plan.json"),
        ("gray-consequence", ["gray-consequence", args.chapter, "--write"], review_dir / "gray_consequence.json"),
        ("chapter-shape-check", ["chapter-shape-check", args.chapter, "--write"], review_dir / "chapter_shape.json"),
        ("reader-reward-check", ["reader-reward-check", args.chapter, "--write"], review_dir / "reader_reward_gate.json"),
        ("reader-reward-index", ["reader-reward-index", "--write"], ROOT / "state" / "derived" / "pacing" / "reader_reward_index.json"),
        ("reader-feedback", ["reader-feedback", "summarize", args.chapter], review_dir / "reader_feedback.json"),
        ("chapter-evidence", ["evidence", args.chapter], None),
    ]
    for name, command, primary in command_steps:
        if should_skip(primary, args.resume):
            steps.append({"name": name, "command": ["python", "scripts/novel.py", *command], "status": "SKIPPED", "returncode": 0, "output": f"resume kept {rel(primary)}", "artifacts": [rel(primary)]})
            continue
        result = run_command(name, command)
        if name == "reader-feedback" and result["returncode"] != 0:
            result["status"] = "WARNING"
        steps.append(result)

    if not has_chapter_anchor(args.chapter):
        steps.append(
            {
                "name": "chapter_anchor",
                "command": [],
                "status": "NOT_READY",
                "returncode": 1,
                "output": "missing human-verified chapter_anchor event",
                "artifacts": ["state/event_ledger.jsonl"],
            }
        )

    failed = [step for step in steps if step["status"] not in {"READY", "SKIPPED", "WARNING"}]
    return {
        "schema_version": 1,
        "chapter": args.chapter,
        "generated_at": now_iso(),
        "status": "READY" if not failed else "NOT_READY",
        "steps": steps,
        "next_action": next_action(args.chapter, failed),
    }


def next_action(chapter: str, failed: list[dict[str, Any]]) -> str:
    if not failed:
        return f"Run `python scripts/novel.py close {chapter} --decision Ship ...` after human editor confirms."
    first = failed[0]["name"]
    mapping = {
        "candidate_selection": f"Run `python scripts/novel.py select-candidate {chapter} --choice ...`.",
        "chapter_landing": f"Run `python scripts/novel.py land {chapter} --selected-direction ... --attestation ...`.",
        "codex_integrated_review": f"Run `python scripts/novel.py codex-review-start {chapter}`, then write the independent Codex review.",
        "codex_anti_ai_review": f"Run `python scripts/novel.py codex-anti-ai-review-start {chapter}`, then complete the isolated Codex anti-AI review.",
        "deepseek_integrated_review": f"Run `python scripts/novel.py review {chapter} --deepseek`.",
        "deepseek_anti_ai_review": f"Run `python scripts/novel.py deepseek-anti-ai-review {chapter}`.",
        "chapter_anchor": f"Run `python scripts/novel.py event {chapter} --type chapter_anchor ...`.",
    }
    return mapping.get(first, f"Fix `{first}` and rerun `python scripts/novel.py receive-chapter {chapter} --resume`.")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Receive Chapter: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"next_action: {report.get('next_action', '')}",
        "",
        "## Steps",
        "",
    ]
    for step in report.get("steps", []):
        command = " ".join(step.get("command") or [])
        lines.append(f"- {step.get('name')}: {step.get('status')} rc={step.get('returncode')} command={command or 'n/a'}")
        output = str(step.get("output", "")).strip().splitlines()
        if output:
            lines.append(f"  output: {output[0][:180]}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full receive-chapter control plane without auto-shipping.")
    parser.add_argument("chapter")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-deepseek", action="store_true", help="Call live DeepSeek review steps when their artifacts are missing.")
    args = parser.parse_args()
    report = evaluate(args)
    if args.preview:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    out_dir = ROOT / "reviews" / args.chapter
    write_json(out_dir / "receive_chapter.json", report)
    write_text(out_dir / "receive_chapter.md", render_markdown(report))
    print(render_markdown(report), end="")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
