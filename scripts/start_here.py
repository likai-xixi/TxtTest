from __future__ import annotations

import argparse
import json
import os
from typing import Any

from _common import ROOT
from workflow_state import dashboard


def report() -> dict[str, Any]:
    state = dashboard()
    readiness = state.get("readiness", {})
    env_blockers = list(readiness.get("env_blockers", []))
    return {
        "schema_version": 1,
        "root": str(ROOT),
        "env_status": readiness.get("env_status", state.get("env_status", "ENV_NOT_READY")),
        "template_status": readiness.get("template_status", state.get("template_status", "TEMPLATE_NOT_READY")),
        "story_status": readiness.get("story_status", state.get("story_status", "STORY_NOT_READY")),
        "deepseek_api_key": "set" if os.environ.get("DEEPSEEK_API_KEY") else "missing",
        "requires_agents": ["product_founder", "technical_lead", "qa_release"],
        "agent_runtime_note": "Codex App must actually run the three subagents; Python verifies the recorded evidence.",
        "current_phase": state.get("phase_id"),
        "current_blocker": state.get("blocker"),
        "next_prompt": state.get("next_prompt") or state.get("human_action"),
        "template_check_detail": readiness.get("template_check_detail", ""),
        "env_blockers": env_blockers,
    }


def print_text(data: dict[str, Any]) -> None:
    print("# Start Here")
    print()
    print(f"ENV: {data['env_status']} (DeepSeek key: {data['deepseek_api_key']})")
    print(f"TEMPLATE: {data['template_status']}")
    print(f"STORY: {data['story_status']}")
    print()
    print("## Current Blocker")
    print(data.get("current_blocker") or "none")
    print()
    print("## Next Editor Prompt")
    print(data.get("next_prompt") or "none")
    print()
    print("## Agent Requirement")
    print("- product_founder")
    print("- technical_lead")
    print("- qa_release")
    print("Python validates agent run evidence; Codex App must run the agents.")


def main() -> int:
    parser = argparse.ArgumentParser(description="First-run guide for a copied novel template.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = report()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_text(data)
    return 0 if data["template_status"] == "TEMPLATE_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
