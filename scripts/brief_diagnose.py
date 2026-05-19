from __future__ import annotations

import argparse
import json
import sys

from _common import ROOT, chapter_parts
from brief_check import check_brief


CATEGORIES = {
    "missing_fields": ("missing required section", "empty required section", "missing field"),
    "placeholders": ("placeholder", "still contains placeholder"),
    "scene_continuity": ("章末锚点", "开场落点", "场景承接", "location changes", "原地承接"),
    "pacing_progress": ("主线牵引", "外部压力", "节奏", "低牵引", "进展契约", "推进对象", "结束状态变化", "最低落账事件", "进展重要度"),
    "cost_consequence": ("代价", "后果", "推进重量", "消化窗口", "冷却范围", "解决伏笔"),
    "element_authorization": ("object id", "ability id", "可用道具", "可用技能", "允许新增元素", "禁止临场解决"),
}

ADVICE = {
    "missing_fields": "补齐正式 brief 模板字段；字段名不要改写或合并。",
    "placeholders": "把待定/TODO 改成可执行的具体状态、动作、限制或缺口说明。",
    "scene_continuity": "写清上一章末与本章开场的时间、地点、人物、状态和转移动作。",
    "pacing_progress": "用 S0-S4/W0-W4 标出牵引与外压，并留下可核验的状态变化。",
    "cost_consequence": "为推进、兑现或解决伏笔写清代价、后果承接义务和消化窗口。",
    "element_authorization": "只使用已授权道具/技能 ID；新元素按 L0-L4 标明边界，不得临场破局。",
}


def categorize(failures: list[str]) -> dict[str, list[str]]:
    grouped = {key: [] for key in CATEGORIES}
    grouped["other"] = []
    for failure in failures:
        target = "other"
        for category, needles in CATEGORIES.items():
            if any(needle in failure for needle in needles):
                target = category
                break
        grouped[target].append(failure)
    return {key: value for key, value in grouped.items() if value}


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain brief-check failures in editor-friendly groups.")
    parser.add_argument("chapter")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    path = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    failures = check_brief(path)
    grouped = categorize(failures)
    report = {
        "chapter": args.chapter,
        "status": "READY" if not failures else "NOT_READY",
        "groups": grouped,
        "advice": {key: ADVICE.get(key, "人工检查该类问题。") for key in grouped},
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Brief Diagnose: {args.chapter}")
        print()
        print(f"status: {report['status']}")
        print()
        if not failures:
            print("No brief-check failures detected.")
        for group, items in grouped.items():
            print(f"## {group}")
            print()
            print(f"advice: {report['advice'][group]}")
            for item in items:
                print(f"- {item}")
            print()
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
