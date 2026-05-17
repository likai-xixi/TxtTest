from __future__ import annotations

import argparse
import re
import sys

from _common import ROOT, now_iso, read_text, write_text


ACTIONS = ["Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project"]
ACTION_RE = re.compile(r"(Ship|Revise once|Rewrite brief|Kill chapter|Pause project)", re.IGNORECASE)
ISSUE_RE = re.compile(
    r"(P[0-3]|问题|风险|建议|AI 味|撞梗|换皮|主角|推进|读得下去|Rewrite|Revise|Ship|Kill|Pause)",
    re.IGNORECASE,
)
BLOCKING_ACTIONS = {"Rewrite brief", "Kill chapter", "Pause project"}


def normalize_action(value: str) -> str:
    lowered = value.lower()
    for action in ACTIONS:
        if action.lower() == lowered:
            return action
    return value


def extract_action(text: str) -> str | None:
    for line in text.splitlines():
        if "建议动作" not in line and "action" not in line.lower():
            continue
        match = ACTION_RE.search(line)
        if match:
            return normalize_action(match.group(1))
    match = ACTION_RE.search(text)
    return normalize_action(match.group(1)) if match else None


def extract_signals(text: str) -> list[str]:
    signals: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or not ISSUE_RE.search(stripped):
            continue
        stripped = stripped.lstrip("-*0123456789.、 ")
        if stripped and stripped not in signals:
            signals.append(stripped)
    return signals[:40]


def signal_key(value: str) -> str:
    normalized = re.sub(r"\s+", "", value.lower())
    normalized = re.sub(r"[，。；：,!.?#*_~>\-]", "", normalized)
    return normalized[:80]


def split_signals(codex_signals: list[str], deepseek_signals: list[str]) -> tuple[list[str], list[str], list[str]]:
    deepseek_by_key = {signal_key(item): item for item in deepseek_signals}
    codex_by_key = {signal_key(item): item for item in codex_signals}
    common_keys = sorted(set(codex_by_key) & set(deepseek_by_key))
    common = [codex_by_key[key] for key in common_keys]
    codex_only = [item for item in codex_signals if signal_key(item) not in deepseek_by_key]
    deepseek_only = [item for item in deepseek_signals if signal_key(item) not in codex_by_key]
    return common, codex_only, deepseek_only


def conflict_status(codex_action: str | None, deepseek_action: str | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not codex_action or not deepseek_action:
        reasons.append("至少一份报告缺少可识别的建议动作。")
        return "NEEDS_HUMAN", reasons
    if codex_action != deepseek_action:
        reasons.append(f"建议动作不一致：Codex={codex_action}，DeepSeek={deepseek_action}。")
    if (codex_action == "Ship") != (deepseek_action == "Ship"):
        reasons.append("一方建议 Ship，另一方不建议 Ship。")
    if codex_action in BLOCKING_ACTIONS or deepseek_action in BLOCKING_ACTIONS:
        reasons.append("至少一方建议重写、杀章或暂停。")
    return ("CONFLICT" if reasons else "CLEAR"), reasons


def bullet_items(items: list[str], fallback: str) -> list[str]:
    return [f"- {item}" for item in items] if items else [f"- {fallback}"]


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
    codex_action = extract_action(codex)
    deepseek_action = extract_action(deepseek)
    common, codex_only, deepseek_only = split_signals(extract_signals(codex), extract_signals(deepseek))
    status, conflict_reasons = conflict_status(codex_action, deepseek_action)

    lines = [
        f"# Model Disagreement: {args.chapter}",
        "",
        f"generated_at: {now_iso()}",
        f"status: {status}",
        f"codex_action: {codex_action or 'UNKNOWN'}",
        f"deepseek_action: {deepseek_action or 'UNKNOWN'}",
        "",
        "## 双方一致的问题",
        "",
        *bullet_items(common, "未自动识别到完全一致的问题；仍需人类阅读两份报告确认。"),
        "",
        "## Codex 独有问题",
        "",
        *bullet_items(codex_only, "无自动识别信号。"),
        "",
        "## DeepSeek 独有问题",
        "",
        *bullet_items(deepseek_only, "无自动识别信号。"),
        "",
        "## 冲突判断",
        "",
        *bullet_items(conflict_reasons, "未识别到建议动作冲突。"),
        "",
        "## 需要人类裁决事项",
        "",
        "- 是否采纳 Codex 指出的风险。",
        "- 是否采纳 DeepSeek 指出的风险。",
        "- 本章判定：Ship / Revise once / Rewrite brief / Kill chapter / Pause project。",
        "",
        "## 建议动作",
        "",
    ]
    if status == "CLEAR" and codex_action == deepseek_action:
        lines.append(f"- 两份报告建议一致：{codex_action}。人类仍需最终裁决。")
    else:
        lines.append("- 暂停自动收章，等待人类裁决分歧。")

    out = review_dir / "model_disagreement.md"
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
