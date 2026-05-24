from __future__ import annotations

import argparse
import json
from typing import Any

from _common import ROOT, chapter_number, now_iso, read_json, read_text, write_json, write_text
from product_kernel import (
    ROUTE_VERSION,
    always_required_ship_gates,
    configured_additional_reviews,
    derived_ledger_source_failures,
    event_ledger_path,
    file_ref,
    gate_chapters,
    official_brief_path,
    official_chapter_path,
    read_event_ledger,
    rel,
    personal_mode_runtime_failures,
    review_dir,
    review_json_stale_failures,
    review_route_path,
    route_for_chapter_number,
    route_input_refs,
)


OPTIONAL_REVIEW_JSONS = (
    "human_flavor.json",
    "highlights_review.json",
    "ai_taste.json",
    "dialogue_function.json",
    "emotion_relationship_gate.json",
    "memorable_scene.json",
    "prose_risk.json",
    "reader_reward_gate.json",
    "reader_feedback.json",
    "chapter_shape.json",
    "series_style.json",
)
THREAD_DEBT_LEDGER = ROOT / "state" / "derived" / "thread_debt_ledger.json"
CHARACTER_ARC_LEDGER = ROOT / "state" / "derived" / "character_arc_ledger.json"
STYLE_VOICE_LEDGER = ROOT / "state" / "derived" / "style_voice_ledger.json"
SHADOW_ROUTE_SIGNAL_DIR = ROOT / "state" / "shadow" / "route_signals"
SHADOW_MANIFEST_DIR = ROOT / "state" / "shadow" / "manifests"
RELATIONSHIP_TERMS = ("关系变化", "relationship_change", "relationship shift", "relationship")
THREAD_TERMS = ("伏笔推进", "推进伏笔", "解决伏笔", "thread_advanced", "thread_paid_off", "payoff")
HEAVY_TERMS = ("P0", "P1", "L3", "L4", "核心机制", "core mechanism", "major protagonist")


def load_routing_config() -> tuple[dict[str, Any], list[str]]:
    from product_kernel import load_review_routing

    return load_review_routing()


def optional_review_data(chapter: str, name: str) -> tuple[dict[str, Any], list[str]]:
    path = review_dir(chapter) / name
    if not path.exists():
        return {}, []
    try:
        data = read_json(path, {})
    except Exception as exc:
        return {}, [f"{chapter}: {name} cannot be parsed: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{chapter}: {name} must be a JSON object"]
    return data, []


def click_reason_is_weak(brief_text: str) -> bool:
    labels = ("章末点击理由", "ending_click_reason", "Ending Click Reason")
    for raw in brief_text.splitlines():
        if any(label in raw for label in labels):
            value = raw.split(":", 1)[-1].split("：", 1)[-1].strip().lower()
            return value in {"", "todo", "tbd", "none", "无", "待定"} or len(value) < 6
    return True


def human_flavor_upgrade(chapter: str) -> tuple[bool, list[str]]:
    data, parse_errors = optional_review_data(chapter, "human_flavor.json")
    reasons: list[str] = []
    reasons.extend(parse_errors)
    if isinstance(data, dict) and data:
        signals = data.get("signals") if isinstance(data.get("signals"), dict) else {}
        window = data.get("window") if isinstance(data.get("window"), dict) else {}
        if int(window.get("last_3_missing_cost_or_misjudgment", 0) or 0) >= 3:
            reasons.append("human_flavor 3-chapter window missing cost/misjudgment")
        if int(window.get("last_5_human_flavor_warnings", 0) or 0) >= 5:
            reasons.append("human_flavor 5-chapter window has repeated warnings")
        if signals and data.get("status") == "WARNING" and not reasons:
            # Single-chapter human-flavor warnings are advisory only. The brief
            # gate owns hard enforcement of missing human-flavor contracts.
            return bool(parse_errors), parse_errors
    return bool(reasons), reasons


