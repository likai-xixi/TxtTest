from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_text, write_blocked_by_locks, write_text
from deepseek_response import DeepSeekResponseError, extract_message_content


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


def default_chapter_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def allowed_review_inputs(chapter: str) -> set[Path]:
    volume, chapter_file = chapter_parts(chapter)
    return {
        (ROOT / "chapters" / volume / chapter_file).absolute(),
        (ROOT / "drafts" / "codex" / f"{chapter}.md").absolute(),
        (ROOT / "drafts" / "deepseek" / f"{chapter}.md").absolute(),
    }


def validate_input_path(path: Path, chapter: str) -> Path:
    absolute = path.absolute()
    if absolute not in allowed_review_inputs(chapter):
        allowed = "\n".join(f"  - {item.relative_to(ROOT)}" for item in sorted(allowed_review_inputs(chapter)))
        raise ValueError(
            "DeepSeek review input must be the official chapter or a candidate draft for this chapter.\n"
            f"Allowed inputs:\n{allowed}"
        )
    if absolute.is_symlink():
        raise ValueError(f"DeepSeek review input must not be a symlink: {absolute.relative_to(ROOT)}")
    resolved = absolute.resolve()
    if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
        raise ValueError(f"DeepSeek review input escapes the project root: {absolute.relative_to(ROOT)}")
    return absolute


def write_manifest(chapter: str, chapter_path: Path) -> None:
    context_path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    manifest_path = ROOT / "reviews" / chapter / "review_manifest.json"
    current = {}
    if manifest_path.exists():
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = []
    for path in (context_path.resolve(), chapter_path.resolve()):
        inputs.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    current["deepseek"] = {
        "recorded_at": now_iso(),
        "inputs": inputs,
        "forbidden_inputs": ["reviews/{chapter}/codex_integrated_review.md"],
    }
    write_text(manifest_path, json.dumps(current, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask DeepSeek for an independent chapter review.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--input", default=None, help="Optional draft/chapter file to review.")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--max-tokens", type=int, default=3500)
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt only; do not call the API.")
    args = parser.parse_args()

    if write_blocked_by_locks("DeepSeek review"):
        return 1

    try:
        chapter_parts(args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    chapter_path = Path(args.input) if args.input else default_chapter_path(args.chapter)
    if not chapter_path.is_absolute():
        chapter_path = ROOT / chapter_path
    try:
        chapter_path = validate_input_path(chapter_path, args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not context_path.exists():
        print(f"ERROR: missing context pack: {context_path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    if not chapter_path.exists():
        print(f"ERROR: missing review input: {chapter_path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    context = read_text(context_path)
    chapter_text = read_text(chapter_path)
    system = (
        "你是独立审查模型。你不能读取 Codex review，也不能修改仓库文件。"
        "只审查给定的 context_pack 与正文，输出结构化审查意见。"
    )
    user = f"""请审查 {args.chapter}，只看下面材料。
必须覆盖：
1. 是否读得下去
2. 主角是否主动
3. 本章是否推进
4. 是否有明显 AI 味
5. 是否有明显撞梗 / 换皮风险

输出：
- 关键结论
- P0/P1/P2/P3 问题
- 建议动作：Ship / Revise once / Rewrite brief / Kill chapter / Pause project

# Context Pack

{context}

# Chapter

{chapter_text}
"""
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "temperature": 0.2,
        "max_tokens": args.max_tokens,
        "stream": False,
    }

    run_dir = ROOT / "external_runs" / "deepseek" / args.chapter
    write_text(run_dir / "review.prompt.md", f"# System\n\n{system}\n\n# User\n\n{user}\n")
    if args.dry_run:
        print(f"OK: dry run wrote {(run_dir / 'review.prompt.md').relative_to(ROOT)}")
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

    write_manifest(args.chapter, chapter_path)
    write_text(run_dir / "review.raw.json", json.dumps(response, ensure_ascii=False, indent=2))
    out = ROOT / "reviews" / args.chapter / "deepseek_integrated_review.md"
    write_text(out, content + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
