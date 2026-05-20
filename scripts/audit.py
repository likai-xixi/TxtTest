from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from _common import ROOT, write_text
from workflow_state import dashboard


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    status: str
    code: str
    output: str


def run_command(command: list[str], *, audit_depth: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["NOVEL_AUDIT_DEPTH"] = str(audit_depth + 1)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)


def has_explicit_error(output: str) -> bool:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("ERROR:") or stripped.startswith("SMOKE FAILED:"):
            return True
    return "Traceback (most recent call last)" in output


def classify(name: str, returncode: int, output: str, state: dict | None = None, *, mode: str = "project") -> str:
    if mode == "template":
        if returncode != 0 or has_explicit_error(output):
            return "ERROR"
        return "READY"
    if name == "status" and state is not None:
        return "NOT_READY" if state.get("blocker") else "READY"
    if "status: WARNING" in output:
        return "WARNING"
    if "status: INFO" in output:
        return "INFO"
    if "status: REHEARSAL_NOT_READY" in output or "status: NOT_READY" in output or "NOT_READY" in output:
        return "NOT_READY"
    if returncode == 0:
        return "READY"
    return "ERROR"


def step_summary(output: str, limit: int = 10) -> list[str]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[:limit] + [f"... ({len(lines) - limit} more lines)"]


def run_step(name: str, args: list[str], *, audit_depth: int, state: dict | None = None, mode: str = "project") -> StepResult:
    command = [sys.executable, str(ROOT / "scripts" / "novel.py"), *args]
    if name == "self-test" and audit_depth > 0:
        return StepResult(name, command, 0, "READY", "SELF_TEST_SKIPPED_NESTED", "skipped nested self-test to avoid audit recursion")
    result = run_command(command, audit_depth=audit_depth)
    output = (result.stdout or "") + (result.stderr or "")
    status = classify(name, result.returncode, output, state, mode=mode)
    code = f"{name.upper().replace('-', '_')}_{status}"
    return StepResult(name, command, result.returncode, status, code, output)


def step_defs_for(mode: str, chapter: str, gate: str) -> list[tuple[str, list[str]]]:
    project = [
        ("check", ["check"]),
        ("status", ["status", "--json"]),
        ("core-freeze-check", ["core-freeze-check"]),
        ("book-outline-check", ["book-outline-check"]),
        ("volume-outline-check", ["volume-outline-check", "--volume", "v01"]),
        ("style-contract-check", ["style-contract-check"]),
        ("style-profile-check", ["style-profile-check"]),
        ("reader-promise-check", ["reader-promise-check", "--require-ready"]),
        ("brief-check", ["brief-check", chapter]),
        ("reader-experience-check", ["reader-experience-check", chapter]),
        ("style-check", ["style-check", chapter]),
        ("series-style-check", ["series-style-check", chapter]),
        ("evidence", ["evidence", chapter]),
        ("market-scan-check", ["market-scan-check", "--id", "latest"]),
        ("commercial-idea-check", ["commercial-idea-check", "--id", "latest"]),
        ("table-check", ["table-check"]),
        ("similarity-risk-check", ["similarity-risk-check", chapter]),
        ("fact-card-check", ["fact-card-check", chapter]),
        ("polish-check", ["polish-check", chapter]),
        ("gate-rehearsal", ["gate-rehearsal", gate]),
        ("self-test", ["self-test"]),
        ("deepseek-preflight", ["deepseek-preflight", "--no-live"]),
    ]
    if mode == "template":
        return [
            ("check", ["check"]),
            ("reader-promise-check", ["reader-promise-check"]),
            ("self-test", ["self-test"]),
            ("workflow-smoke", ["workflow-smoke"]),
            ("deepseek-preflight", ["deepseek-preflight", "--no-live"]),
        ]
    if mode == "release":
        return project + [("workflow-smoke", ["workflow-smoke"]), ("longrun-smoke", ["longrun-smoke", "--chapters", "10"])]
    return project


def overall_status(steps: list[StepResult]) -> str:
    statuses = {step.status for step in steps}
    if "ERROR" in statuses:
        return "ERROR"
    if "NOT_READY" in statuses:
        return "NOT_READY"
    if "WARNING" in statuses:
        return "WARNING"
    if "INFO" in statuses:
        return "INFO"
    return "READY"