def ai_or_prose_high_risk(chapter: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for name in ("ai_taste.json", "prose_risk.json"):
        data, parse_errors = optional_review_data(chapter, name)
        reasons.extend(parse_errors)
        if not isinstance(data, dict) or not data:
            continue
        if data.get("status") == "BLOCKED":
            reasons.append(f"{name} is BLOCKED")
        categories = data.get("categories")
        if isinstance(categories, dict):
            for key, value in categories.items():
                if not isinstance(value, dict):
                    continue
                if value.get("status") == "BLOCKED" or value.get("severity") in {"P0", "P1"}:
                    reasons.append(f"{name} high risk category {key}")
                    break
    return bool(reasons), reasons


def chapter_events(chapter: str) -> list[dict[str, Any]]:
    return [event for event in read_event_ledger() if event.get("chapter") == chapter]


def event_route_reasons(chapter: str) -> tuple[str, list[str]]:
    route = "fast"
    reasons: list[str] = []
    for event in chapter_events(chapter):
        event_type = str(event.get("type", ""))
        importance = str(event.get("importance", ""))
        text = " ".join(str(event.get(key, "")) for key in ("fact", "consequence", "thread_id"))
        tags = " ".join(str(tag) for tag in event.get("tags", []) if str(tag).strip())
        combined = f"{event_type} {importance} {text} {tags}"
        if event_type in {"character_state_change", "rule_reveal"} and (
            importance in {"P0", "P1"} or any(term in combined for term in HEAVY_TERMS)
        ):
            route = "heavy"
            reasons.append(f"heavy event {event_type} {importance}".strip())
        elif event_type in {"relationship_change", "thread_advanced", "thread_paid_off"}:
            if route != "heavy":
                route = "normal"
            reasons.append(f"normal event {event_type}")
    return route, reasons


def thread_debt_route_reasons(chapter: str) -> tuple[str, list[str]]:
    if not THREAD_DEBT_LEDGER.exists():
        return "fast", []
    source_failures = derived_ledger_source_failures(file_ref(THREAD_DEBT_LEDGER), f"{chapter}: thread_debt_ledger")
    if source_failures:
        return "heavy", source_failures
    try:
        data = read_json(THREAD_DEBT_LEDGER, {})
    except Exception as exc:
        return "heavy", [f"thread_debt_ledger cannot be parsed: {exc}"]
    if not isinstance(data, dict):
        return "heavy", ["thread_debt_ledger must be a JSON object"]
    route = "fast"
    reasons: list[str] = []
    for item in data.get("threads", []):
        if not isinstance(item, dict):
            continue
        level = str(item.get("level", "P2"))
        due = bool(item.get("due") or item.get("advance_due") or item.get("payoff_due"))
        if not due:
            continue
        thread_id = str(item.get("thread_id", "thread"))
        if level in {"P0", "P1"}:
            route = "heavy"
            reasons.append(f"{level} thread debt due: {thread_id}")
        elif route != "heavy":
            route = "normal"
            reasons.append(f"{level} thread debt due: {thread_id}")
    return route, reasons


def derived_ledger_route_reasons(chapter: str) -> tuple[str, list[str]]:
    route = "fast"
    reasons: list[str] = []
    for label, path in (
        ("character_arc_ledger", CHARACTER_ARC_LEDGER),
        ("style_voice_ledger", STYLE_VOICE_LEDGER),
    ):
        if not path.exists():
            continue
        source_failures = derived_ledger_source_failures(file_ref(path), f"{chapter}: {label}")
        if source_failures:
            route = "heavy"
            reasons.extend(source_failures)
            continue
        try:
            data = read_json(path, {})
        except Exception as exc:
            route = "heavy"
            reasons.append(f"{label} cannot be parsed: {exc}")
            continue
        if not isinstance(data, dict):
            route = "heavy"
            reasons.append(f"{label} must be a JSON object")
            continue
        status = str(data.get("status", "READY"))
        if status == "BLOCKED":
            route = "heavy"
            reasons.append(f"{label} is BLOCKED")
        elif status == "WARNING" and route != "heavy":
            route = "normal"
            reasons.append(f"{label} is WARNING")
    return route, reasons


def text_route_reasons(brief_text: str, chapter_text: str) -> tuple[str, list[str]]:
    route = "fast"
    reasons: list[str] = []
    combined = f"{brief_text}\n{chapter_text}"
    if any(term in combined for term in HEAVY_TERMS):
        route = "heavy"
        reasons.append("brief/chapter mentions P0/P1, L3/L4, or core mechanism change")
    elif any(term in combined for term in RELATIONSHIP_TERMS + THREAD_TERMS):
        route = "normal"
        reasons.append("brief/chapter mentions relationship or thread movement")
    if click_reason_is_weak(brief_text):
        if route != "heavy":
            route = "normal"
        reasons.append("ending click reason is missing or weak")
    return route, reasons


def shadow_route_reasons(chapter: str) -> tuple[str, list[str], list[str], bool]:
    path = SHADOW_ROUTE_SIGNAL_DIR / f"{chapter}.json"
    if not path.exists():
        return "fast", [], [], False
    try:
        data = read_json(path, {})
    except Exception as exc:
        return "heavy", [], [f"shadow route signals cannot be parsed: {exc}"], True
    if not isinstance(data, dict):
        return "heavy", [], ["shadow route signals must be a JSON object"], True
    route = str(data.get("route") or "fast").lower()
    if route not in {"fast", "normal", "heavy", "gate"}:
        route = "heavy"
    reasons = [f"shadow route signal: {item}" for item in data.get("reasons", []) if str(item).strip()]
    warnings = [f"shadow route warning: {item}" for item in data.get("warnings", []) if str(item).strip()]
    fail_closed = False
    if data.get("status") == "BLOCKED":
        warnings.extend(f"shadow route blocker: {item}" for item in data.get("blockers", []) if str(item).strip())
        fail_closed = True
        route = "heavy"
    if data.get("can_downgrade_route") is not False:
        warnings.append("shadow route signals must not downgrade route")
        fail_closed = True
        route = "heavy"
    if data.get("must_not_skip_ship_evidence") is not True:
        warnings.append("shadow route signals must assert Ship evidence remains mandatory")
        fail_closed = True
        route = "heavy"
    return route, reasons, warnings, fail_closed


def max_route(left: str, right: str) -> str:
    order = {"fast": 0, "normal": 1, "heavy": 2, "gate": 3}
    return left if order[left] >= order[right] else right


def should_fail_closed(reasons: list[str]) -> bool:
    markers = ("hash is stale", "cannot be parsed", "must be a JSON object", "invalid JSON")
    return any(any(marker in reason for marker in markers) for reason in reasons)


def evaluate(chapter: str) -> dict[str, Any]:
    config, config_errors = load_routing_config()
    route = route_for_chapter_number(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []
    fail_closed = False

    personal_errors = personal_mode_runtime_failures()
    if config_errors or personal_errors:
        route = "heavy"
        fail_closed = True
        warnings.extend(config_errors)
        warnings.extend(personal_errors)
    refs = route_input_refs(chapter)
    for key, item in refs.items():
        if not item.get("exists"):
            blockers.append(f"missing critical routing input: {item['path']}")
    if blockers:
        route = "heavy" if route != "gate" else "gate"
        fail_closed = True

    official = official_chapter_path(chapter)
    brief = official_brief_path(chapter)
    brief_text = read_text(brief)
    chapter_text = read_text(official)

    if chapter_number(chapter) in gate_chapters():
        route = "gate"
        reasons.append("gate recap chapter number")

    event_route, event_reasons = event_route_reasons(chapter)
    route = max_route(route, event_route)
    reasons.extend(event_reasons)

    debt_route, debt_reasons = thread_debt_route_reasons(chapter)
    route = max_route(route, debt_route)
    reasons.extend(debt_reasons)
    if should_fail_closed(debt_reasons):
        fail_closed = True
        warnings.extend(debt_reasons)

    ledger_route, ledger_reasons = derived_ledger_route_reasons(chapter)
    route = max_route(route, ledger_route)
    reasons.extend(ledger_reasons)
    if should_fail_closed(ledger_reasons):
        fail_closed = True
        warnings.extend(ledger_reasons)

    text_route, text_reasons = text_route_reasons(brief_text, chapter_text)
    route = max_route(route, text_route)
    reasons.extend(text_reasons)

    has_upgrade, flavor_reasons = human_flavor_upgrade(chapter)
    if has_upgrade:
        route = max_route(route, "normal")
        reasons.extend(flavor_reasons)

    has_high_risk, high_risk_reasons = ai_or_prose_high_risk(chapter)
    if has_high_risk:
        route = max_route(route, "normal")
        reasons.extend(high_risk_reasons)

    shadow_route, shadow_reasons, shadow_warnings, shadow_fail_closed = shadow_route_reasons(chapter)
    route = max_route(route, shadow_route)
    reasons.extend(shadow_reasons)
    if shadow_warnings:
        warnings.extend(shadow_warnings)
    if shadow_fail_closed:
        fail_closed = True

    routing_inputs = []
    for name in OPTIONAL_REVIEW_JSONS:
        path = review_dir(chapter) / name
        if path.exists():
            routing_inputs.append(file_ref(path))
            stale = review_json_stale_failures(chapter, name)
            if stale:
                route = max_route(route, "heavy")
                fail_closed = True
                warnings.extend(stale)
    for path in (THREAD_DEBT_LEDGER, CHARACTER_ARC_LEDGER, STYLE_VOICE_LEDGER):
        if path.exists():
            routing_inputs.append(file_ref(path))
    for path in (SHADOW_ROUTE_SIGNAL_DIR / f"{chapter}.json", SHADOW_MANIFEST_DIR / f"{chapter}.json"):
        if path.exists():
            routing_inputs.append(file_ref(path))
    status = "BLOCKED" if blockers or fail_closed else ("WARNING" if warnings else "READY")
    additional = configured_additional_reviews(route)
    if not additional and isinstance(config.get("routes"), dict):
        warnings.append(f"route {route} has no configured additional_literary_reviews")
        additional = []
    report = {
        "schema_version": 1,
        "chapter": chapter,
        "route": route,
        "route_version": ROUTE_VERSION,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": refs["official_chapter"],
        "official_brief": refs["official_brief"],
        "context_manifest": refs["context_manifest"],
        "source_event_ledger": refs["source_event_ledger"],
        "routing_inputs": routing_inputs,
        "fail_closed": fail_closed,
        "always_required_ship_gates": always_required_ship_gates(),
        "additional_literary_reviews": additional,
        "reasons": sorted(set(reasons)) or ["default FAST route"],
        "warnings": warnings,
        "blockers": blockers,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Review Route: {report['chapter']}",
        "",
        f"status: {report.get('status', 'UNKNOWN')}",
        f"route: {str(report.get('route', '')).upper()}",
        f"fail_closed: {str(report.get('fail_closed')).lower()}",
        f"generated_at: {report.get('generated_at')}",
        "",
        "## Reasons",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("reasons", [])) if report.get("reasons") else lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report.get("warnings", [])) if report.get("warnings") else lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in report.get("blockers", [])) if report.get("blockers") else lines.append("- none")
    lines.extend(["", "## Additional Literary Reviews", ""])
    lines.extend(f"- {item}" for item in report.get("additional_literary_reviews", [])) if report.get("additional_literary_reviews") else lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Route chapter literary reviews without skipping Ship gates.")
    parser.add_argument("chapter")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.chapter)
    if args.write and not args.preview:
        out = review_route_path(args.chapter)
        write_json(out, report)
        write_text(out.with_suffix(".md"), render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
        if args.preview:
            print("preview: true")
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
