from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from style_contract import metrics_for_text


STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"
ADVISORY_START = 4
HARD_START = 6
RECENT_WINDOW = 3

CORE_METRICS = {
    "average_paragraph_chars",
    "paragraph_chars_stddev",
    "average_sentence_chars",
    "sentence_chars_stddev",
    "dialogue_line_ratio",
    "interiority_marker_density",
    "exposition_marker_density",
    "scene_motion_marker_density",
    "short_paragraph_ratio",
    "dialogue_start_ratio",
}

BLOCKER_MARKERS = {
    "[series-drift:person]": "series style declares narration person drift",
    "[series_drift:person]": "series style declares narration person drift",
    "[series-drift:distance]": "series style declares narration distance drift",
    "[series_drift:distance]": "series style declares narration distance drift",
    "[series-drift:voice]": "series style declares protagonist voice drift",
    "[series_drift:voice]": "series style declares protagonist voice drift",
}

WARNING_MARKERS = {
    "[series-drift:dialogue]": "series style declares dialogue drift",
    "[series_drift:dialogue]": "series style declares dialogue drift",
    "[series-drift:exposition]": "series style declares exposition drift",
    "[series_drift:exposition]": "series style declares exposition drift",
    "[series-drift:rhythm]": "series style declares rhythm drift",
    "[series_drift:rhythm]": "series style declares rhythm drift",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def style_metrics_path(chapter: str) -> Path:
    return ROOT / "reviews" / chapter / "style_metrics.json"


def series_style_path(chapter: str) -> Path:
    return ROOT / "reviews" / chapter / "series_style.json"


def deepseek_style_path(chapter: str) -> Path:
    return ROOT / "reviews" / chapter / "deepseek_style_review.json"


def gate_mode(chapter: str) -> str:
    number = chapter_number(chapter)
    if number < ADVISORY_START:
        return "WARMUP"
    if number < HARD_START:
        return "ADVISORY"
    return "HARD"


def safe_read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def input_ref(path: Path, *, status: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists():
        ref["sha256"] = sha256(path)
    else:
        ref["sha256"] = ""
    if status is not None:
        ref["status"] = status
    return ref


def previous_chapters(chapter: str, limit: int = RECENT_WINDOW) -> list[str]:
    current = chapter_number(chapter)
    chapters: list[str] = []
    for path in sorted((ROOT / "reviews").glob("v??_c???/style_metrics.json")):
        candidate = path.parent.name
        try:
            number = chapter_number(candidate)
        except ValueError:
            continue
        if number < current:
            chapters.append(candidate)
    return chapters[-limit:]


def recent_metric_refs(chapter: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for previous in previous_chapters(chapter):
        path = style_metrics_path(previous)
        data = safe_read_json(path, {})
        status = data.get("status") if isinstance(data, dict) else "INVALID"
        ref = input_ref(path, status=str(status or "MISSING"))
        ref["chapter"] = previous
        refs.append(ref)
    return refs


def metric_outliers(current: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    ranges = profile.get("allowed_ranges", {})
    if not isinstance(ranges, dict):
        ranges = {}
    outliers: list[dict[str, Any]] = []
    for key in sorted(CORE_METRICS):
        value = current.get(key)
        allowed = ranges.get(key)
        if not isinstance(value, (int, float)) or not isinstance(allowed, dict):
            continue
        minimum = allowed.get("min")
        maximum = allowed.get("max")
        if not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)):
            continue
        if value < minimum or value > maximum:
            outliers.append(
                {
                    "metric": key,
                    "value": round(float(value), 3),
                    "expected_min": round(float(minimum), 3),
                    "expected_max": round(float(maximum), 3),
                    "direction": "low" if value < minimum else "high",
                }
            )
    return outliers


def marker_findings(text: str) -> tuple[list[str], list[str]]:
    blockers = [message for marker, message in BLOCKER_MARKERS.items() if marker in text]
    warnings = [message for marker, message in WARNING_MARKERS.items() if marker in text]
    return blockers, warnings


def deepseek_findings(chapter: str, official_hash: str, *, require_deepseek: bool) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    path = deepseek_style_path(chapter)
    warnings: list[str] = []
    blockers: list[str] = []
    if not path.exists():
        if require_deepseek:
            blockers.append(f"missing DeepSeek style review: {rel(path)}")
        return None, warnings, blockers

    data = safe_read_json(path, {})
    if not isinstance(data, dict):
        blockers.append(f"invalid DeepSeek style review JSON: {rel(path)}")
        return input_ref(path), warnings, blockers

    ref = input_ref(path, status=str(data.get("status", "UNKNOWN")))
    ref["chapter"] = chapter
    official = data.get("official_chapter", {})
    if not isinstance(official, dict) or official.get("sha256") != official_hash:
        blockers.append("DeepSeek style review is stale for the official chapter")

    status = str(data.get("status", "UNKNOWN"))
    if status in {"BLOCKED", "NOT_READY"}:
        blockers.append("DeepSeek style review reports blocking series-style drift")
    elif status not in {"CLEAR", "WARNING", "ACCEPTED_BY_HUMAN"}:
        warnings.append(f"DeepSeek style review status is {status}")
    elif status == "WARNING":
        warnings.append("DeepSeek style review reports advisory drift")
    return ref, warnings, blockers


def acceptance_blockers(infrastructure_blockers: list[str], reason: str) -> list[str]:
    blockers = list(infrastructure_blockers)
    if not reason.strip():
        blockers.append("human acceptance requires --reason")
    return blockers


def evaluate(chapter: str, *, accept: bool = False, reason: str = "", require_deepseek: bool = False) -> dict[str, Any]:
    mode = gate_mode(chapter)
    official_path = chapter_path(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    findings: list[dict[str, Any]] = []
    infrastructure_blockers: list[str] = []

    official_hash = ""
    text = ""
    if not official_path.exists() or not read_text(official_path).strip():
        infrastructure_blockers.append(f"missing official chapter text: {rel(official_path)}")
    else:
        official_hash = sha256(official_path)
        text = read_text(official_path)

    metrics_path = style_metrics_path(chapter)
    metrics_report = safe_read_json(metrics_path, {})
    metrics_ref = input_ref(metrics_path, status=str(metrics_report.get("status", "MISSING")) if isinstance(metrics_report, dict) else "INVALID")
    current_metrics: dict[str, Any] = {}
    if not isinstance(metrics_report, dict) or not metrics_path.exists():
        infrastructure_blockers.append(f"missing style metrics: {rel(metrics_path)}")
        current_metrics = metrics_for_text(text) if text else {}
    else:
        official = metrics_report.get("official_chapter", {})
        if metrics_report.get("chapter") != chapter:
            infrastructure_blockers.append("style metrics chapter mismatch")
        if metrics_report.get("status") != "READY":
            infrastructure_blockers.append(f"style metrics status is {metrics_report.get('status', 'MISSING')}")
        if not isinstance(official, dict) or official.get("sha256") != official_hash:
            infrastructure_blockers.append("style metrics are stale for the official chapter")
        raw_metrics = metrics_report.get("metrics", {})
        current_metrics = raw_metrics if isinstance(raw_metrics, dict) else {}

    profile = safe_read_json(STYLE_PROFILE, {})
    profile_status = profile.get("status", "MISSING") if isinstance(profile, dict) else "INVALID"
    profile_ref = input_ref(STYLE_PROFILE, status=str(profile_status))
    if mode != "WARMUP":
        if not STYLE_PROFILE.exists() or not isinstance(profile, dict):
            infrastructure_blockers.append(f"missing style profile: {rel(STYLE_PROFILE)}")
        elif profile.get("status") != "READY":
            infrastructure_blockers.append(f"style profile status is {profile.get('status', 'MISSING')}")

    marker_blockers, marker_warnings = marker_findings(text)
    warnings.extend(marker_warnings)
    outliers = metric_outliers(current_metrics, profile if isinstance(profile, dict) else {})

    for item in outliers:
        findings.append({"kind": "metric_outlier", **item})

    if outliers:
        warnings.append(f"{len(outliers)} style metric(s) outside the derived profile range")
    if marker_blockers:
        findings.extend({"kind": "marker_blocker", "message": item} for item in marker_blockers)
    if marker_warnings:
        findings.extend({"kind": "marker_warning", "message": item} for item in marker_warnings)

    deepseek_ref, deepseek_warnings, deepseek_blockers = deepseek_findings(chapter, official_hash, require_deepseek=require_deepseek)
    warnings.extend(deepseek_warnings)

    style_blockers: list[str] = []
    if mode == "HARD":
        style_blockers.extend(marker_blockers)
        if len(outliers) >= 2:
            style_blockers.append("hard gate: two or more core style metrics are outside the derived profile range")
        style_blockers.extend(deepseek_blockers)
    elif mode == "ADVISORY":
        warnings.extend(marker_blockers)
        warnings.extend(deepseek_blockers)
    else:
        warnings.extend(marker_blockers)
        warnings.extend(deepseek_blockers)

    blockers.extend(infrastructure_blockers)
    blockers.extend(style_blockers)

    status = "READY"
    human_acceptance: dict[str, Any] | None = None
    if blockers:
        status = "NOT_READY"
    elif warnings and mode != "HARD":
        status = "WARNING"

    if accept:
        acceptance_errors = acceptance_blockers(infrastructure_blockers, reason)
        if acceptance_errors:
            blockers = acceptance_errors + style_blockers
            status = "NOT_READY"
        else:
            status = "ACCEPTED_BY_HUMAN"
            human_acceptance = {
                "accepted_at": now_iso(),
                "reason": reason.strip(),
                "official_chapter_sha256": official_hash,
            }

    inputs: dict[str, Any] = {
        "style_profile": profile_ref,
        "style_metrics": metrics_ref,
        "recent_style_metrics": recent_metric_refs(chapter),
    }
    if deepseek_ref is not None:
        inputs["deepseek_style_review"] = deepseek_ref

    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "gate_mode": mode,
        "official_chapter": {"path": rel(official_path), "sha256": official_hash},
        "inputs": inputs,
        "window": {
            "baseline_chapters": profile.get("generated_from_chapters", []) if isinstance(profile, dict) else [],
            "recent_chapters": previous_chapters(chapter),
        },
        "current_metrics": current_metrics,
        "signals": {
            "metric_outlier_count": len(outliers),
            "marker_blocker_count": len(marker_blockers),
            "marker_warning_count": len(marker_warnings),
            "deepseek_style_review": "present" if deepseek_ref is not None else "missing",
        },
        "findings": findings,
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": human_acceptance,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Series Style Check: {report.get('chapter')}",
        "",
        f"status: {report.get('status')}",
        f"gate_mode: {report.get('gate_mode')}",
        "",
        "## Signals",
        "",
        json.dumps(report.get("signals", {}), ensure_ascii=False, indent=2),
        "",
    ]
    if report.get("findings"):
        lines.extend(["## Findings", ""])
        for item in report["findings"]:
            lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
        lines.append("")
    if report.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in report["blockers"])
        lines.append("")
    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in report["warnings"])
        lines.append("")
    if report.get("human_acceptance"):
        lines.extend(["## Human Acceptance", ""])
        lines.append(json.dumps(report["human_acceptance"], ensure_ascii=False, indent=2))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command_check(args: argparse.Namespace) -> int:
    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = evaluate(args.chapter, accept=args.accept, reason=args.reason or "", require_deepseek=args.require_deepseek)
    out_json = series_style_path(args.chapter)
    out_md = ROOT / "reviews" / args.chapter / "series_style.md"
    write_json(out_json, report)
    write_text(out_md, render_markdown(report))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Series Style Check: {args.chapter}")
        print()
        print(f"status: {report['status']}")
        print(f"gate_mode: {report['gate_mode']}")
        print(f"path: {rel(out_json)}")
        for item in report.get("blockers", []):
            print(f"- {item}")
        if report.get("status") in {"WARNING", "ACCEPTED_BY_HUMAN"}:
            for item in report.get("warnings", []):
                print(f"- {item}")

    return 0 if report["status"] in {"READY", "WARNING", "ACCEPTED_BY_HUMAN"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Check cross-chapter style consistency and series feel.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--accept", action="store_true", help="Record a human acceptance for non-infrastructure style drift.")
    parser.add_argument("--reason", default="", help="Required with --accept.")
    parser.add_argument("--require-deepseek", action="store_true", help="Require reviews/{chapter}/deepseek_style_review.json as an input.")
    args = parser.parse_args()
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
