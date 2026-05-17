from __future__ import annotations

import argparse
import sys

from _common import ROOT, chapter_parts, now_iso, read_json, write_blocked_by_locks, write_json, write_text


ALLOWED = ["Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project"]
STRUCTURED_REQUIRED = {"Ship", "Revise once", "Rewrite brief"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the human decision for a chapter.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--decision", required=True, choices=ALLOWED)
    parser.add_argument("--keep", default="")
    parser.add_argument("--change", default="")
    parser.add_argument("--next-verify", default="")
    parser.add_argument("--setting-boundary", default="")
    parser.add_argument("--failure-condition", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("chapter decision recording"):
        return 1

    chapter_parts(args.chapter)
    existing = read_json(ROOT / "reviews" / args.chapter / "decision.json", {})
    if args.decision == "Revise once" and existing.get("decision") == "Revise once":
        print(
            "ERROR: this chapter already used Revise once; choose Rewrite brief or record an explicit human decision.",
            file=sys.stderr,
        )
        return 1
    if args.decision in STRUCTURED_REQUIRED:
        required = {
            "--keep": args.keep,
            "--change": args.change,
            "--next-verify": args.next_verify,
            "--setting-boundary": args.setting_boundary,
            "--failure-condition": args.failure_condition,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            print(
                "ERROR: structured decision fields are required for "
                f"{args.decision}: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1
    decided_at = now_iso()
    record = {
        "chapter": args.chapter,
        "decided_at": decided_at,
        "decision": args.decision,
        "keep": args.keep,
        "change": args.change,
        "next_verify": args.next_verify,
        "setting_boundary": args.setting_boundary,
        "failure_condition": args.failure_condition,
        "notes": args.notes,
        "verified_by": "human",
    }
    lines = [
        f"# Human Decision: {args.chapter}",
        "",
        f"decided_at: {decided_at}",
        f"decision: {args.decision}",
        "",
        "## Keep",
        "",
        args.keep.strip() or "无。",
        "",
        "## Change",
        "",
        args.change.strip() or "无。",
        "",
        "## Next Verify",
        "",
        args.next_verify.strip() or "无。",
        "",
        "## Setting Boundary",
        "",
        args.setting_boundary.strip() or "无。",
        "",
        "## Failure Condition",
        "",
        args.failure_condition.strip() or "无。",
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
    write_json(ROOT / "reviews" / args.chapter / "decision.json", record)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
