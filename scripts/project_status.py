from __future__ import annotations

import argparse
import json

from product_kernel import personal_mode_is_noncommercial
from workflow_state import dashboard, labs_needing_agent_manifest, ready_idea_labs


def main() -> int:
    parser = argparse.ArgumentParser(description="Show project status and next likely action.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Show the legacy detailed status report.")
    args = parser.parse_args()

    state = dashboard()
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    if not args.verbose:
        risks = ", ".join(state.get("risk_flags", [])) or "none"
        print(
            f"status: {state.get('phase_id')}; "
            f"blocker: {state.get('blocker')}; "
            f"next: {state.get('human_action')}; "
            f"risks: {risks}"
        )
        return 0

    idea = state["idea"]
    labs = ready_idea_labs()
    manifest_labs = labs_needing_agent_manifest()
    unselected_labs = [lab for lab in labs if idea.get("idea_id") != lab or idea.get("selection_exists") is False]

    print("# Project Status")
    print()
    print(f"root: {state['root']}")
    print(f"git: {state['git']}")
    print(f"DEEPSEEK_API_KEY: {state['deepseek_api_key']}")
    print(f"ENV: {state.get('env_status', 'ENV_UNKNOWN')}")
    print(f"TEMPLATE: {state.get('template_status', 'TEMPLATE_UNKNOWN')}")
    print(f"STORY: {state.get('story_status', 'STORY_UNKNOWN')}")
    print()
    print("## Editor Hint")
    print(f"- phase: {state.get('phase_id')}")
    print(f"- current blocker: {state.get('blocker')}")
    print(f"- why: {state.get('why')}")
    print(f"- next command: {state.get('human_action')}")
    print(f"- risk flags: {', '.join(state.get('risk_flags', [])) or 'none'}")
    print()
    print("## Setup")
    print(f"- core setting freeze: {'ready' if state['freeze_ready'] else 'missing'}")
    print(f"- premise placeholders: {'yes' if state['premise_placeholders'] else 'no'}")
    print(f"- c001 brief placeholders: {'yes' if state['c001_brief_placeholders'] else 'no'}")
    print(f"- event ledger exists: {'yes' if state['event_ledger_exists'] else 'no'}")
    print()
    print("## Workflow Gates")
    print(f"- open stop locks: {len(state['locks'])}")
    print(f"- Gate A decision: {state['gates']['A']}")
    print(f"- Gate B decision: {state['gates']['B']}")
    print(f"- stale state: {state.get('stale', {}).get('status', 'UNKNOWN')}")
    print()
    print("## Advisory Signals")
    advisory = state.get("advisory", {})
    if not personal_mode_is_noncommercial():
        print(f"- 商业定位: {advisory.get('commercial_positioning', 'unknown')}")
        print(f"- 赛道扫描: {advisory.get('market_scan', 'unknown')}")
    print(f"- 章节结构: {advisory.get('chapter_structure', 'unknown')}")
    print(f"- 章末状态变化: {advisory.get('end_state_change', 'unknown')}")
    print(f"- 润色状态: {advisory.get('polish', 'unknown')}")
    risk = state.get("reader_risk", {})
    prose = state.get("prose_risk", {})
    health = state.get("long_health", {})
    print(f"- 读者风险: {risk.get('status', 'UNKNOWN')} through {risk.get('through', '')}")
    print(f"- 成稿七病: {prose.get('status', 'UNKNOWN')} through {prose.get('through', '')}")
    print(f"- 长篇健康: {health.get('status', 'UNKNOWN')} through {health.get('through', '')}")
    print()
    print("## Idea Lab")
    print(f"- latest idea: {idea.get('idea_id') or 'none'}")
    print(f"- status: {idea.get('status')}")
    if idea.get("blockers"):
        for blocker in idea["blockers"][:5]:
            print(f"- blocker: {blocker}")
    print()
    print("## Next likely action")
    if not state["freeze_ready"]:
        if manifest_labs:
            print(f"Run `python scripts/novel.py idea-agent-manifest --id {manifest_labs[0]}` to record multi-agent provenance.")
        elif unselected_labs:
            print(f"Run `python scripts/novel.py idea-select --id {unselected_labs[0]} --choice A` to lock core settings.")
        elif idea.get("can_select"):
            print(f"Run `python scripts/novel.py idea-select --id {idea['idea_id']} --choice A` to lock core settings.")
        else:
            print("Say `想法：...` / `开书实验`, or run `python scripts/novel.py idea --text \"...\"`; chapters cannot open until core settings are frozen.")
    else:
        print(state["recommended_command"])
    print()
    print("## Evidence paths")
    for path in state.get("evidence_paths", []):
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
