from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error

from _common import ROOT, chapter_number, chapter_parts, read_json, read_text, write_blocked_by_locks, write_text
from context_governance import context_quality_path
from context_pack_quality import write_quality_report
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze
from deepseek_client import call_deepseek, model_for
from deepseek_response import DeepSeekResponseError, extract_message_content


STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"


def validate_style_profile(chapter: str) -> list[str]:
    if chapter_number(chapter) < 4:
        return []
    if not STYLE_PROFILE.exists():
        return [f"post-warmup chapter requires READY style profile: {STYLE_PROFILE.relative_to(ROOT)}; run style-profile-build"]
    data = read_json(STYLE_PROFILE, {})
    if data.get("status") != "READY":
        return [f"post-warmup chapter requires READY style profile, got {data.get('status', 'MISSING')}; run style-profile-build"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for a candidate chapter draft.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--model", default=model_for("deepseek_generate"))
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek candidate generation"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1
    profile_errors = validate_style_profile(args.chapter)
    if profile_errors:
        for error in profile_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    if not context_path.exists():
        print(f"ERROR: missing context pack: {context_path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    quality_path = context_quality_path(args.chapter)
    quality = write_quality_report(args.chapter)
    if quality.get("status") != "READY":
        print(
            f"ERROR: context pack quality is not READY: {quality_path.relative_to(ROOT)}. "
            "Run `python scripts/context_pack_quality.py --chapter ...` after rebuilding context.",
            file=sys.stderr,
        )
        return 1

    context = read_text(context_path)
    system = (
        "你是外部候选生成模型。只输出候选正文，不声称它是 canon，"
        "不修改状态，不追加 event ledger，不自称最终稿。"
        "如果 context_pack 信息不足，列出缺口并停止。"
        "必须遵守 context_pack 的 Style Instruction，包括 project style contract、style guide 和 derived style profile；"
        "如果文风输入缺失或互相矛盾，必须停止并列出缺口。"
        "可以创造 L0 场景细节和 L1 一次性线索；L2 新道具/异常/人物只能作为伏笔或提案，不能立刻解决本章核心问题；"
        "L3 长期机制和 L4 核心设定只能使用 context_pack/brief 明确授权的内容。"
        "不得用未授权的新道具、新能力或新规则作为本章破局钥匙。"
    )
    user = (
        f"请只依据下面的 context_pack 为 {args.chapter} 生成候选稿。"
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

    try:
        content = extract_message_content(response)
    except DeepSeekResponseError as exc:
        print(f"ERROR: invalid DeepSeek response: {exc}", file=sys.stderr)
        return 1

    write_text(run_dir / "generate.raw.json", json.dumps(response, ensure_ascii=False, indent=2))
    out = ROOT / "drafts" / "deepseek" / f"{args.chapter}.md"
    write_text(out, content + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
