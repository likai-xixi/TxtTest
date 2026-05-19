from __future__ import annotations

import argparse
import json

from workflow_state import analyze_idea_lab


def print_text(report: dict) -> None:
    print(f"# Idea Status: {report.get('idea_id') or 'none'}")
    print()
    print(f"status: {report['status']}")
    print(f"can_select: {str(bool(report.get('can_select'))).lower()}")
    print()
    print("## Files")
    for name, item in report.get("files", {}).items():
        state = "ok" if item["exists"] and item["nonempty"] and not item["has_placeholders"] else "not_ready"
        print(f"- {name}: {state} ({item['path']})")
    print()
    print("## Blockers")
    if report.get("blockers"):
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    else:
        print("- none")
    if report.get("warnings"):
        print()
        print("## Warnings")
        for warning in report["warnings"]:
            print(f"- {warning}")
    print()
    print("## Next Action")
    print(report["next_action"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose idea-lab readiness before idea-select.")
    parser.add_argument("--id", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = analyze_idea_lab(args.id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report["status"] in {"READY_TO_SELECT", "LOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
