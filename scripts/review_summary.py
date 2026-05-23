from __future__ import annotations

import argparse
import json
from typing import Any

from _common import ROOT, now_iso, read_json, write_json, write_text
from chapter_evidence import always_required_ship_gate_failures, literary_review_failures
from product_kernel import file_ref, official_chapter_path, review_dir, review_route_path, route_artifact_status


def highlight_preserve_items(chapter: str) -> list[dict[str, str]]:
    data = read_json(review_dir(chapter) / "highlights_review.json", {})
    items: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return items
    for highlight in data.get("protected_highlights", []) if isinstance(data.get("protected_highlights"), list) else []:
        if not isinstance(highlight, dict):
            continue
        items.append(
            {
                "highlight_id": str(highlight.get("highlight_id", "")),
                "type": str(highlight.get("type", "")),
                "quote": str(highlight.get("quote", "")),
                "protection_level": str(highlight.get("protection_level", "")),
            }
        )
    return items


def route_display(route: str) -> str:
    return route.upper() if route in {"fast", "normal", "heavy", "gate"} else "HEAVY"


def ai_risk_summary(chapter: str, route_data: dict[str, Any]) -> dict[str, Any]:
    route_reviews = set(route_data.get("additional_literary_reviews", []) if isinstance(route_data, dict) else [])
    source_names = {
        "ai_taste": "ai_taste.json",
        "prose_risk": "prose_risk.json",
        "codex_anti_ai": "codex_anti_ai_review.json",
        "deepseek_anti_ai": "deepseek_anti_ai_review.json",
    }
    order = {"MISSING": 0, "CLEAR": 1, "ACCEPTED_BY_HUMAN": 1, "WARNING": 2, "NOT_READY": 3, "BLOCKED": 3}
    status = "MISSING"
    sources: list[dict[str, str]] = []
    issues: list[str] = []
    for review_key, filename in source_names.items():
        path = review_dir(chapter) / filename
        required = review_key in route_reviews
        if not path.exists():
            if required:
                issues.append(f"missing required AI-risk source {filename}")
                status = "BLOCKED"
            continue
        try:
            data = read_json(path, {})
        except Exception as exc:
            issues.append(f"{filename} cannot be parsed: {exc}")
            status = "BLOCKED"
            continue
        if not isinstance(data, dict):
            issues.append(f"{filename} is not a JSON object")
            status = "BLOCKED"
            continue
        source_status = str(data.get("status", "UNKNOWN"))
        sources.append({"review": review_key, "path": filename, "status": source_status})
        if order.get(source_status, 0) > order.get(status, 0):
            status = "BLOCKED" if source_status == "NOT_READY" else source_status
        for item in data.get("blockers", []) if isinstance(data.get("blockers"), list) else []:
            if str(item).strip():
                issues.append(f"{filename}: {item}")
        for item in data.get("warnings", []) if isinstance(data.get("warnings"), list) else []:
            if str(item).strip() and len(issues) < 12:
                issues.append(f"{filename}: {item}")
        categories = data.get("categories")
        if isinstance(categories, dict):
            for key, value in categories.items():
                if not isinstance(value, dict):
                    continue
                category_status = str(value.get("status", ""))
                severity = str(value.get("severity", ""))
                issue = str(value.get("issue", "")).strip()
                if category_status in {"BLOCKED", "WARNING"} or severity in {"P0", "P1"}:
                    issues.append(f"{filename} {key}: {category_status or severity} {issue}".strip())
                    if category_status == "BLOCKED" and order["BLOCKED"] > order.get(status, 0):
                        status = "BLOCKED"
                    elif category_status == "WARNING" and order["WARNING"] > order.get(status, 0):
                        status = "WARNING"
    if not sources and status == "MISSING" and not issues:
        issues.append("no AI-risk review sources present")
    return {
        "status": status,
        "sources": sources,
        "issues": issues[:12],
    }


def preview_route_status(chapter: str) -> tuple[str, list[str], dict[str, Any]]:
    from route_reviews import evaluate as evaluate_route

    route_data = evaluate_route(chapter)
    route = str(route_data.get("route", "heavy")).lower()
    if route not in {"fast", "normal", "heavy", "gate"}:
        route = "heavy"
    failures: list[str] = []
    if route_data.get("status") == "BLOCKED":
        failures.extend(str(item) for item in route_data.get("blockers", []) if str(item).strip())
    if route_data.get("fail_closed") is True:
        failures.extend(str(item) for item in route_data.get("warnings", []) if str(item).strip())
        if not failures:
            failures.append(f"{chapter}: route preview fail_closed requires rerun before Ship")
    return route, failures, route_data