def render_human_report(state: dict, steps: list[StepResult], chapter: str, gate: str, mode: str) -> str:
    overall = overall_status(steps)
    lines = [
        "# Editor Audit Report",
        "",
        f"mode: {mode}",
        f"overall: {overall}",
        f"env: {state.get('env_status', 'ENV_UNKNOWN')}",
        f"template: {state.get('template_status', 'TEMPLATE_UNKNOWN')}",
        f"story: {state.get('story_status', 'STORY_UNKNOWN')}",
        f"chapter: {chapter}",
        f"gate: {gate}",
        f"current_blocker: {state.get('blocker') or 'none'}",
        f"next_prompt: {state.get('next_prompt') or state.get('recommended_command') or 'none'}",
        "",
        "## Editor Prompt",
        "",
        f"- phase: {state.get('phase_id') or 'unknown'}",
        f"- human_action: {state.get('human_action') or state.get('recommended_command') or 'none'}",
        f"- codex_action: {state.get('codex_action') or state.get('next_prompt') or 'none'}",
        f"- risk_flags: {', '.join(state.get('risk_flags', [])) or 'none'}",
        "",
        "## Advisory Signals",
        "",
        f"- commercial_positioning: {state.get('advisory', {}).get('commercial_positioning', 'unknown')}",
        f"- market_scan: {state.get('advisory', {}).get('market_scan', 'unknown')}",
        f"- chapter_structure: {state.get('advisory', {}).get('chapter_structure', 'unknown')}",
        f"- end_state_change: {state.get('advisory', {}).get('end_state_change', 'unknown')}",
        f"- polish: {state.get('advisory', {}).get('polish', 'unknown')}",
        f"- series_style: {state.get('advisory', {}).get('series_style', 'unknown')}",
        "",
        "## Contract Signals",
        "",
        f"- book_outline: {state.get('contracts', {}).get('book_outline', 'unknown')}",
        f"- volume_outline: {state.get('contracts', {}).get('volume_outline', 'unknown')}",
        f"- target_word_count: {state.get('contracts', {}).get('target_word_count', 'unknown')}",
        f"- genre_lane: {state.get('contracts', {}).get('genre_lane', 'unknown')}",
        f"- ending_direction: {state.get('contracts', {}).get('ending_direction', 'unknown')}",
        f"- style_contract: {state.get('contracts', {}).get('style_contract', 'unknown')}",
        f"- style_profile: {state.get('contracts', {}).get('style_profile', 'unknown')}",
        f"- reader_promise: {state.get('contracts', {}).get('reader_promise', 'unknown')}",
        "",
        "## Checks",
        "",
    ]
    for step in steps:
        lines.append(f"### {step.name}: {step.status}")
        lines.append(f"code: {step.code}")
        lines.append(f"returncode: {step.returncode}")
        for line in step_summary(step.output):
            lines.append(f"- {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def resolve_report_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def write_human_report(value: str, report: str) -> list[Path]:
    target = resolve_report_path(value)
    write_text(target, report)
    written = [target]
    default_path = ROOT / "state" / "audit" / "latest.md"
    if target.resolve() == default_path.resolve():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_path = ROOT / "state" / "audit" / f"audit_{timestamp}.md"
        write_text(timestamp_path, report)
        written.append(timestamp_path)
    return written


def json_report(state: dict, steps: list[StepResult], chapter: str, gate: str, mode: str) -> dict:
    return {
        "mode": mode,
        "overall": overall_status(steps),
        "env_status": state.get("env_status"),
        "template_status": state.get("template_status"),
        "story_status": state.get("story_status"),
        "readiness": state.get("readiness"),
        "chapter": chapter,
        "gate": gate,
        "current_blocker": state.get("blocker"),
        "next_prompt": state.get("next_prompt") or state.get("recommended_command"),
        "advisory": state.get("advisory", {}),
        "contracts": state.get("contracts", {}),
        "steps": [
            {
                "name": step.name,
                "status": step.status,
                "code": step.code,
                "returncode": step.returncode,
                "command": [str(item) for item in step.command],
                "output": step.output,
            }
            for step in steps
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an editor-readable project audit.")
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--gate", default="A")
    parser.add_argument("--mode", choices=["template", "project", "release"], default="project")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write-report",
        nargs="?",
        const="state/audit/latest.md",
        default=None,
        help="Write the human-readable Markdown report. Without a path, writes state/audit/latest.md and a timestamped copy.",
    )
    args = parser.parse_args()

    state = dashboard()
    chapter = args.chapter or state.get("chapter") or "v01_c001"
    gate = args.gate.upper()
    audit_depth = int(os.environ.get("NOVEL_AUDIT_DEPTH", "0") or "0")
    steps = [
        run_step(name, command_args, audit_depth=audit_depth, state=state if name == "status" else None, mode=args.mode)
        for name, command_args in step_defs_for(args.mode, chapter, gate)
    ]

    human_report = render_human_report(state, steps, chapter, gate, args.mode)
    if args.write_report:
        written = write_human_report(args.write_report, human_report)
        for path in written:
            print(f"wrote_report: {path.relative_to(ROOT).as_posix()}", file=sys.stderr)

    if args.json:
        print(json.dumps(json_report(state, steps, chapter, gate, args.mode), ensure_ascii=False, indent=2))
    else:
        print(human_report, end="")
    return 0 if overall_status(steps) in {"READY", "WARNING", "INFO"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
