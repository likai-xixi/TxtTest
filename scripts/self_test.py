from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETED_WORKFLOW_TESTS = [
    "tests.test_governance_refactors.GovernanceRefactorTests.test_route_reviews_fail_closed_for_missing_parse_and_gate_inputs",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_route_artifact_stales_when_bound_inputs_change",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_route_artifact_stales_when_routing_input_changes",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_fast_route_cannot_bypass_always_required_ship_gates",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_highlights_are_imported_and_unreasoned_flattening_blocks",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_receive_preview_uses_route_aware_step_plan",
    "tests.test_governance_refactors.GovernanceRefactorTests.test_long_health_context_quality_ref_must_be_current",
    "tests.test_workflow_guards.WorkflowGuardTests.test_structured_anti_ai_reviews_go_stale_when_chapter_changes",
    "tests.test_workflow_guards.WorkflowGuardTests.test_chapter_evidence_rejects_stale_context_quality_hash",
    "tests.test_workflow_guards.WorkflowGuardTests.test_receive_chapter_preview_does_not_write_report",
]


@dataclass
class Step:
    name: str
    command: list[str]
    returncode: int


def run_step(name: str, command: list[str]) -> Step:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    print(f"# {name}")
    result = subprocess.run(command, cwd=ROOT, env=env)
    return Step(name, command, result.returncode)


def main() -> int:
    if os.environ.get("NOVEL_SELF_TEST_FULL") == "1":
        steps = [
            Step(
                "full-unittest",
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
                subprocess.run(
                    [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8:replace"},
                ).returncode,
            )
        ]
    else:
        steps = [
            run_step("check", [sys.executable, str(ROOT / "scripts" / "novel.py"), "check"]),
            run_step("stale-check-strict", [sys.executable, str(ROOT / "scripts" / "novel.py"), "stale-check", "--strict"]),
            run_step("governance-refactors", [sys.executable, "-B", "-m", "unittest", "-q", "tests.test_governance_refactors"]),
            run_step("workflow-v2-guards", [sys.executable, "-B", "-m", "unittest", "-q", *TARGETED_WORKFLOW_TESTS]),
        ]
    print()
    print("# Self Test Summary")
    for step in steps:
        status = "PASS" if step.returncode == 0 else "FAIL"
        print(f"- {step.name}: {status} ({step.returncode})")
    return 0 if all(step.returncode == 0 for step in steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
