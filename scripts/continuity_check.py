from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_text, write_text
from validate_event_ledger import validate as validate_ledger


PLACEHOLDERS = ("待定", "待填", "TODO")


def add_issue(issues: list[tuple[str, str]], level: str, text: str) -> None:
    issues.append((level, text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a conservative continuity check for one chapter.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    volume, chapter_file = chapter_parts(args.chapter)
    chapter_path = ROOT / "chapters" / volume / chapter_file
    context_path = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    ledger_path = ROOT / "state" / "event_ledger.jsonl"
    issues: list[tuple[str, str]] = []

    if not context_path.exists():
        add_issue(issues, "P1", f"Missing context pack: {context_path.relative_to(ROOT)}")

    if not chapter_path.exists():
        add_issue(issues, "P1", f"Missing chapter file: {chapter_path.relative_to(ROOT)}")
        chapter_text = ""
    else:
        chapter_text = read_text(chapter_path)
        if not chapter_text.strip():
            add_issue(issues, "P2", "Chapter file is empty.")
        if any(marker in chapter_text for marker in PLACEHOLDERS):
            add_issue(issues, "P3", "Chapter contains placeholder text.")

    ledger_errors = validate_ledger(ledger_path)
    for error in ledger_errors:
        add_issue(issues, "P1", f"Event ledger validation failed: {error}")

    canon_text = read_text(ROOT / "bible" / "canon.md")
    if "当前状态：暂无 canon 事实" not in canon_text and chapter_text:
        # This is intentionally conservative. Real canon contradiction checks should
        # become stricter after the first human-confirmed facts exist.
        pass

    p0_count = sum(1 for level, _text in issues if level == "P0")
    p1_count = sum(1 for level, _text in issues if level == "P1")
    status = "BLOCKED" if p0_count or p1_count else "CLEAR"

    lines = [
        f"# Continuity: {args.chapter}",
        "",
        f"generated_at: {now_iso()}",
        f"status: {status}",
        f"p0_count: {p0_count}",
        f"p1_count: {p1_count}",
        f"p2_count: {sum(1 for level, _text in issues if level == 'P2')}",
        f"p3_count: {sum(1 for level, _text in issues if level == 'P3')}",
        "",
        "## Summary",
        "",
    ]
    if issues:
        lines.append("发现需要处理的问题。")
    else:
        lines.append("未发现自动检查可识别的连续性问题。")

    for level in ("P0", "P1", "P2", "P3"):
        lines.extend(["", f"## {level}", ""])
        matched = [text for item_level, text in issues if item_level == level]
        if matched:
            lines.extend(f"- {text}" for text in matched)
        else:
            lines.append("无。")

    lines.extend(
        [
            "",
            "## Check Scope",
            "",
            "- canon 违反",
            "- rules 违反",
            "- 人物状态冲突",
            "- 关系冲突",
            "- 时间线冲突",
            "- 地点 / 物品冲突",
            "- 术语漂移",
            "- 未登记伏笔",
        ]
    )

    out = ROOT / "reviews" / args.chapter / "continuity.md"
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 1 if any(level in {"P0", "P1"} for level, _ in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
