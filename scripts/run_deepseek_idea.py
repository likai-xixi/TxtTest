from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from _common import ROOT, now_iso, write_blocked_by_locks, write_text


API_URL = "https://api.deepseek.com/chat/completions"
IDEA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


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


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def build_payload(args: argparse.Namespace) -> dict:
    system = (
        "你是外部开书发散模型。你只提供试点方向建议，不写 canon，不写正式正文，"
        "不决定人物命运，不承诺 300 万字。输出必须围绕前三章验证。"
    )
    user = f"""请基于下面的原始想法，提出 3 个互相区分明显的开书方向。

固定输出结构：

## Direction A：最强商业钩子
- 一句话卖点
- 主角欲望
- 核心冲突
- 世界最大异常
- 前三章验证点
- 最大风险
- 适合继续的信号
- 不适合继续的信号

## Direction B：最强人物驱动
同样字段。

## Direction C：最大差异化/反套路
同样字段。

## 总体提醒
- 不要直接进入 canon。
- 不要写正式正文。
- 指出最需要人类总编裁决的问题。

# 原始想法

{args.text}
"""
    return {
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for zero-to-pilot novel directions.")
    parser.add_argument("--idea-id", required=True, type=validate_idea_id)
    parser.add_argument("--text", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=5000)
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek idea lab"):
        return 1
    if not args.text.strip():
        print("ERROR: idea text must not be empty.", file=sys.stderr)
        return 1

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is required for idea lab; dry-run is not allowed.", file=sys.stderr)
        return 2

    payload = build_payload(args)
    try:
        response = call_deepseek(payload, api_key)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: DeepSeek request failed: {exc}", file=sys.stderr)
        return 1

    raw_path = ROOT / "external_runs" / "deepseek" / args.idea_id / "idea.raw.json"
    write_text(raw_path, json.dumps(response, ensure_ascii=False, indent=2))
    content = response["choices"][0]["message"].get("content") or ""
    out = ROOT / "state" / "idea_lab" / args.idea_id / "deepseek_idea.md"
    write_text(
        out,
        "\n".join(
            [
                f"# DeepSeek Idea Directions: {args.idea_id}",
                "",
                f"generated_at: {now_iso()}",
                "source: deepseek",
                "",
                content.strip(),
                "",
            ]
        ),
    )
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
