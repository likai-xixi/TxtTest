from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

from _common import ROOT


REQUIRED_ROLES = ["product_founder", "technical_lead", "qa_release"]
AGENT_READY_ENV = "CODEX_REQUIRED_AGENTS_READY"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "ready"}


def evaluate(live: bool, agents_ready: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    checks.append(
        {
            "id": "deepseek_api_key",
            "status": "READY" if api_key else "BLOCKED",
            "detail": "set" if api_key else "DEEPSEEK_API_KEY is missing",
        }
    )
    template = run([sys.executable, str(ROOT / "scripts" / "check_template.py")])
    checks.append(
        {
            "id": "template_check",
            "status": "READY" if template.returncode == 0 else "BLOCKED",
            "detail": (template.stdout + template.stderr).strip(),
        }
    )
    deepseek_args = ["deepseek-preflight"]
    if not live:
        deepseek_args.append("--no-live")
    deepseek = run([sys.executable, str(ROOT / "scripts" / "novel.py"), *deepseek_args])
    checks.append(
        {
            "id": "deepseek_preflight",
            "status": "READY" if deepseek.returncode == 0 else "BLOCKED",
            "detail": (deepseek.stdout + deepseek.stderr).strip(),
        }
    )
    agents_available = agents_ready or truthy(os.environ.get(AGENT_READY_ENV))
    checks.append(
        {
            "id": "codex_subagents",
            "status": "READY" if agents_available else "BLOCKED",
            "detail": (
                "product_founder, technical_lead, and qa_release are available for this run."
                if agents_available
                else "Opening experiment requires product_founder, technical_lead, and qa_release; rerun from Codex App after confirming them, or pass --agents-ready only when they are actually available."
            ),
        }
    )
    blockers = [item["detail"] for item in checks if item["status"] == "BLOCKED"]
    return {
        "schema_version": 1,
        "status": "BLOCKED" if blockers else "READY_FOR_IDEA",
        "live_request": live,
        "required_roles": REQUIRED_ROLES,
        "checks": checks,
        "blockers": blockers,
        "next_action": (
            "Say `想法：...` / run `python scripts/novel.py idea --text ...`, then run the three required agents."
            if not blockers
            else "Resolve blockers first; do not start the opening experiment until DeepSeek and the three required Codex agents are available."
        ),
    }


def print_text(data: dict[str, Any]) -> None:
    print("# Opening Preflight")
    print()
    print(f"status: {data['status']}")
    print(f"live_request: {str(data['live_request']).lower()}")
    print()
    print("## Checks")
    for item in data["checks"]:
        print(f"- {item['id']}: {item['status']}")
    print()
    print("## Required Agents")
    for role in data["required_roles"]:
        print(f"- {role}")
    print()
    print("## Next Action")
    print(data["next_action"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether the opening experiment can start.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--live", action="store_true", help="Make a live DeepSeek preflight request.")
    parser.add_argument(
        "--agents-ready",
        action="store_true",
        help="Assert that product_founder, technical_lead, and qa_release are available for this opening run.",
    )
    args = parser.parse_args()
    data = evaluate(args.live, args.agents_ready)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_text(data)
    return 0 if data["status"] == "READY_FOR_IDEA" else 1


if __name__ == "__main__":
    raise SystemExit(main())
