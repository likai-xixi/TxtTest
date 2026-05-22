from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, now_iso, read_json, write_json, write_text


QUESTIONS = {
    "stuck_point": "Where did the reader hesitate or stop?",
    "continue_reason": "Why would the reader continue?",
    "promise_gap": "Where did the chapter drift from the reader promise?",
    "favorite_moment": "What moment stayed in memory?",
    "skip_moment": "What felt skippable?",
    "next_click_intent": "Would the reader click the next chapter, and why?",
    "protagonist_charm": "Did the protagonist feel appealing or active in this chapter?",
    "author_explanation_feel": "Did any part feel like author explanation instead of drama?",
    "suspense_feel": "Did the suspense feel like expectation or fatigue?",
}
PLACEHOLDERS = {"", "TODO", "TBD", "placeholder", "unknown", "待填", "待定"}


def response_dir(chapter: str) -> Path:
    return ROOT / "reader_tests" / "chapter_feedback" / chapter


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def validate_answers(answers: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in QUESTIONS:
        value = str(answers.get(key, "")).strip()
        if value in PLACEHOLDERS:
            errors.append(f"missing answer: {key}")
    return errors


def command_add(args: argparse.Namespace) -> int:
    if args.answers:
        answers = read_json(Path(args.answers), {})
        if not isinstance(answers, dict):
            print("ERROR: --answers must point to a JSON object.", file=sys.stderr)
            return 1
    else:
        answers = {
            "stuck_point": args.stuck_point,
            "continue_reason": args.continue_reason,
            "promise_gap": args.promise_gap,
            "favorite_moment": args.favorite_moment,
            "skip_moment": args.skip_moment,
            "next_click_intent": args.next_click_intent,
            "protagonist_charm": args.protagonist_charm,
            "author_explanation_feel": args.author_explanation_feel,
            "suspense_feel": args.suspense_feel,
        }
    errors = validate_answers(answers)
    if args.target_reader.strip() in PLACEHOLDERS and not args.allow_unknown:
        errors.append("target reader must be identified; use --allow-unknown only for synthetic tests.")
    if errors and not args.allow_incomplete:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    record = {
        "schema_version": 1,
        "chapter": args.chapter,
        "reader_id": args.reader,
        "target_reader": args.target_reader,
        "recorded_at": now_iso(),
        "answers": answers,
        "status": "INCOMPLETE" if errors else "RECORDED",
    }
    out = response_dir(args.chapter) / f"{args.reader}.json"
    write_json(out, record)
    log = ROOT / "reader_tests" / "feedback_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"chapter": args.chapter, "reader_id": args.reader, "action": "add", "recorded_at": record["recorded_at"]}, ensure_ascii=False) + "\n")
    print(f"OK: wrote {rel(out)}")
    return 0


def response_items(chapter: str) -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(response_dir(chapter).glob("*.json")):
        data = read_json(path, {})
        if isinstance(data, dict):
            items.append((path, data))
    return items


def load_responses(chapter: str, *, include_incomplete: bool = False) -> list[dict[str, Any]]:
    responses = []
    for _path, data in response_items(chapter):
        if not include_incomplete and str(data.get("status", "")).upper() == "INCOMPLETE":
            continue
        responses.append(data)
    return responses


def response_refs(chapter: str, *, include_incomplete: bool = False) -> list[dict[str, Any]]:
    refs = []
    for path, data in response_items(chapter):
        if not include_incomplete and str(data.get("status", "")).upper() == "INCOMPLETE":
            continue
        refs.append(file_ref(path))
    return refs


def incomplete_response_refs(chapter: str) -> list[dict[str, Any]]:
    return [
        file_ref(path)
        for path, data in response_items(chapter)
        if str(data.get("status", "")).upper() == "INCOMPLETE"
    ]


def accepted_report_hash(report: dict[str, Any]) -> str:
    clean = dict(report)
    clean.pop("human_acceptance", None)
    clean.pop("status", None)
    body = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def risk_acceptance_items(report: dict[str, Any]) -> list[str]:
    items = []
    for key in ("risk", "recommendation"):
        value = str(report.get(key, "")).strip()
        if value:
            items.append(value)
    return items or ["Human editor accepts the retention risk of continuing without real reader responses."]


def summarize(chapter: str, risk: str, recommendation: str, acceptance_reason: str = "") -> dict[str, Any]:
    responses = load_responses(chapter)
    ignored_refs = incomplete_response_refs(chapter)
    stuck = []
    reasons = []
    gaps = []
    favorite = []
    skip = []
    next_click = []
    charm = []
    explanation = []
    suspense = []
    for response in responses:
        answers = response.get("answers", {}) if isinstance(response.get("answers"), dict) else {}
        if answers.get("stuck_point"):
            stuck.append(str(answers["stuck_point"]))
        if answers.get("continue_reason"):
            reasons.append(str(answers["continue_reason"]))
        if answers.get("promise_gap"):
            gaps.append(str(answers["promise_gap"]))
        if answers.get("favorite_moment"):
            favorite.append(str(answers["favorite_moment"]))
        if answers.get("skip_moment"):
            skip.append(str(answers["skip_moment"]))
        if answers.get("next_click_intent"):
            next_click.append(str(answers["next_click_intent"]))
        if answers.get("protagonist_charm"):
            charm.append(str(answers["protagonist_charm"]))
        if answers.get("author_explanation_feel"):
            explanation.append(str(answers["author_explanation_feel"]))
        if answers.get("suspense_feel"):
            suspense.append(str(answers["suspense_feel"]))
    status = "READY" if responses else "WARNING"
    report = {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "response_count": len(responses),
        "source_response_refs": response_refs(chapter),
        "ignored_response_count": len(ignored_refs),
        "ignored_response_refs": ignored_refs,
        "stuck_points": stuck,
        "continue_reasons": reasons,
        "reader_promise_gaps": gaps,
        "favorite_moments": favorite,
        "skip_moments": skip,
        "next_click_intents": next_click,
        "protagonist_charm_notes": charm,
        "author_explanation_flags": explanation,
        "suspense_fatigue_flags": suspense,
        "risk": risk.strip() or ("No real reader feedback yet; do not infer retention." if not responses else "Review reader friction before Gate decisions."),
        "recommendation": recommendation.strip() or "Use this as reader-experience evidence only; do not treat it as canon.",
        "human_acceptance": None,
    }
    if acceptance_reason.strip():
        report["human_acceptance"] = {
            "accepted_by": "human",
            "accepted_at": now_iso(),
            "reason": acceptance_reason.strip(),
            "response_refs": report["source_response_refs"],
            "report_sha256": accepted_report_hash(report),
            "risk_acceptance_items": risk_acceptance_items(report),
        }
        if not responses:
            report["status"] = "ACCEPTED_BY_HUMAN"
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Reader Feedback: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"generated_at: {report['generated_at']}",
        f"response_count: {report['response_count']}",
        f"ignored_response_count: {report.get('ignored_response_count', 0)}",
        "",
    ]
    for key, title in (
        ("stuck_points", "Stuck Points"),
        ("continue_reasons", "Continue Reasons"),
        ("reader_promise_gaps", "Reader Promise Gaps"),
        ("favorite_moments", "Favorite Moments"),
        ("skip_moments", "Skip Moments"),
        ("next_click_intents", "Next Click Intent"),
        ("protagonist_charm_notes", "Protagonist Charm"),
        ("author_explanation_flags", "Author Explanation Flags"),
        ("suspense_fatigue_flags", "Suspense Expectation Or Fatigue"),
    ):
        lines.extend([f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {item}" for item in values or ["none"])
        lines.append("")
    lines.extend(["## Risk", "", report.get("risk", ""), "", "## Recommendation", "", report.get("recommendation", "")])
    acceptance = report.get("human_acceptance")
    lines.extend(["", "## Human Acceptance", ""])
    if isinstance(acceptance, dict):
        for key in ("accepted_by", "accepted_at", "reason", "report_sha256"):
            lines.append(f"- {key}: {acceptance.get(key, '')}")
        lines.append("- risk_acceptance_items:")
        for item in acceptance.get("risk_acceptance_items") or []:
            lines.append(f"  - {item}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def update_derived(report: dict[str, Any]) -> None:
    path = ROOT / "state" / "derived" / "reader_feedback.json"
    current = read_json(path, {"schema_version": 1, "generated_at": "", "chapters": {}})
    if not isinstance(current, dict):
        current = {"schema_version": 1, "chapters": {}}
    chapters = current.setdefault("chapters", {})
    if isinstance(chapters, dict):
        chapters[report["chapter"]] = {
            "status": report["status"],
            "response_count": report["response_count"],
            "ignored_response_count": report.get("ignored_response_count", 0),
            "risk": report["risk"],
            "recommendation": report["recommendation"],
            "human_acceptance": report.get("human_acceptance"),
            "updated_at": now_iso(),
        }
    current["generated_at"] = now_iso()
    write_json(path, current)


def command_summarize(args: argparse.Namespace) -> int:
    report = summarize(args.chapter, args.risk, args.recommendation, args.human_acceptance_reason)
    if args.no_write:
        print(render_markdown(report), end="")
        return 0 if report["status"] in {"READY", "ACCEPTED_BY_HUMAN"} else 1
    out_dir = ROOT / "reviews" / args.chapter
    write_json(out_dir / "reader_feedback.json", report)
    write_text(out_dir / "reader_feedback.md", render_markdown(report))
    update_derived(report)
    print(f"OK: wrote {rel(out_dir / 'reader_feedback.json')}")
    return 0 if report["status"] in {"READY", "ACCEPTED_BY_HUMAN"} else 1


def command_resolve(args: argparse.Namespace) -> int:
    report_path = ROOT / "reviews" / args.chapter / "reader_feedback.json"
    report = read_json(report_path, {})
    if not isinstance(report, dict) or not report:
        print(f"ERROR: missing reader feedback summary: {rel(report_path)}", file=sys.stderr)
        return 1
    resolutions = report.setdefault("resolutions", [])
    if not isinstance(resolutions, list):
        resolutions = []
        report["resolutions"] = resolutions
    resolutions.append({"resolved_at": now_iso(), "reason": args.reason, "resolved_by": "human"})
    write_json(report_path, report)
    update_derived(report)
    print(f"OK: resolved reader feedback for {args.chapter}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and summarize per-chapter reader feedback.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("chapter")
    add.add_argument("--reader", required=True)
    add.add_argument("--target-reader", default="unknown")
    add.add_argument("--answers", default=None)
    add.add_argument("--stuck-point", default="")
    add.add_argument("--continue-reason", default="")
    add.add_argument("--promise-gap", default="")
    add.add_argument("--favorite-moment", default="")
    add.add_argument("--skip-moment", default="")
    add.add_argument("--next-click-intent", default="")
    add.add_argument("--protagonist-charm", default="")
    add.add_argument("--author-explanation-feel", default="")
    add.add_argument("--suspense-feel", default="")
    add.add_argument("--allow-incomplete", action="store_true")
    add.add_argument("--allow-unknown", action="store_true")
    add.set_defaults(func=command_add)

    summarize_cmd = sub.add_parser("summarize")
    summarize_cmd.add_argument("chapter")
    summarize_cmd.add_argument("--risk", default="")
    summarize_cmd.add_argument("--recommendation", default="")
    summarize_cmd.add_argument("--human-acceptance-reason", default="")
    summarize_cmd.add_argument("--no-write", action="store_true")
    summarize_cmd.set_defaults(func=command_summarize)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("chapter")
    resolve.add_argument("--reason", required=True)
    resolve.set_defaults(func=command_resolve)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
