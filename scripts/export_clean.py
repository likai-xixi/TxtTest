from __future__ import annotations

import argparse
import re
import sys

from _common import ROOT, read_text, write_text
from chapter_evidence import chapter_evidence_failures


VOLUME_RE = re.compile(r"^v\d{2}$")


def chapter_id(volume: str, stem: str) -> str:
    if not VOLUME_RE.match(volume) or not re.match(r"^c\d{3}$", stem):
        raise ValueError(f"Invalid chapter path component: {volume}/{stem}.md")
    return f"{volume}_{stem}"


def decision_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export clean chapter text into exports/clean.")
    parser.add_argument("--volume", default="v01")
    parser.add_argument("--include-unshipped", action="store_true", help="Export non-empty chapters without Ship evidence; for private diagnostics only.")
    args = parser.parse_args()

    chapter_dir = ROOT / "chapters" / args.volume
    files = sorted(chapter_dir.glob("c*.md"))
    lines = [f"# {args.volume}", ""]
    exported = 0
    for path in files:
        text = read_text(path).strip()
        if text:
            chapter = chapter_id(args.volume, path.stem)
            if not args.include_unshipped:
                failures: list[str] = []
                if decision_for(chapter) != "Ship":
                    failures.append(f"{chapter}: human decision is not Ship")
                failures.extend(chapter_evidence_failures(chapter))
                if failures:
                    print(f"ERROR: refusing to export unshipped chapter {chapter}", file=sys.stderr)
                    for failure in failures:
                        print(f"  - {failure}", file=sys.stderr)
                    return 1
            lines.extend([f"## {path.stem}", "", text, ""])
            exported += 1

    if exported == 0:
        print(f"ERROR: no non-empty chapters found in {chapter_dir.relative_to(ROOT)}", file=sys.stderr)
        return 1

    out = ROOT / "exports" / "clean" / f"{args.volume}.md"
    write_text(out, "\n".join(lines).strip() + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
