from __future__ import annotations

import argparse
import re

from _common import ROOT, read_text, truncate, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight recent chapter summary snapshot.")
    parser.add_argument("--volume", default="v01")
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    chapter_dir = ROOT / "chapters" / args.volume
    files = sorted(chapter_dir.glob("c*.md"))[-args.count:]
    lines = [f"# Recent Chapters: {args.volume}", ""]
    if not files:
        lines.append("暂无已落盘正文。")
    for path in files:
        text = read_text(path)
        title = re.sub(r"\.md$", "", path.name)
        lines.extend([f"## {args.volume}_{title}", "", truncate(text, 500), ""])

    out = ROOT / "state" / "snapshots" / f"recent_{args.volume}.md"
    write_text(out, "\n".join(lines).strip() + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

