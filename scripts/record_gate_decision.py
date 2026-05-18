from __future__ import annotations

import argparse
import subprocess
import sys

from _common import ROOT, now_iso, write_blocked_by_locks, write_json, write_text


DECISIONS = ["continue", "pause", "kill", "rework"]


def run_gate_check(gate: str) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gate_check.py"), "--gate", gate],
        cwd=ROOT,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a human gate decision after evidence is ready.")
    parser.add_argument("--gate", required=True, choices=["A", "B", "C", "E", "F", "G", "H"])
    parser.add_argument("--decision", required=True, choices=DECISIONS)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--next-limits", default="")
    parser.add_argument("--continue-to", default="")
    parser.add_argument("--budget", default="")
    parser.add_argument("--primary-model", default="")
    parser.add_argument("--must-fix", default="")
    parser.add_argument("--stop-trigger", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("gate decision recording"):
        return 1

    if args.decision == "continue":
        required = {
            "--next-limits": args.next_limits,
            "--continue-to": args.continue_to,
            "--budget": args.budget,
            "--primary-model": args.primary_model,
            "--must-fix": args.must_fix,
            "--stop-trigger": args.stop_trigger,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            print(
                "ERROR: structured gate continue fields are required: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            return 1
        code = run_gate_check(args.gate)
        if code != 0:
            print("ERROR: gate evidence is not ready; refusing to record continue.", file=sys.stderr)
            return code

    gate_id = f"gate_{args.gate.lower()}"
    decided_at = now_iso()
    record = {
        "gate": args.gate,
        "decided_at": decided_at,
        "decision": args.decision,
        "reason": args.reason,
        "next_limits": args.next_limits,
        "continue_to": args.continue_to,
        "budget": args.budget,
        "primary_model": args.primary_model,
        "must_fix": args.must_fix,
        "stop_trigger": args.stop_trigger,
        "verified_by": "human",
    }
    write_json(ROOT / "state" / "gates" / f"{gate_id}.json", record)

    lines = [
        f"# Gate {args.gate} Decision",
        "",
        f"decided_at: {decided_at}",
        f"decision: {args.decision}",
        "verified_by: human",
        "",
        "## Reason",
        "",
        args.reason,
        "",
        "## Next Stage Limits",
        "",
        args.next_limits.strip() or "无。",
        "",
        "## Continue To",
        "",
        args.continue_to.strip() or "无。",
        "",
        "## Budget",
        "",
        args.budget.strip() or "无。",
        "",
        "## Primary Model",
        "",
        args.primary_model.strip() or "无。",
        "",
        "## Must Fix",
        "",
        args.must_fix.strip() or "无。",
        "",
        "## Stop Trigger",
        "",
        args.stop_trigger.strip() or "无。",
        "",
        "## Boundary",
        "",
        "- This record captures the human decision.",
        "- No command automatically passes a gate.",
    ]
    write_text(ROOT / "state" / "gates" / f"{gate_id}.md", "\n".join(lines) + "\n")
    print(f"OK: recorded gate {args.gate} decision {args.decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
