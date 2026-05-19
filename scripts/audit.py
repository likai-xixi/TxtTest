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
    output: str


def run_command(command: list[str], *, audit_depth: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["NOVEL_AUDIT_DEPTH"] = str(audit_depth + 1)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)


def classify(name: str, returncode: int, output: str, state: dict | None = None) -> str:
    if name == "status" and state is not None:
        return "NOT_READY" if state.get("blocker") else "READY"
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


def run_step(name: str, args: list[str], *, audit_depth: int, state: dict | None = None) -> StepResult:
    command = [sys.executable, str(ROOT / "scripts" / "novel.py"), *args]
    if name == "self-test" and audit_depth > 0:
        return StepResult(name, command, 0, "READY", "skipped nested self-test to avoid audit recursion")
    result = run_command(command, audit_depth=audit_depth)
    output = (result.stdout or "") + (result.stderr or "")
    return StepResult(name, command, result.returncode, classify(name, result.returncode, output, state), output)


def overall_status(steps: list[StepResult]) -> str:
    statuses = {step.status for step in steps}
    if "ERROR" in statuses:
        return "ERROR"
    if "NOT_READY" in statuses:
        return "NOT_READY"
    return "READY"


def render_human_report(state: dict, steps: list[StepResult], chapter: str, gate: str) -> str:
    overall = overall_status(steps)
    lines = [
        "# 总编审查报告",
        "",
        f"overall: {overall}",
        f"chapter: {chapter}",
        f"gate: {gate}",
        f"current_blocker: {state.get('blocker') or 'none'}",
        f"next_prompt: {state.get('next_prompt') or state.get('recommended_command') or 'none'}",
        "",
        "## 总编提示",
        "",
        f"- 当前阶段: {state.get('phase_id') or 'unknown'}",
        f"- 下一条口令: {state.get('human_action') or state.get('recommended_command') or 'none'}",
        f"- 风险标记: {', '.join(state.get('risk_flags', [])) or 'none'}",
        "",
        "## 检查结果",
        "",
    ]
    for step in steps:
        lines.append(f"### {step.name}: {step.status}")
        lines.append(f"returncode: {step.returncode}")
        for line in step_summary(step.output):
            lines.append(f"- {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_human_report(state: dict, steps: list[StepResult], chapter: str, gate: str) -> None:
    print(render_human_report(state, steps, chapter, gate), end="")


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


def json_report(state: dict, steps: list[StepResult], chapter: str, gate: str) -> dict:
    return {
        "overall": overall_status(steps),
        "chapter": chapter,
        "gate": gate,
        "current_blocker": state.get("blocker"),
        "next_prompt": state.get("next_prompt") or state.get("recommended_command"),
        "steps": [
            {
                "name": step.name,
                "status": step.status,
                "returncode": step.returncode,
                "command": [str(item) for item in step.command],
                "output": step.output,
            }
            for step in steps
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a complete editor-readable project audit.")
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--gate", default="A")
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

    step_defs = [
        ("check", ["check"]),
        ("status", ["status", "--json"]),
        ("core-freeze-check", ["core-freeze-check"]),
        ("brief-check", ["brief-check", chapter]),
        ("evidence", ["evidence", chapter]),
        ("gate-rehearsal", ["gate-rehearsal", gate]),
        ("self-test", ["self-test"]),
        ("deepseek-preflight", ["deepseek-preflight", "--no-live"]),
    ]
    steps = [
        run_step(name, command_args, audit_depth=audit_depth, state=state if name == "status" else None)
        for name, command_args in step_defs
    ]

    human_report = render_human_report(state, steps, chapter, gate)
    if args.write_report:
        written = write_human_report(args.write_report, human_report)
        for path in written:
            print(f"wrote_report: {path.relative_to(ROOT).as_posix()}", file=sys.stderr)

    if args.json:
        print(json.dumps(json_report(state, steps, chapter, gate), ensure_ascii=False, indent=2))
    else:
        print(human_report, end="")
    return 0 if overall_status(steps) == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
