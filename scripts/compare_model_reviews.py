from __future__ import annotations

import argparse
import re
import sys

from _common import ROOT, now_iso, read_text, write_text


ISSUE_RE = re.compile(r"(P[0-3]|问题|风险|建议|Rewrite|Revise|Ship|Kill|Pause)", re.IGNORECASE)


def extract_signals(text: str) -> list[str]:
    signals: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and ISSUE_RE.search(stripped):
            signals.append(stripped)
    return signals[:30]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Codex and DeepSeek independent reviews.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    review_dir = ROOT / "reviews" / args.chapter
    codex_path = review_dir / "codex_integrated_review.md"
    deepseek_path = review_dir / "deepseek_integrated_review.md"

    missing = [path for path in (codex_path, deepseek_path) if not path.exists()]
    if missing and not args.allow_missing:
        for path in missing:
            print(f"ERROR: missing {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    codex = read_text(codex_path, "缺失。")
    deepseek = read_text(deepseek_path, "缺失。")
    codex_signals = extract_signals(codex)
    deepseek_signals = extract_signals(deepseek)

    lines = [
        f"# Model Disagreement: {args.chapter}",
        "",
        f"generated_at: {now_iso()}",
        "",
        "## 双方一致的问题",
        "",
        "需人工根据两份报告确认；自动比较只提取信号，不替代裁决。",
        "",
        "## Codex 独有问题",
        "",
    ]
    lines.extend(f"- {item}" for item in codex_signals) if codex_signals else lines.append("无自动提取信号。")
    lines.extend(["", "## DeepSeek 独有问题", ""])
    lines.extend(f"- {item}" for item in deepseek_signals) if deepseek_signals else lines.append("无自动提取信号。")
    lines.extend(
        [
            "",
            "## 冲突判断",
            "",
            "待人类结合两份报告裁决。若双方在核心问题上冲突，按 stop rules 暂停。",
            "",
            "## 需要人类裁决事项",
            "",
            "- 是否采纳 Codex 指出的风险。",
            "- 是否采纳 DeepSeek 指出的风险。",
            "- 本章判定：Ship / Revise once / Rewrite brief / Kill chapter / Pause project。",
            "",
            "## 建议动作",
            "",
            "未自动决定。",
        ]
    )

    out = review_dir / "model_disagreement.md"
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

