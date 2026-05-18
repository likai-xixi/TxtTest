from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import ROOT, now_iso, read_text, write_text
from core_setting_freeze import sha256
from record_idea_selection import (
    AGENT_REVIEW_MANIFEST,
    AGENT_ROLES,
    IDEA_ID_RE,
    validate_agent_review_manifest,
)


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def input_item(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def valid_completed_at(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--completed-at must be ISO-8601") from exc
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Record idea-lab multi-agent review provenance.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--completed-at", default=None, type=valid_completed_at)
    args = parser.parse_args()

    lab = ROOT / "state" / "idea_lab" / args.id
    if not lab.exists():
        print(f"ERROR: missing idea lab: {lab.relative_to(ROOT)}", file=sys.stderr)
        return 1

    missing = [
        path.relative_to(ROOT).as_posix()
        for path in [lab / "original_idea.md", lab / "deepseek_idea.md", *(lab / name for name in AGENT_ROLES.values())]
        if not path.exists() or not read_text(path).strip()
    ]
    if missing:
        print(f"ERROR: missing idea-lab agent manifest inputs: {', '.join(missing)}", file=sys.stderr)
        return 1

    completed_at = args.completed_at or now_iso()
    manifest = {
        "schema_version": 1,
        "idea_id": args.id,
        "recorded_at": now_iso(),
        "inputs": [
            input_item(lab / "original_idea.md"),
            input_item(lab / "deepseek_idea.md"),
        ],
        "reviews": {
            role: {
                "role": role,
                "path": (lab / filename).relative_to(ROOT).as_posix(),
                "sha256": sha256(lab / filename),
                "completed_at": completed_at,
            }
            for role, filename in AGENT_ROLES.items()
        },
    }
    out = lab / AGENT_REVIEW_MANIFEST
    write_text(out, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    errors = validate_agent_review_manifest(args.id, lab)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
