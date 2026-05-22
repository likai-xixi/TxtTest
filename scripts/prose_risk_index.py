from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, write_json, write_text
from context_governance import sha256


TRACKED_CATEGORIES = (
    "subject_repetition",
    "process_bloat",
    "protagonist_invulnerable",
    "flat_side_character",
    "homogeneous_hook",
    "qa_dialogue",
    "anomaly_density",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def chapter_id(volume: str, number: int) -> str:
    return f"{volume}_c{number:03d}"


def file_ref(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "exists": True} if path.exists() else {"path": rel(path), "sha256": "", "exists": False}


def report_status(blockers: list[str], warnings: list[str]) -> str:
    return "BLOCKED" if blockers else "WARNING" if warnings else "READY"


def category_flag(report: dict[str, Any], key: str) -> bool:
    category = (report.get("categories") or {}).get(key)
    if not isinstance(category, dict):
        return False
    return str(category.get("status", "")).upper() in {"WARNING", "BLOCKED"}


def category_blocked(report: dict[str, Any], key: str) -> bool:
    category = (report.get("categories") or {}).get(key)
    if not isinstance(category, dict):
        return False
    return str(category.get("status", "")).upper() == "BLOCKED"


def hook_type(report: dict[str, Any]) -> str:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    return str(metrics.get("ending_hook_type") or "")


def category_issue(report: dict[str, Any], key: str) -> str:
    category = (report.get("categories") or {}).get(key)
    return str(category.get("issue", "")) if isinstance(category, dict) else ""


def evaluate(to_chapter: str | None = None) -> dict[str, Any]:
    target = to_chapter or "v01_c001"
    target_number = chapter_number(target)
    volume = target[:3]
    chapters: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    category_blockers: dict[str, list[str]] = {key: [] for key in TRACKED_CATEGORIES}
    category_warnings: dict[str, list[str]] = {key: [] for key in TRACKED_CATEGORIES}
    runs = {key: 0 for key in TRACKED_CATEGORIES}
    previous_hook = ""
    hook_run = 0

    for number in range(1, target_number + 1):
        chapter = chapter_id(volume, number)
        prose_path = ROOT / "reviews" / chapter / "prose_risk.json"
        shape_path = ROOT / "reviews" / chapter / "chapter_shape.json"
        item: dict[str, Any] = {
            "chapter": chapter,
            "prose_risk": file_ref(prose_path),
            "chapter_shape": file_ref(shape_path),
            "category_flags": {},
            "blockers": [],
            "warnings": [],
        }
        if not prose_path.exists():
            item["blockers"].append(f"missing prose risk report reviews/{chapter}/prose_risk.json")
            chapters.append(item)
            blockers.append(f"{chapter}: missing prose risk report")
            continue
        report = read_json(prose_path, {})
        if not isinstance(report, dict):
            item["blockers"].append("prose_risk.json is malformed")
            chapters.append(item)
            blockers.append(f"{chapter}: prose_risk.json is malformed")
            continue

        status = str(report.get("status", "")).upper()
        if status == "BLOCKED" and category_blocked(report, "anomaly_density"):
            message = f"{chapter}: unauthorized anomaly or high anomaly density is BLOCKED"
            item["blockers"].append(message)
            category_blockers["anomaly_density"].append(message)
        elif status == "BLOCKED" and number < 6:
            item["warnings"].append("warmup chapter has blocked prose risk; treat as editor warning unless it is unauthorized anomaly")

        for key in TRACKED_CATEGORIES:
            flagged = category_flag(report, key)
            item["category_flags"][key] = flagged
            runs[key] = runs[key] + 1 if flagged else 0
            if flagged:
                issue = category_issue(report, key)
                if number < 4:
                    category_warnings[key].append(f"{chapter}: warmup {key} signal: {issue}")
                elif number < 6:
                    category_warnings[key].append(f"{chapter}: observation {key} signal requires next_chapter_obligation: {issue}")
                elif runs[key] >= 2 and key in {"protagonist_invulnerable", "process_bloat", "qa_dialogue", "anomaly_density"}:
                    category_blockers[key].append(f"{chapter}: {key} repeats for {runs[key]} checked chapters")
                elif runs[key] >= 3:
                    category_blockers[key].append(f"{chapter}: {key} repeats for {runs[key]} checked chapters")
                else:
                    category_warnings[key].append(f"{chapter}: {key} signal: {issue}")

        current_hook = hook_type(report)
        if current_hook and current_hook != "unclear" and current_hook == previous_hook:
            hook_run += 1
        elif current_hook:
            hook_run = 1
        previous_hook = current_hook or previous_hook
        item["hook_type"] = current_hook
        item["hook_repeat_run"] = hook_run
        if current_hook and hook_run >= 3:
            message = f"{chapter}: ending hook type {current_hook} repeats for {hook_run} chapters"
            if number >= 6:
                category_blockers["homogeneous_hook"].append(message)
            else:
                category_warnings["homogeneous_hook"].append(message)

        chapters.append(item)

    for key, values in category_blockers.items():
        blockers.extend(f"{key}: {value}" for value in values)
    for key, values in category_warnings.items():
        warnings.extend(f"{key}: {value}" for value in values)

    source_event = ROOT / "state" / "event_ledger.jsonl"
    category_statuses = {
        key: report_status(category_blockers[key], category_warnings[key])
        for key in TRACKED_CATEGORIES
    }
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": report_status(blockers, warnings),
        "through": target,
        "chapters_checked": target_number,
        "window": 3,
        "category_statuses": category_statuses,
        "category_blockers": category_blockers,
        "category_warnings": category_warnings,
        "chapters": chapters,
        "source_event_ledger": file_ref(source_event),
        "blockers": blockers,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Prose Risk Index: through {report['through']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"chapters_checked: {report['chapters_checked']}",
        "",
        "## Category Statuses",
        "",
    ]
    for key, value in report.get("category_statuses", {}).items():
        lines.append(f"- {key}: {value}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {value}" for value in values) if values else lines.append("- none")
    lines.extend(["", "## Recent Chapters", ""])
    for item in report.get("chapters", [])[-10:]:
        flags = [key for key, value in (item.get("category_flags") or {}).items() if value]
        lines.append(f"- {item.get('chapter')}: hook={item.get('hook_type', '')} flags={', '.join(flags) or 'none'}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the cross-chapter prose-risk index.")
    parser.add_argument("--to", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.to)
    if args.write:
        out_dir = ROOT / "state" / "derived" / "prose_risk"
        write_json(out_dir / "latest.json", report)
        write_text(out_dir / "latest.md", render_markdown(report))
        print(f"wrote: {(out_dir / 'latest.md').relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
