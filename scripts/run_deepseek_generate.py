from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from _common import ROOT, read_text, write_text


API_URL = "https://api.deepseek.com/chat/completions"


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
    parser = argparse.ArgumentParser(description="Ask DeepSeek for a candidate chapter draft.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    if not context_path.exists():
        print(f"ERROR: missing context pack: {context_path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    context = read_text(context_path)
    system = (
        "你是外部候选生成模型。只输出候选正文，不声明 canon，不改状态，"
        "不追加 event ledger，不自称最终稿。若 context_pack 信息不足，列出缺口并停止。"
    )
    user = (
        f"请依据以下 context_pack 为 {args.chapter} 生成候选稿。"
        "不要读取或引用任何未给出的仓库信息。\n\n"
        f"{context}"
    )
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
    write_text(run_dir / "generate.prompt.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    if args.dry_run:
        print(f"OK: dry run wrote {(run_dir / 'generate.prompt.md').relative_to(ROOT)}")
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

    write_text(run_dir / "generate.raw.json", json.dumps(response, ensure_ascii=False, indent=2))
    content = response["choices"][0]["message"].get("content") or ""
    out = ROOT / "drafts" / "deepseek" / f"{args.chapter}.md"
    write_text(out, content.strip() + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

