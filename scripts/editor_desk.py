from __future__ import annotations

import argparse
import html
import json

from _common import ROOT, write_text
from product_kernel import personal_mode_is_noncommercial
from workflow_state import dashboard


def bullet_list(items: list[str], fallback: str = "none") -> None:
    if not items:
        print(f"- {fallback}")
        return
    for item in items:
        print(f"- {item}")


def dashboard_markdown(state: dict) -> str:
    risk = state.get("reader_risk", {})
    prose = state.get("prose_risk", {})
    health = state.get("long_health", {})
    lines = [
        "# 总编台 Dashboard",
        "",
        f"- phase: {state.get('phase_id')}",
        f"- blocker: {state.get('blocker')}",
        f"- next: {state.get('human_action')}",
        f"- risk_flags: {', '.join(state.get('risk_flags', [])) or 'none'}",
        f"- reader_risk: {risk.get('status', 'UNKNOWN')} through {risk.get('through', '')} blockers={risk.get('blocker_count', 0)}",
        f"- prose_risk: {prose.get('status', 'UNKNOWN')} through {prose.get('through', '')} blockers={prose.get('blocker_count', 0)}",
        f"- long_health: {health.get('status', 'UNKNOWN')} through {health.get('through', '')} blockers={health.get('rolling_blocker_count', 0)}",
        "",
        "## Gate Countdown",
        "",
    ]
    for gate, item in (state.get("gate_countdown") or {}).items():
        lines.append(f"- Gate {gate}: remaining={item.get('remaining')} decision={item.get('decision')}")
    lines.extend(["", "## Evidence Paths", ""])
    lines.extend(f"- {item}" for item in state.get("evidence_paths", []) or ["none"])
    return "\n".join(lines).rstrip() + "\n"


def dashboard_html(state: dict) -> str:
    risk = state.get("reader_risk", {})
    prose = state.get("prose_risk", {})
    health = state.get("long_health", {})
    flags = state.get("risk_flags", [])
    category_rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in (risk.get("category_statuses") or {}).items()
    ) or "<tr><td colspan='2'>none</td></tr>"
    prose_category_rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in (prose.get("category_statuses") or {}).items()
    ) or "<tr><td colspan='2'>none</td></tr>"
    gate_rows = "".join(
        "<tr><td>Gate {gate}</td><td>{remaining}</td><td>{decision}</td></tr>".format(
            gate=html.escape(str(gate)),
            remaining=html.escape(str(item.get("remaining", ""))),
            decision=html.escape(str(item.get("decision", ""))),
        )
        for gate, item in (state.get("gate_countdown") or {}).items()
    )
    evidence = "".join(f"<li>{html.escape(str(item))}</li>" for item in state.get("evidence_paths", []) or ["none"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>总编台 Dashboard</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #171717; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .panel {{ border: 1px solid #ddd; border-radius: 8px; padding: 14px; }}
    .status {{ font-size: 24px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>总编台 Dashboard</h1>
  <div class="grid">
    <section class="panel"><h2>当前卡点</h2><p class="status">{html.escape(str(state.get('phase_id')))}</p><p>{html.escape(str(state.get('blocker')))}</p></section>
    <section class="panel"><h2>Reader Risk</h2><p class="status">{html.escape(str(risk.get('status', 'UNKNOWN')))}</p><p>through {html.escape(str(risk.get('through', '')))}, blockers {html.escape(str(risk.get('blocker_count', 0)))}</p></section>
    <section class="panel"><h2>Prose Risk</h2><p class="status">{html.escape(str(prose.get('status', 'UNKNOWN')))}</p><p>through {html.escape(str(prose.get('through', '')))}, blockers {html.escape(str(prose.get('blocker_count', 0)))}</p></section>
    <section class="panel"><h2>Long Health</h2><p class="status">{html.escape(str(health.get('status', 'UNKNOWN')))}</p><p>through {html.escape(str(health.get('through', '')))}, blockers {html.escape(str(health.get('rolling_blocker_count', 0)))}</p></section>
    <section class="panel"><h2>风险标记</h2><p>{html.escape(', '.join(flags) or 'none')}</p></section>
  </div>
  <h2>Reader Risk Categories</h2>
  <table><tr><th>Category</th><th>Status</th></tr>{category_rows}</table>
  <h2>Prose Risk Categories</h2>
  <table><tr><th>Category</th><th>Status</th></tr>{prose_category_rows}</table>
  <h2>Gate Countdown</h2>
  <table><tr><th>Gate</th><th>Remaining</th><th>Decision</th></tr>{gate_rows}</table>
  <h2>Evidence Paths</h2>
  <ul>{evidence}</ul>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the editor dashboard with the current blocker and next command.")
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write state/audit/dashboard.md.")
    parser.add_argument("--html", action="store_true", help="Also write state/audit/dashboard.html when used with --write-report.")
    parser.add_argument("--verbose", action="store_true", help="Show the legacy detailed dashboard.")
    args = parser.parse_args()

    state = dashboard(args.chapter)
    if args.write_report:
        md_path = ROOT / "state" / "audit" / "dashboard.md"
        write_text(md_path, dashboard_markdown(state))
        print(f"wrote_report: {md_path.relative_to(ROOT).as_posix()}")
        if args.html:
            html_path = ROOT / "state" / "audit" / "dashboard.html"
            write_text(html_path, dashboard_html(state))
            print(f"wrote_report: {html_path.relative_to(ROOT).as_posix()}")
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if not args.verbose:
        print(f"status: {state.get('phase_id')}")
        print(f"blocker: {state.get('blocker')}")
        print(f"next: {state.get('human_action')}")
        print(f"risk_flags: {', '.join(state.get('risk_flags', [])) or 'none'}")
        print(f"evidence: {', '.join(state.get('evidence_paths', [])[:3]) or 'none'}")
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
    if not personal_mode_is_noncommercial():
        print(f"- 商业定位: {advisory.get('commercial_positioning', 'unknown')}")
        print(f"- 赛道扫描: {advisory.get('market_scan', 'unknown')}")
    print(f"- 章节结构: {advisory.get('chapter_structure', 'unknown')}")
    print(f"- 章末状态变化: {advisory.get('end_state_change', 'unknown')}")
    print(f"- 润色状态: {advisory.get('polish', 'unknown')}")
    print()
    print("## Reader Risk / Prose Risk / Long Health")
    risk = state.get("reader_risk", {})
    prose = state.get("prose_risk", {})
    health = state.get("long_health", {})
    print(f"- reader risk: {risk.get('status', 'UNKNOWN')} through {risk.get('through', '')} blockers={risk.get('blocker_count', 0)}")
    print(f"- prose risk: {prose.get('status', 'UNKNOWN')} through {prose.get('through', '')} blockers={prose.get('blocker_count', 0)}")
    print(f"- long health: {health.get('status', 'UNKNOWN')} through {health.get('through', '')} blockers={health.get('rolling_blocker_count', 0)}")
    categories = risk.get("category_statuses") or {}
    if categories:
        print("- reader risk categories: " + ", ".join(f"{key}={value}" for key, value in categories.items()))
    prose_categories = prose.get("category_statuses") or {}
    if prose_categories:
        print("- prose risk categories: " + ", ".join(f"{key}={value}" for key, value in prose_categories.items()))
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
