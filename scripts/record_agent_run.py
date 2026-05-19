from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import ROOT, now_iso, read_json, read_text, write_text
from core_setting_freeze import sha256
from record_idea_selection import AGENT_ROLES, IDEA_ID_RE


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def valid_completed_at(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--completed-at must be ISO-8601") from exc
    return value


def file_item(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def allowed_inputs_hash(items: list[dict[str, str]]) -> str:
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one idea-lab agent run before building the agent manifest.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--role", required=True, choices=sorted(AGENT_ROLES))
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runner-type", choices=["codex_subagent", "external_agent"], default="codex_subagent")
    parser.add_argument("--runner-id", required=True)
    parser.add_argument(
        "--transcript",
        required=True,
        help="Transcript or run log proving the isolated agent review execution.",
    )
    parser.add_argument(
        "--isolation-attestation",
        required=True,
        help="Short statement that the agent read only original_idea.md and deepseek_idea.md.",
    )
    parser.add_argument("--completed-at", default=None, type=valid_completed_at)
    args = parser.parse_args()

    if not args.agent_id.strip():
        print("ERROR: --agent-id must not be empty.", file=sys.stderr)
        return 1

    lab = ROOT / "state" / "idea_lab" / args.id
    if not lab.exists():
        print(f"ERROR: missing idea lab: {lab.relative_to(ROOT)}", file=sys.stderr)
        return 1

    expected_output = lab / AGENT_ROLES[args.role]
    output = resolve_repo_path(args.output)
    transcript = resolve_repo_path(args.transcript)
    if output.resolve() != expected_output.resolve():
        print(f"ERROR: --output for {args.role} must be {expected_output.relative_to(ROOT).as_posix()}", file=sys.stderr)
        return 1
    required = [lab / "original_idea.md", lab / "deepseek_idea.md", output, transcript]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.exists() or not read_text(path).strip()]
    if missing:
        print(f"ERROR: missing or empty agent run files: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not args.runner_id.strip():
        print("ERROR: --runner-id must not be empty.", file=sys.stderr)
        return 1
    if not args.isolation_attestation.strip():
        print("ERROR: --isolation-attestation must not be empty.", file=sys.stderr)
        return 1

    path = lab / "agent_runs.json"
    data = read_json(path, {"schema_version": 1, "idea_id": args.id, "runs": {}})
    runs = data.get("runs") if isinstance(data, dict) else {}
    if not isinstance(runs, dict):
        runs = {}
    input_files = [file_item(lab / "original_idea.md"), file_item(lab / "deepseek_idea.md")]
    runs[args.role] = {
        "role": args.role,
        "agent_id": args.agent_id.strip(),
        "runner_type": args.runner_type,
        "runner_id": args.runner_id.strip(),
        "input_files": input_files,
        "allowed_inputs": input_files,
        "allowed_inputs_sha256": allowed_inputs_hash(input_files),
        "output_file": file_item(output),
        "transcript_file": file_item(transcript),
        "transcript_sha256": sha256(transcript),
        "isolation_attestation": args.isolation_attestation.strip(),
        "completed_at": args.completed_at or now_iso(),
    }
    data = {
        "schema_version": 1,
        "idea_id": args.id,
        "updated_at": now_iso(),
        "runs": runs,
    }
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"OK: recorded {args.role} agent run in {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
