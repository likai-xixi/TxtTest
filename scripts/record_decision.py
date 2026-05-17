from __future__ import annotations

import argparse
import sys

from _common import ROOT, chapter_parts, now_iso, write_text


ALLOWED = ["Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the human decision for a chapter.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--decision", required=True, choices=ALLOWED)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    chapter_parts(args.chapter)
    lines = [
        f"# Human Decision: {args.chapter}",
        "",
        f"decided_at: {now_iso()}",
        f"decision: {args.decision}",
        "",
        "## Notes",
        "",
        args.notes.strip() or "无。",
        "",
        "## Allowed Decisions",
        "",
    ]
    lines.extend(f"- {item}" for item in ALLOWED)
    out = ROOT / "reviews" / args.chapter / "decision.md"
    write_text(out, "\n".join(lines) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

