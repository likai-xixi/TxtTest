from __future__ import annotations

import argparse
import json

from workflow_state import dashboard


def bullet_list(items: list[str], fallback: str = "none") -> None:
    if not items:
        print(f"- {fallback}")
        return
    for item in items:
        print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the editor dashboard with the current blocker and next command.")
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    state = dashboard(args.chapter)
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    idea = state["idea"]

    print("# 总编台")
    print()
    print("## 总编提示")
    print(f"- 当前阶段: {state.get('phase_id')}")
    print(f"- 下一条口令: {state.get('human_action')}")
    print(f"- Codex 动作: {state.get('codex_action')}")
    if state.get("risk_flags"):
        print(f"- 风险标记: {', '.join(state['risk_flags'])}")
    else:
        print("- 风险标记: none")
    print()
    print("## Project Status")
    print(f"- root: {state['root']}")
    print(f"- git: {state['git']}")
    print(f"- env readiness: {state.get('env_status', 'ENV_UNKNOWN')}")
    print(f"- template readiness: {state.get('template_status', 'TEMPLATE_UNKNOWN')}")
    print(f"- story readiness: {state.get('story_status', 'STORY_UNKNOWN')}")
    print(f"- core setting freeze: {'ready' if state['freeze_ready'] else 'missing'}")
    print()
    print("## 当前卡点")
    print(f"- {state['blocker']}")
    print()
    print("## 为什么")
    print(f"- {state['why']}")
    print()
    print("## 推荐口令")
    print(f"- {state['recommended_command']}")
    print()
    print("## 下一步会读取")
    bullet_list(state["reads"])
    print()
    print("## 下一步可能写入")
    bullet_list(state["writes"])
    print()
    print("## 证据路径")
    bullet_list(state.get("evidence_paths", []))
    print()
    print("## DeepSeek")
    print(f"- DEEPSEEK_API_KEY: {state['deepseek_api_key']}")
    print("- preflight: `python scripts/novel.py deepseek-preflight`")
    print()
    print("## Idea Lab")
    print(f"- latest: {idea.get('idea_id') or 'none'}")
    print(f"- status: {idea.get('status')}")
    print(f"- can_select: {str(bool(idea.get('can_select'))).lower()}")
    print()
    print("## Brief / Chapter")
    print(f"- target chapter: {state['chapter']}")
    print(f"- c001 brief placeholders: {'yes' if state['c001_brief_placeholders'] else 'no'}")
    print(f"- stale state: {state.get('stale', {}).get('status', 'UNKNOWN')}")
    print()
    print("## Advisory Signals")
    advisory = state.get("advisory", {})
    print(f"- 商业定位: {advisory.get('commercial_positioning', 'unknown')}")
    print(f"- 赛道扫描: {advisory.get('market_scan', 'unknown')}")
    print(f"- 章节结构: {advisory.get('chapter_structure', 'unknown')}")
    print(f"- 章末状态变化: {advisory.get('end_state_change', 'unknown')}")
    print(f"- 润色状态: {advisory.get('polish', 'unknown')}")
    print()
    print("## Gates / Locks")
    print(f"- stop locks: {len(state['locks'])}")
    print(f"- Gate A: {state['gates']['A']}")
    print(f"- Gate B: {state['gates']['B']}")
    print(f"- Gate C: {state['gates']['C']}")
    print(f"- Gate E: {state['gates']['E']}")
    print(f"- Gate F: {state['gates']['F']}")
    print(f"- Gate G: {state['gates']['G']}")
    print(f"- Gate H: {state['gates']['H']}")
    print()
    print("## Stale State")
    stale = state.get("stale", {})
    print(f"- status: {stale.get('status', 'UNKNOWN')}")
    print(f"- checked chapters: {', '.join(stale.get('checked_chapters', [])) or 'none'}")
    print(f"- issue count: {stale.get('issue_count', 0)}")
    print()
    print("## Next Prompt")
    print()
    print("```text")
    print(state["next_prompt"])
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
