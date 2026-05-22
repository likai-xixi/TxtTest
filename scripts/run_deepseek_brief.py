from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error

from _common import ROOT, chapter_parts, read_text, write_blocked_by_locks, write_text
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from deepseek_client import call_deepseek, model_for
from deepseek_response import DeepSeekResponseError, extract_message_content


def output_contract(chapter: str) -> str:
    return f"""输出格式必须是可直接进入 `outline/chapter_briefs/{chapter}.md` 的 Markdown 候选：

# {chapter} Brief

schema_version: 2

必须先输出 `## Story Card`，再输出 `## Machine Contract Appendix`。不要把审计语言、门禁语言或“合同”腔写进 Story Card。

`## Story Card` 必须逐项包含：
- 第一屏扰动
- 主角本章想要
- 主角主动动作
- 最大阻力
- 中段变化点
- 本章小兑现
- before -> after
- 章末点击理由
- 本章只讲懂的一条世界规则
- 禁止临场破局

`## Machine Contract Appendix` 必须逐项包含：
- 上章章末锚点
- 本章开场落点
- 场景承接说明
- 主线牵引档位
- 外部压力档位
- 本章继承变化
- 本章节奏用途
- 节奏说明
- 本章进展契约
- 本章代价与后果契约
- 本章解决边界
- reader_reward_intensity
- reader_reward_type
- reader_reward_delivery
- reader_reward_timing
- reward_evidence_requirement
- 低戏剧载体
- 低戏剧载体承载的推进类型
- 核心机制是否出现
- 若未出现，当前沉默计数
- 等待结尾债务
- 可用人物状态
- 可用道具 / 装备
- 可用道具 IDs
- 可用技能 / 能力
- 可用技能 IDs
- 能力限制 / 代价
- 未解决伏笔
- 新增设定
- 允许新增元素
- 最低落账事件
- 禁止新增
- 禁止解决
- 主角弱点 / 误判
- 普通人 / 外部视角对照
- 旧问题
- 悬念状态

填写规则：
- 所有字段必须具体，不得写“待定”“待填”“TODO”“待人类确认”等占位符。
- Story Card 只写创作卡：可见行动、压力、欲望、选择、兑现和翻页理由。
- Machine Contract Appendix 写机器治理字段，允许紧凑写成分号分隔的键值对。
- `before -> after` 必须出现箭头。
- `本章进展契约` 必须包含进展类型、有效推进类型、推进对象、起始状态依据、结束状态变化、进展重要度、低牵引功能。
- `本章代价与后果契约` 必须包含推进重量 C0-C4、后果等级、代价类型、已支付代价、延后代价、后果承接义务、消化窗口、冷却范围。
- `本章解决边界` 必须包含新开伏笔、推进伏笔、解决伏笔、禁止解决、解决是否需要代价。
- `最低落账事件` 必须使用现有 event ledger 类型。
- 可用道具/技能 IDs 只能列 brief pack 中已存在且本章确实要用的 id；没有就写 `none`。
- 信息不足时写具体缺口，但不能自行补 canon 或核心设定。"""


def build_prompts(chapter: str, pack: str) -> tuple[str, str]:
    system = (
        "你是外部 brief 候选生成模型。只输出章节 brief 候选，不写正文，"
        "不声称它是正式 brief，不修改 canon，不追加 event ledger。"
        "必须输出 v2 Story Card + Machine Contract Appendix。"
        "如果材料不足，列出具体缺口并停止自行补设定。"
    )
    user = (
        f"请只依据下面的 brief candidate pack 为 {chapter} 生成一个完整章节 brief 候选。"
        "输出必须可被人类选择、混合或修改后落成正式 brief。\n\n"
        f"{output_contract(chapter)}\n\n"
        "# Brief Candidate Pack\n\n"
        f"{pack}"
    )
    return system, user


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for a candidate chapter brief.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default=model_for("deepseek_brief"))
    parser.add_argument("--temperature", type=float, default=0.65)
    parser.add_argument("--max-tokens", type=int, default=3500)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek brief candidate generation"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1

    pack_path = ROOT / "state" / "context_pack" / f"{args.chapter}_brief.md"
    if not pack_path.exists():
        print(f"ERROR: missing brief candidate pack: {pack_path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    pack = read_text(pack_path)
    system, user = build_prompts(args.chapter, pack)
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": False,
    }

    run_dir = ROOT / "external_runs" / "deepseek" / args.chapter
    write_text(run_dir / "brief.prompt.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    if args.dry_run:
        print(f"OK: dry run wrote {(run_dir / 'brief.prompt.md').relative_to(ROOT)}")
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set.", file=sys.stderr)
        return 2

    try:
        response = call_deepseek(payload, api_key)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: DeepSeek request failed: {exc}", file=sys.stderr)
        return 1

    try:
        content = extract_message_content(response)
    except DeepSeekResponseError as exc:
        print(f"ERROR: invalid DeepSeek response: {exc}", file=sys.stderr)
        return 1

    write_text(run_dir / "brief.raw.json", json.dumps(response, ensure_ascii=False, indent=2))
    out = ROOT / "drafts" / "deepseek" / f"{args.chapter}_brief.md"
    write_text(out, content + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
