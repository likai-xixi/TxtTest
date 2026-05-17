from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, write_blocked_by_locks, write_text


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def allowed_inputs(chapter: str, reviewer: str) -> set[Path]:
    volume, chapter_file = chapter_parts(chapter)
    base = {
        (ROOT / "state" / "context_pack" / f"{chapter}.md").absolute(),
        (ROOT / "chapters" / volume / chapter_file).absolute(),
        (ROOT / "drafts" / "codex" / f"{chapter}.md").absolute(),
        (ROOT / "drafts" / "deepseek" / f"{chapter}.md").absolute(),
    }
    if reviewer == "codex":
        # Codex review must not depend on DeepSeek review; candidate drafts are
        # allowed only as draft inputs, not as review reports.
        return base
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description="Record review input hashes to make independence auditable.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--reviewer", required=True, choices=["codex", "deepseek"])
    parser.add_argument("--input", action="append", required=True)
    args = parser.parse_args()

    if write_blocked_by_locks("review manifest recording"):
        return 1

    allowed = allowed_inputs(args.chapter, args.reviewer)
    inputs = []
    for item in args.input:
        path = Path(item)
        if not path.is_absolute():
            path = ROOT / path
        absolute = path.absolute()
        if absolute not in allowed:
            allowed_text = "\n".join(f"  - {relative(path)}" for path in sorted(allowed))
            print(f"ERROR: disallowed {args.reviewer} review input: {item}\nAllowed:\n{allowed_text}", file=sys.stderr)
            return 1
        if absolute.is_symlink():
            print(f"ERROR: review input must not be a symlink: {relative(absolute)}", file=sys.stderr)
            return 1
        resolved = absolute.resolve()
        if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
            print(f"ERROR: review input escapes project root: {relative(absolute)}", file=sys.stderr)
            return 1
        if not absolute.exists():
            print(f"ERROR: missing review input: {relative(absolute)}", file=sys.stderr)
            return 1
        inputs.append({"path": relative(absolute), "sha256": sha256(absolute)})

    out = ROOT / "reviews" / args.chapter / "review_manifest.json"
    current = {}
    if out.exists():
        current = json.loads(out.read_text(encoding="utf-8"))
    current[args.reviewer] = {
        "recorded_at": now_iso(),
        "inputs": inputs,
        "forbidden_inputs": [
            "reviews/{chapter}/codex_integrated_review.md for DeepSeek",
            "reviews/{chapter}/deepseek_integrated_review.md for Codex",
        ],
    }
    write_text(out, json.dumps(current, ensure_ascii=False, indent=2) + "\n")
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
