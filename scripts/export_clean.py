from __future__ import annotations

import argparse

from _common import ROOT, read_text, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Export clean chapter text into exports/clean.")
    parser.add_argument("--volume", default="v01")
    args = parser.parse_args()

    chapter_dir = ROOT / "chapters" / args.volume
    files = sorted(chapter_dir.glob("c*.md"))
    lines = [f"# {args.volume}", ""]
    for path in files:
        text = read_text(path).strip()
        if text:
            lines.extend([f"## {path.stem}", "", text, ""])

    out = ROOT / "exports" / "clean" / f"{args.volume}.md"
    write_text(out, "\n".join(lines).strip() + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

