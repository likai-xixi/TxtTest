from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts, now_iso, read_json
from context_governance import sha256


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def decision_value(chapter: str) -> str:
    data = read_json(ROOT / "reviews" / chapter / "decision.json", {})
    if isinstance(data, dict) and data.get("decision"):
        return str(data["decision"])
    path = ROOT / "reviews" / chapter / "decision.md"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return ""


def ref_current(item: Any) -> tuple[bool, str]:
    if not isinstance(item, dict):
        return False, "missing path/sha256"
    path_text = str(item.get("path") or "")
    expected = str(item.get("sha256") or "")
    if not path_text or not expected:
        return False, "missing path/sha256"
    path = ROOT / path_text
    if not path.exists():
        return False, f"missing input: {path_text}"
    if sha256(path) != expected:
        return False, f"stale input: {path_text}"
    return True, ""


def input_hash_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    values = data.get("input_hashes", [])
    if not values:
        return failures
    if not isinstance(values, list):
        return ["revision_plan.json input_hashes must be a list"]
    for item in values:
        ok, message = ref_current(item)
        if not ok:
            failures.append(message)
    return failures


def evaluate(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    decision = decision_value(chapter)
    path = ROOT / "reviews" / chapter / "revision_plan.json"
    blockers: list[str] = []
    warnings: list[str] = []
    plan: dict[str, Any] = {}
    required = decision == "Revise once"

    if not path.exists():
        if not required:
            return {
                "schema_version": 1,
                "chapter": chapter,
                "generated_at": now_iso(),
                "status": "READY",
                "decision": decision or "MISSING",
                "required": False,
                "revision_plan": {"path": rel(path), "exists": False},
                "blockers": blockers,
                "warnings": warnings,
                "writes_canon": False,
                "writes_event_ledger": False,
            }
        blockers.append(f"Revise once requires current revision_plan.json: {rel(path)}")
    else:
        try:
            data = read_json(path, {})
        except Exception as exc:
            data = {}
            blockers.append(f"revision_plan.json invalid JSON: {exc}")
        if not isinstance(data, dict):
            blockers.append("revision_plan.json must be a JSON object")
            data = {}
        plan = data
        official = official_path(chapter)
        official_ref = data.get("official_chapter")
        if not isinstance(official_ref, dict):
            blockers.append("revision_plan.json missing official_chapter")
        elif official.exists() and official_ref.get("sha256") != sha256(official):
            blockers.append("revision_plan.json official chapter hash is stale")
        blockers.extend(input_hash_failures(data))
        if str(data.get("status", "")).upper() != "READY":
            blockers.append(f"revision_plan.json status is {data.get('status') or 'MISSING'}; expected READY")
        must_fix = data.get("must_fix", [])
        if isinstance(must_fix, list) and must_fix:
            blockers.append(f"revision_plan.json still has {len(must_fix)} must_fix item(s)")
        elif not isinstance(must_fix, list):
            blockers.append("revision_plan.json must_fix must be a list")

    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "BLOCKED" if blockers else "READY",
        "decision": decision,
        "required": True,
        "revision_plan": {
            "path": rel(path),
            "exists": path.exists(),
            "status": plan.get("status") if plan else None,
            "must_fix_count": len(plan.get("must_fix", [])) if isinstance(plan.get("must_fix"), list) else None,
        },
        "blockers": blockers,
        "warnings": warnings,
        "writes_canon": False,
        "writes_event_ledger": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Revision Closure: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"decision: {report.get('decision', '')}",
        f"required: {str(bool(report.get('required'))).lower()}",
        "",
        "## Revision Plan",
        "",
    ]
    plan = report.get("revision_plan") or {}
    for key in ("path", "exists", "status", "must_fix_count"):
        lines.append(f"- {key}: {plan.get(key)}")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        items = report.get(key) or []
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that a Revise once decision has been closed before Ship.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