def evaluate(chapter: str, *, preview_route: bool = False) -> dict[str, Any]:
    if preview_route:
        route, route_failures, route_data = preview_route_status(chapter)
    else:
        route, route_failures, route_data = route_artifact_status(chapter)
    always_failures = route_failures + always_required_ship_gate_failures(chapter)
    literary_failures = literary_review_failures(
        chapter,
        route,
        route_data=route_data,
        include_revision_closure=False,
    )
    ai_risk = ai_risk_summary(chapter, route_data)
    must_fix = always_failures + literary_failures
    ship_gates = "CLEAR" if not always_failures else "BLOCKED"
    if ship_gates == "CLEAR" and ai_risk["status"] == "BLOCKED" and not any("AI-risk" in item for item in must_fix):
        must_fix.append("AI-risk aggregate is BLOCKED")
    must_preserve = highlight_preserve_items(chapter)

    if ship_gates == "BLOCKED":
        status = "暂停"
        one_line = "事实门禁 BLOCKED；先补齐 provenance、hash/stale、ledger 或 P0/P1 continuity。"
    elif literary_failures:
        status = "重修"
        one_line = f"事实门禁 CLEAR；本章 {route_display(route)}，AI味 {ai_risk['status']}，文学路由仍有阻断项。"
    elif must_preserve:
        status = "可收"
        one_line = f"事实门禁 CLEAR；本章 {route_display(route)}，AI味 {ai_risk['status']}；修订时保留 {must_preserve[0]['highlight_id']}。"
    else:
        status = "可收"
        one_line = f"事实门禁 CLEAR；本章 {route_display(route)}，AI味 {ai_risk['status']}。"

    input_hashes = [file_ref(official_chapter_path(chapter))]
    route_path = review_route_path(chapter)
    if route_path.exists():
        input_hashes.append(file_ref(route_path))
    highlights_path = review_dir(chapter) / "highlights_review.json"
    if highlights_path.exists():
        input_hashes.append(file_ref(highlights_path))

    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "route": route_display(route),
        "ship_gates": ship_gates,
        "one_line_decision": one_line,
        "must_fix": must_fix[:20],
        "must_preserve": must_preserve[:10],
        "ai_risk": ai_risk,
        "input_hashes": input_hashes,
        "route_artifact": route_data if route_data else None,
    }


def render_markdown(report: dict[str, Any], *, verbose: bool = False) -> str:
    if not verbose:
        lines = [
            f"status: {report['status']}",
            f"route: {report['route']} / ship_gates: {report['ship_gates']}",
            f"one_line_decision: {report['one_line_decision']}",
        ]
        first_fix = (report.get("must_fix") or ["none"])[0]
        preserve = report.get("must_preserve") or []
        first_preserve = "none"
        if preserve:
            first_preserve = f"{preserve[0].get('highlight_id')}: {preserve[0].get('quote')}"
        lines.append(f"must_fix: {first_fix}")
        lines.append(f"must_preserve: {first_preserve}")
        return "\n".join(lines).rstrip() + "\n"
    lines = [
        f"# Review Summary: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"route: {report['route']}",
        f"ship_gates: {report['ship_gates']}",
        f"one_line_decision: {report['one_line_decision']}",
    ]
    lines.extend(["", "## Must Fix", ""])
    must_fix = report.get("must_fix") or []
    lines.extend(f"- {item}" for item in must_fix) if must_fix else lines.append("- none")
    lines.extend(["", "## Must Preserve", ""])
    preserve = report.get("must_preserve") or []
    if not preserve:
        lines.append("- none")
    for item in preserve:
        lines.append(f"- {item.get('highlight_id')}: {item.get('quote')} ({item.get('protection_level')})")
    ai_risk = report.get("ai_risk") or {}
    lines.extend(["", "## AI Risk", "", f"- status: {ai_risk.get('status', 'UNKNOWN')}"])
    for item in ai_risk.get("issues", []) if isinstance(ai_risk.get("issues"), list) else []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the five-line editor dashboard for one chapter.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--preview", "--preview-route", dest="preview_route", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter, preview_route=args.preview_route)
    if args.write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "review_summary.json", report)
        write_text(out_dir / "review_summary.md", render_markdown(report, verbose=args.verbose))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report, verbose=args.verbose), end="")
    return 1 if report["ship_gates"] == "BLOCKED" or report.get("must_fix") else 0


if __name__ == "__main__":
    raise SystemExit(main())
