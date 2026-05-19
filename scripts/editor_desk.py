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
    print("## Project Status")
    print(f"- root: {state['root']}")
    print(f"- git: {state['git']}")
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
