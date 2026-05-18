from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from _common import ROOT, chapter_parts, read_text, write_blocked_by_locks, write_text
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from deepseek_response import DeepSeekResponseError, extract_message_content


API_URL = "https://api.deepseek.com/chat/completions"
REQUIRED_BRIEF_FIELDS = (
    "本章功能",
    "开篇吸引点",
    "主角目标",
    "主要阻力",
    "主角主动选择",
    "本章推进",
    "信息增量",
    "章末问题",
    "本章使用设定",
    "本章可用人物状态",
    "本章可用道具 / 装备",
    "本章可用道具 IDs",
    "本章可用技能 / 能力",
    "本章可用技能 IDs",
    "能力限制 / 代价",
    "未解决伏笔",
    "新增设定",
    "本章允许新增元素",
    "本章禁止临场解决",
    "伏笔：新开 / 推进 / 回收",
    "本章禁止新增",
    "本章禁止解决",
    "禁止新增 / 禁止解决 / 禁止模仿",
)


def output_contract(chapter: str) -> str:
    fields = "\n".join(f"{index}. {field}" for index, field in enumerate(REQUIRED_BRIEF_FIELDS, start=1))
    return f"""输出格式必须是可直接进入 `outline/chapter_briefs/{chapter}.md` 的 Markdown 候选：

# {chapter} Brief

然后按以下字段逐项输出，字段名必须逐字一致，不能删减、合并、改名或换成 JSON：

{fields}

字段填写规则：
- 每个字段写 1-3 句具体中文；不得写“待定”“待填”“TODO”“待人类确认”等占位符。
- `本章可用道具 IDs` 只能列 brief pack 中 `全局道具 ID 索引` 已存在且本章确实要用的 id；没有就写 `none`。
- `本章可用技能 IDs` 只能列 brief pack 中 `全局技能 ID 索引` 已存在且本章确实要用的 id；没有就写 `none`。
- `本章允许新增元素` 必须按 L0/L1/L2/L3/L4 写清：L0 场景细节、L1 一次性线索、L2 伏笔/提案、L3 长期机制、L4 核心设定；不允许的等级写 `无`。
- `本章禁止临场解决` 必须明确本章核心问题不能靠哪些未授权新道具、新技能、新规则解决。
- `新增设定` 只能写本章候选提议，不得宣称进入 canon；触及 L4 核心设定时必须写“需人类裁决”。
- `本章禁止新增` 和 `本章禁止解决` 必须继承核心冻结、Gate 目标和 brief pack 中的禁止项。
- 信息不足时仍保留字段，并写具体缺口，例如“缺口：缺少第二章正式事件账本”，不要自行补设定。"""


def build_prompts(chapter: str, pack: str) -> tuple[str, str]:
    system = (
        "你是外部 brief 候选生成模型。只输出章节 brief 候选，不写正文，"
        "不声称它是正式 brief，不修改 canon，不追加 event ledger。"
        "必须完整覆盖正式 brief 模板和防漂移字段。"
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


def call_deepseek(payload: dict, api_key: str) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for a candidate chapter brief.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
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
