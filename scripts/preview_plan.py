from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_parts
from workflow_errors import issue


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _exists(path_text: str, *, required: bool = True, nonempty_required: bool = True) -> dict[str, Any]:
    path = ROOT / path_text
    return {
        "path": path_text,
        "required": required,
        "nonempty_required": nonempty_required,
        "exists": path.exists(),
        "nonempty": path.exists() and bool(path.read_text(encoding="utf-8", errors="replace").strip()) if path.is_file() else None,
    }


def _base(command: str, role_scope: str) -> dict[str, Any]:
    return {
        "mode": "preview",
        "command": command,
        "role_scope": role_scope,
        "mutates_files": False,
        "checks": [],
        "planned_writes": [],
        "guardrails": [
            "preview runs preflight-style checks only",
            "preview does not write official state, chapters, canon, event ledger, or reviews",
            "rerun without --preview after human confirmation",
        ],
        "issues": [],
    }


def idea_select_plan(args: Namespace) -> dict[str, Any]:
    idea_id = args.id
    plan = _base("idea-select", "idea")
    plan["checks"] = [
        _exists(f"state/idea_lab/{idea_id}/original_idea.md"),
        _exists(f"state/idea_lab/{idea_id}/deepseek_idea.md"),
        _exists(f"state/idea_lab/{idea_id}/product_founder_review.md"),
        _exists(f"state/idea_lab/{idea_id}/technical_lead_review.md"),
        _exists(f"state/idea_lab/{idea_id}/qa_release_review.md"),
        _exists(f"state/idea_lab/{idea_id}/agent_review_manifest.json"),
        _exists(f"state/idea_lab/{idea_id}/codex_synthesis.md"),
    ]
    plan["planned_writes"] = [
        {"path": f"state/idea_lab/{idea_id}/selection.json", "reason": "record human idea direction"},
        {"path": f"state/idea_lab/{idea_id}/selection.md", "reason": "human-readable selection record"},
        {"path": f"state/idea_lab/{idea_id}/core_setting_freeze.json", "reason": "hard gate evidence for opening prose"},
        {"path": f"state/idea_lab/{idea_id}/core_setting_freeze.md", "reason": "editor-readable core freeze"},
        {"path": "state/idea_lab/selected.json", "reason": "latest selected idea pointer"},
        {"path": "outline/premise.md", "reason": "pilot premise seeded from selected direction"},
        {"path": "bible/open_questions.md", "reason": "open questions parked outside canon"},
        {"path": "outline/gate_a_3_chapters.md", "reason": "pilot Gate A criteria"},
        {"path": "outline/chapter_briefs/v01_c001.md", "reason": "pilot first chapter brief seed"},
    ]
    return plan


def land_brief_plan(args: Namespace) -> dict[str, Any]:
    chapter = args.chapter
    plan = _base("land-brief", "brief")
    plan["checks"] = [
        _exists(f"outline/chapter_briefs/{chapter}.md"),
        _exists(f"state/selections/{chapter}_brief.json"),
    ]
    if getattr(args, "from_candidate", None):
        plan["checks"].append(_exists(f"drafts/{args.from_candidate.lower()}/{chapter}_brief.md"))
        plan["planned_writes"].append({"path": f"outline/chapter_briefs/{chapter}.md", "reason": "copy selected brief candidate into official brief"})
    plan["planned_writes"].extend(
        [
            {"path": f"reviews/{chapter}/brief_landing.json", "reason": "machine-readable brief provenance"},
            {"path": f"reviews/{chapter}/brief_landing.md", "reason": "editor-readable brief provenance"},
        ]
    )
    if not getattr(args, "attestation", "").strip():
        plan["issues"].append(issue("POLICY", "--attestation must not be empty"))
    return plan


def land_plan(args: Namespace) -> dict[str, Any]:
    chapter = args.chapter
    volume, chapter_file = chapter_parts(chapter)
    plan = _base("land", "chapter")
    plan["checks"] = [
        _exists(f"chapters/{volume}/{chapter_file}"),
        _exists(f"outline/chapter_briefs/{chapter}.md"),
        _exists(f"state/context_pack/{chapter}.md"),
        _exists(f"state/derived/context_quality/{chapter}.json"),
        _exists(f"state/selections/{chapter}.json", required=False),
    ]
    plan["planned_writes"] = [
        {"path": f"reviews/{chapter}/chapter_landing.json", "reason": "machine-readable chapter provenance"},
        {"path": f"reviews/{chapter}/chapter_landing.md", "reason": "editor-readable chapter provenance"},
    ]
    if not getattr(args, "attestation", "").strip():
        plan["issues"].append(issue("POLICY", "--attestation must not be empty"))
    return plan


def close_plan(args: Namespace) -> dict[str, Any]:
    chapter = args.chapter
    plan = _base("close", "chapter")
    checks = [_exists("state/event_ledger.jsonl", nonempty_required=False)]
    if args.decision == "Ship":
        volume, chapter_file = chapter_parts(chapter)
        checks.extend(
            [
                _exists(f"chapters/{volume}/{chapter_file}"),
                _exists(f"reviews/{chapter}/chapter_landing.json"),
                _exists(f"reviews/{chapter}/model_disagreement.md"),
                _exists(f"reviews/{chapter}/continuity.md"),
                _exists(f"reviews/{chapter}/codex_review_manifest.json"),
                _exists(f"reviews/{chapter}/deepseek_review.md"),
            ]
        )
    plan["checks"] = checks
    plan["planned_writes"] = [
        {"path": f"reviews/{chapter}/decision.md", "reason": "record human close decision"},
        {"path": "state/derived/", "reason": "rebuild derived state after close"},
    ]
    if getattr(args, "commit_message", None):
        plan["planned_writes"].append({"path": ".git", "reason": "optional role-scoped commit"})
    return plan


def event_plan(args: Namespace) -> dict[str, Any]:
    chapter = args.chapter
    plan = _base("event", "state")
    plan["checks"] = []
    plan["planned_writes"] = [{"path": "state/event_ledger.jsonl", "reason": "append one human-verified event"}]
    if getattr(args, "rebuild", True):
        plan["planned_writes"].append({"path": "state/derived/", "reason": "rebuild derived state after event append"})
    if args.type == "chapter_anchor":
        plan["guardrails"].append("chapter_anchor preview includes anchor fields; human must confirm exact continuity before execution")
        required = [
            "anchor_end_time",
            "anchor_end_location",
            "anchor_present_character",
            "anchor_protagonist_state",
            "anchor_carried_item",
            "anchor_unfinished_action",
            "anchor_next_required_continuity",
        ]
        missing = [name for name in required if not getattr(args, name, None)]
        if missing:
            plan["issues"].append(issue("MISSING", "chapter_anchor is missing anchor fields: " + ", ".join(missing)))
    return plan


PLANNERS = {
    "idea-select": idea_select_plan,
    "land-brief": land_brief_plan,
    "land": land_plan,
    "close": close_plan,
    "event": event_plan,
}


def build_plan(command: str, args: Namespace) -> dict[str, Any]:
    return PLANNERS[command](args)


def print_plan(command: str, args: Namespace) -> int:
    plan = build_plan(command, args)
    for item in plan.get("checks", []):
        if not item.get("required", True):
            continue
        if not item.get("exists"):
            plan["issues"].append(issue("MISSING", "required preview input is missing", item["path"]))
        elif item.get("nonempty_required", True) and item.get("nonempty") is False:
            plan["issues"].append(issue("MISSING", "required preview input is empty", item["path"]))
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 1 if plan.get("issues") else 0
