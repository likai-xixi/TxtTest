from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, gate_decision, read_text, unresolved_locks
from book_outline import BOOK_JSON, validate_contract as validate_book_outline_contract, volume_json_path, validate_volume
from core_setting_freeze import validate_freeze
from record_idea_selection import (
    AGENT_ROLES,
    REQUIRED_INPUTS,
    validate_agent_review_manifest,
    validate_codex_synthesis,
    validate_output_freshness,
)
from style_contract import CONTRACT_JSON, STYLE_PROFILE, validate_contract as validate_style_contract


PLACEHOLDERS = ("待定", "待填", "待评", "待生成", "待人类裁决", "寰呭畾", "寰呭～", "寰呰瘎", "TODO")
AGENT_REVIEW_FILES = tuple(AGENT_ROLES.values())
IDEA_READY_FILES = tuple(REQUIRED_INPUTS)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_status() -> str:
    result = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        return "not a git repository"
    return result.stdout.strip() or "clean"


def template_readiness() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_template.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    detail = ((result.stdout or "") + (result.stderr or "")).strip()
    return {
        "status": "TEMPLATE_READY" if result.returncode == 0 else "TEMPLATE_NOT_READY",
        "returncode": result.returncode,
        "detail": detail,
    }


def has_placeholders(path: Path | str) -> bool:
    path = ROOT / path if isinstance(path, str) else path
    return any(marker in read_text(path) for marker in PLACEHOLDERS)


def file_report(path: Path) -> dict[str, Any]:
    exists = path.exists()
    text = read_text(path) if exists and path.is_file() else ""
    return {
        "path": rel(path),
        "exists": exists,
        "nonempty": bool(text.strip()),
        "has_placeholders": any(marker in text for marker in PLACEHOLDERS),
        "sha256": sha256(path) if exists and path.is_file() else None,
    }


def idea_lab_root() -> Path:
    return ROOT / "state" / "idea_lab"


def idea_lab_ids() -> list[str]:
    root = idea_lab_root()
    if not root.exists():
        return []
    labs: list[tuple[float, str]] = []
    for lab in root.iterdir():
        if not lab.is_dir():
            continue
        files = [item for item in lab.iterdir() if item.is_file()]
        latest = max((item.stat().st_mtime for item in files), default=lab.stat().st_mtime)
        labs.append((latest, lab.name))
    return [name for _mtime, name in sorted(labs, reverse=True)]


def selected_idea_id() -> str | None:
    path = ROOT / "state" / "idea_lab" / "selected.json"
    if not path.exists():
        return None
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return None
    value = data.get("idea_id")
    return str(value) if value else None


def latest_idea_id() -> str | None:
    selected = selected_idea_id()
    if selected:
        return selected
    labs = idea_lab_ids()
    return labs[0] if labs else None


def ready_idea_labs() -> list[str]:
    ready: list[tuple[float, str]] = []
    for idea_id in idea_lab_ids():
        lab = idea_lab_root() / idea_id
        required = [lab / name for name in IDEA_READY_FILES]
        if all(path.exists() and read_text(path).strip() for path in required):
            ready.append((max(path.stat().st_mtime for path in required), idea_id))
    return [name for _mtime, name in sorted(ready, reverse=True)]


def labs_needing_agent_manifest() -> list[str]:
    labs: list[tuple[float, str]] = []
    for idea_id in idea_lab_ids():
        lab = idea_lab_root() / idea_id
        if (lab / "agent_review_manifest.json").exists():
            continue
        required = [lab / "original_idea.md", lab / "deepseek_idea.md", *[lab / name for name in AGENT_REVIEW_FILES]]
        if all(path.exists() and read_text(path).strip() for path in required):
            labs.append((max(path.stat().st_mtime for path in required), idea_id))
    return [name for _mtime, name in sorted(labs, reverse=True)]


def _safe_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing {rel(path)}"
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return None, f"{rel(path)} invalid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"{rel(path)} must be a JSON object"
    return data, None


def _valid_iso(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _hash_current(item: object) -> tuple[bool, str]:
    if not isinstance(item, dict):
        return False, "missing path/sha256"
    rel_path = str(item.get("path") or "")
    expected = str(item.get("sha256") or "")
    if not rel_path or not expected:
        return False, "missing path/sha256"
    path = ROOT / rel_path
    if not path.exists():
        return False, f"missing file: {rel_path}"
    if sha256(path) != expected:
        return False, f"hash mismatch: {rel_path}"
    return True, ""


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def agent_run_matrix(idea_id: str | None, lab: Path) -> dict[str, Any]:
    path = lab / "agent_runs.json"
    report: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "status": "MISSING",
        "errors": [],
        "roles": {},
    }
    manifest_path = lab / "agent_review_manifest.json"
    manifest, manifest_error = _safe_json(manifest_path) if manifest_path.exists() else ({}, None)
    manifest_reviews = manifest.get("reviews", {}) if isinstance(manifest, dict) else {}
    if manifest_error:
        report["errors"].append(manifest_error)
        manifest_reviews = {}

    data: dict[str, Any] = {}
    if path.exists():
        data, error = _safe_json(path)
        if error:
            report["errors"].append(error)
            data = {}
    runs = data.get("runs", {}) if isinstance(data, dict) else {}
    if path.exists() and not isinstance(runs, dict):
        report["errors"].append("agent_runs.json missing runs mapping")
        runs = {}
    if path.exists() and data.get("schema_version") != 1:
        report["errors"].append("agent_runs.json schema_version must be 1")
    if path.exists() and idea_id and data.get("idea_id") != idea_id:
        report["errors"].append("agent_runs.json idea_id mismatch")

    expected_inputs = [(lab / "original_idea.md").relative_to(ROOT).as_posix(), (lab / "deepseek_idea.md").relative_to(ROOT).as_posix()]
    for role, filename in AGENT_ROLES.items():
        run = runs.get(role)
        item: dict[str, Any] = {
            "role": role,
            "review_file": rel(lab / filename),
            "has_run": isinstance(run, dict),
            "agent_id": None,
            "completed_at": None,
            "runner_type": None,
            "runner_id": None,
            "transcript_hash_current": False,
            "isolation_attestation": False,
            "input_hashes_current": False,
            "output_hash_current": False,
            "manifest_covered": False,
            "status": "MISSING_RUN",
            "errors": [],
        }
        if not isinstance(run, dict):
            item["errors"].append(f"missing agent run for {role}")
            report["roles"][role] = item
            continue

        item["agent_id"] = str(run.get("agent_id") or "")
        item["completed_at"] = run.get("completed_at")
        item["runner_type"] = run.get("runner_type")
        item["runner_id"] = run.get("runner_id")
        item["isolation_attestation"] = bool(str(run.get("isolation_attestation") or "").strip())
        if run.get("role") != role:
            item["errors"].append("role mismatch")
        if not item["agent_id"]:
            item["errors"].append("missing agent_id")
        if item["runner_type"] not in {"codex_subagent", "external_agent"}:
            item["errors"].append("missing valid runner_type")
        if not str(item["runner_id"] or "").strip():
            item["errors"].append("missing runner_id")
        if not item["isolation_attestation"]:
            item["errors"].append("missing isolation_attestation")
        if not _valid_iso(item["completed_at"]):
            item["errors"].append("missing valid completed_at")

        input_files = run.get("input_files")
        if not isinstance(input_files, list):
            item["errors"].append("input_files must be a list")
            input_files = []
        input_by_path = {str(entry.get("path")): entry for entry in input_files if isinstance(entry, dict)}
        input_ok = True
        for expected in expected_inputs:
            ok, error = _hash_current(input_by_path.get(expected))
            input_ok = input_ok and ok
            if error:
                item["errors"].append(f"input {expected}: {error}")
        extras = sorted(set(input_by_path) - set(expected_inputs))
        if extras:
            item["errors"].append(f"unexpected inputs: {', '.join(extras)}")
            input_ok = False
        item["input_hashes_current"] = input_ok

        allowed_inputs = run.get("allowed_inputs")
        if not isinstance(allowed_inputs, list):
            item["errors"].append("allowed_inputs must be a list")
            allowed_inputs = []
        elif allowed_inputs != input_files:
            item["errors"].append("allowed_inputs must match input_files")
        if run.get("allowed_inputs_sha256") != _stable_hash(allowed_inputs):
            item["errors"].append("allowed_inputs_sha256 mismatch")

        output = run.get("output_file")
        expected_output = (lab / filename).relative_to(ROOT).as_posix()
        if isinstance(output, dict) and output.get("path") != expected_output:
            item["errors"].append(f"output path must be {expected_output}")
        output_ok, output_error = _hash_current(output)
        item["output_hash_current"] = output_ok
        if output_error:
            item["errors"].append(f"output: {output_error}")

        transcript_ok, transcript_error = _hash_current(run.get("transcript_file"))
        item["transcript_hash_current"] = transcript_ok
        if transcript_error:
            item["errors"].append(f"transcript: {transcript_error}")
        elif isinstance(run.get("transcript_file"), dict) and run["transcript_file"].get("sha256") != run.get("transcript_sha256"):
            item["errors"].append("transcript_sha256 mismatch")
            item["transcript_hash_current"] = False

        review = manifest_reviews.get(role) if isinstance(manifest_reviews, dict) else None
        item["manifest_covered"] = (
            isinstance(review, dict)
            and review.get("agent_id") == item["agent_id"]
            and isinstance(review.get("agent_run"), dict)
            and review["agent_run"].get("output_file") == output
        )
        if item["errors"]:
            item["status"] = "STALE_OR_INVALID"
        elif manifest_path.exists() and item["manifest_covered"]:
            item["status"] = "MANIFESTED"
        elif manifest_path.exists():
            item["status"] = "MANIFEST_MISMATCH"
        else:
            item["status"] = "RECORDED"
        report["roles"][role] = item

    role_statuses = [item["status"] for item in report["roles"].values()]
    if any(status in {"MISSING_RUN", "STALE_OR_INVALID", "MANIFEST_MISMATCH"} for status in role_statuses) or report["errors"]:
        report["status"] = "NOT_READY"
    elif role_statuses and all(status == "MANIFESTED" for status in role_statuses):
        report["status"] = "MANIFESTED"
    elif role_statuses and all(status == "RECORDED" for status in role_statuses):
        report["status"] = "RECORDED"
    else:
        report["status"] = "MISSING"
    return report


def analyze_idea_lab(idea_id: str | None = None) -> dict[str, Any]:
    idea_id = idea_id or latest_idea_id()
    if not idea_id:
        return {
            "idea_id": None,
            "status": "NO_LAB",
            "can_select": False,
            "blockers": ["no idea lab found"],
            "next_action": "Say `想法：...` / `开书实验`.",
            "files": {},
        }

    lab = idea_lab_root() / idea_id
    files = {name: file_report(lab / name) for name in [*REQUIRED_INPUTS, "agent_runs.json"]}
    blockers: list[str] = []
    warnings: list[str] = []

    if not lab.exists():
        return {
            "idea_id": idea_id,
            "status": "MISSING",
            "can_select": False,
            "blockers": [f"missing idea lab: {rel(lab)}"],
            "next_action": "Create the idea lab again with `python scripts/novel.py idea --text ...`.",
            "files": files,
        }

    missing = [name for name, item in files.items() if not item["exists"]]
    empty = [name for name, item in files.items() if item["exists"] and not item["nonempty"]]
    placeholder = [
        name
        for name, item in files.items()
        if name != "original_idea.md" and item["exists"] and item["has_placeholders"]
    ]
    if missing:
        blockers.extend(f"missing idea-lab input: {name}" for name in missing)
    if empty:
        blockers.extend(f"empty idea-lab input: {name}" for name in empty)
    if placeholder:
        blockers.extend(f"idea-lab input still has placeholders: {name}" for name in placeholder)

    if (lab / "codex_synthesis.md").exists():
        blockers.extend(validate_codex_synthesis(read_text(lab / "codex_synthesis.md")))

    if (lab / "agent_review_manifest.json").exists():
        blockers.extend(validate_agent_review_manifest(idea_id, lab))
    elif all((lab / name).exists() and read_text(lab / name).strip() for name in ("original_idea.md", "deepseek_idea.md", *AGENT_REVIEW_FILES)):
        blockers.append("missing idea-lab input: state/idea_lab/{idea_id}/agent_review_manifest.json".format(idea_id=idea_id))

    runs = agent_run_matrix(idea_id, lab)
    if all((lab / name).exists() and read_text(lab / name).strip() for name in ("original_idea.md", "deepseek_idea.md", *AGENT_REVIEW_FILES)):
        for error in runs.get("errors", []):
            blockers.append(f"agent run metadata: {error}")
        for role, item in runs.get("roles", {}).items():
            for error in item.get("errors", []):
                blockers.append(f"agent run metadata {role}: {error}")

    if all((lab / name).exists() for name in ("original_idea.md", "deepseek_idea.md", *AGENT_REVIEW_FILES, "codex_synthesis.md")):
        blockers.extend(validate_output_freshness(lab))

    selection_exists = (lab / "selection.json").exists()
    freeze_exists = (lab / "core_setting_freeze.json").exists()
    freeze_errors = validate_freeze(idea_id) if freeze_exists else []
    if freeze_errors:
        warnings.extend(freeze_errors)

    if freeze_exists and not freeze_errors:
        status = "LOCKED"
        next_action = "Core setting freeze is ready; proceed with `写下一章` / brief candidates."
    elif selection_exists:
        status = "SELECTED_NOT_LOCKED"
        next_action = f"Run `python scripts/novel.py core-freeze-check --idea-id {idea_id}` and inspect freeze evidence."
    elif not (lab / "deepseek_idea.md").exists():
        status = "WAITING_DEEPSEEK"
        next_action = f"Run `python scripts/novel.py idea --id {idea_id} --force --text ...` or restore DeepSeek output."
    elif not all((lab / name).exists() and read_text(lab / name).strip() for name in AGENT_REVIEW_FILES):
        status = "WAITING_AGENT_REVIEWS"
        next_action = "Complete product_founder, technical_lead, and qa_release review files."
    elif not (lab / "agent_review_manifest.json").exists():
        status = "WAITING_AGENT_MANIFEST"
        next_action = f"Run `python scripts/novel.py idea-agent-manifest --id {idea_id}`."
    elif not (lab / "codex_synthesis.md").exists():
        status = "WAITING_SYNTHESIS"
        next_action = "Write codex_synthesis.md with Direction A/B/C and all required fields."
    elif blockers:
        status = "BLOCKED"
        next_action = f"Fix blockers, then rerun `python scripts/novel.py idea-status --id {idea_id}`."
    else:
        status = "READY_TO_SELECT"
        next_action = f"Run `python scripts/novel.py idea-select --id {idea_id} --choice A` after human choice."

    return {
        "idea_id": idea_id,
        "status": status,
        "can_select": status == "READY_TO_SELECT",
        "blockers": blockers,
        "warnings": warnings,
        "next_action": next_action,
        "files": files,
        "agent_runs": runs,
        "selection_exists": selection_exists,
        "freeze_exists": freeze_exists,
    }


def decision_for(chapter: str) -> str | None:
    text = read_text(ROOT / "reviews" / chapter / "decision.md")
    for line in text.splitlines():
        if line.startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return None


def shipped_through(number: int) -> bool:
    return all(decision_for(f"v01_c{idx:03d}") == "Ship" for idx in range(1, number + 1))


def first_unshipped(limit: int = 126) -> str:
    for idx in range(1, limit + 1):
        chapter = f"v01_c{idx:03d}"
        if decision_for(chapter) != "Ship":
            return chapter
    return "v01_c127"


def chapter_paths(chapter: str) -> dict[str, Path]:
    volume, chapter_file = chapter_parts(chapter)
    return {
        "brief": ROOT / "outline" / "chapter_briefs" / f"{chapter}.md",
        "brief_landing": ROOT / "reviews" / chapter / "brief_landing.json",
        "brief_pack": ROOT / "state" / "context_pack" / f"{chapter}_brief.md",
        "context_pack": ROOT / "state" / "context_pack" / f"{chapter}.md",
        "context_quality": ROOT / "state" / "derived" / "context_quality" / f"{chapter}.json",
        "codex_prompt": ROOT / "external_runs" / "codex" / chapter / "draft.prompt.md",
        "codex_prompt_manifest": ROOT / "external_runs" / "codex" / chapter / "draft.prompt.manifest.json",
        "deepseek_prompt": ROOT / "external_runs" / "deepseek" / chapter / "generate.prompt.md",
        "deepseek_prompt_manifest": ROOT / "external_runs" / "deepseek" / chapter / "generate.prompt.manifest.json",
        "codex_draft": ROOT / "drafts" / "codex" / f"{chapter}.md",
        "deepseek_draft": ROOT / "drafts" / "deepseek" / f"{chapter}.md",
        "selection": ROOT / "state" / "selections" / f"{chapter}.json",
        "official": ROOT / "chapters" / volume / chapter_file,
        "style_metrics": ROOT / "reviews" / chapter / "style_metrics.json",
        "series_style": ROOT / "reviews" / chapter / "series_style.json",
        "decision": ROOT / "reviews" / chapter / "decision.md",
    }


def section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    if "\n## " in tail:
        tail = tail.split("\n## ", 1)[0]
    return tail.strip()


def labeled_value(body: str, key: str) -> str:
    for raw in body.splitlines():
        line = raw.strip().lstrip("-*+ ").strip()
        if not line:
            continue
        if ":" in line:
            label, value = line.split(":", 1)
        elif "：" in line:
            label, value = line.split("：", 1)
        else:
            continue
        if label.strip() == key:
            return value.strip()
    return ""


def _json_or_none(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def chapter_landing_uses_polish(chapter: str) -> bool:
    landing = _json_or_none(ROOT / "reviews" / chapter / "chapter_landing.json") or {}
    for item in landing.get("inputs", []) or []:
        if isinstance(item, dict) and str(item.get("path", "")).startswith("drafts/polish/"):
            return True
    return False


def thread_has_ledger_entry(chapter: str, thread_id: str) -> bool:
    if not thread_id:
        return False
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("chapter") != chapter:
            continue
        if event.get("type") not in {"thread_opened", "thread_advanced", "thread_paid_off"}:
            continue
        values = {str(event.get("thread_id", "")), str(event.get("fact", ""))}
        values |= {str(item) for item in event.get("tags", []) if str(item).strip()}
        values |= {str(item) for item in event.get("entities", []) if str(item).strip()}
        if thread_id in values or any(thread_id in value for value in values):
            return True
    return False


def advisory_snapshot(chapter: str, idea_id: str | None) -> dict[str, str]:
    lab = idea_lab_root() / idea_id if idea_id else None
    commercial = "缺"
    market = "缺"
    if lab is not None:
        commercial_data = _json_or_none(lab / "commercial_idea.json")
        if commercial_data:
            risk_text = json.dumps(commercial_data, ensure_ascii=False)
            commercial = "有风险" if "HIGH_RISK" in risk_text or "BLOCKED" in risk_text else "有"
        market_data = _json_or_none(lab / "market_scan.json")
        if market_data:
            risk = str(market_data.get("copyright_risk", "")).upper()
            market = "高相似风险" if "HIGH" in risk or "BLOCKED" in risk else "有"

    brief = read_text(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md")
    title = section(brief, "章节标题")
    intro = section(brief, "章节简介")
    end_state = section(brief, "章末状态变化")
    if not brief:
        structure = "缺"
    elif any(marker in title + intro for marker in PLACEHOLDERS):
        structure = "冲突"
    elif title and intro:
        intro_len = len("".join(intro.split()))
        structure = "完整" if 80 <= intro_len <= 180 else "弱"
    else:
        structure = "弱"

    if not end_state:
        end_state_status = "弱"
    else:
        thread_id = labeled_value(end_state, "affected_thread")
        if thread_id and ("P0" in end_state or "P1" in end_state) and not thread_has_ledger_entry(chapter, thread_id):
            end_state_status = "未落账"
        elif any(marker in end_state for marker in PLACEHOLDERS):
            end_state_status = "弱"
        else:
            end_state_status = "有"

    if chapter_landing_uses_polish(chapter):
        polish = "已采用"
    elif (ROOT / "drafts" / "polish" / f"{chapter}.md").exists():
        polish = "候选"
    else:
        polish = "无"

    series_report = ROOT / "reviews" / chapter / "series_style.json"
    if series_report.exists():
        series_data = _json_or_none(series_report) or {}
        series_style = str(series_data.get("status", "unknown")).lower()
    elif chapter_number(chapter) >= 4:
        series_style = "missing"
    else:
        series_style = "warmup"

    return {
        "commercial_positioning": commercial,
        "market_scan": market,
        "chapter_structure": structure,
        "end_state_change": end_state_status,
        "polish": polish,
        "series_style": series_style,
    }


def contract_snapshot() -> dict[str, str]:
    book_data, book_error = _safe_json(BOOK_JSON)
    style_data, style_error = _safe_json(CONTRACT_JSON)
    profile_data, _profile_error = _safe_json(STYLE_PROFILE)
    volume_data, volume_error = _safe_json(volume_json_path("v01"))

    book_errors = validate_book_outline_contract(book_data or {}, official=True)
    style_errors = validate_style_contract(style_data or {}, official=True)
    if book_error or not isinstance(book_data, dict) or book_data.get("status") != "READY":
        book_status = "missing"
    else:
        book_status = "ready" if not book_errors else "conflict"
    if style_error or not isinstance(style_data, dict) or style_data.get("status") != "READY":
        style_status = "missing"
    else:
        style_status = "ready" if not style_errors else "drift"
    if profile_data and profile_data.get("status") == "READY":
        profile_status = "ready"
    elif profile_data:
        profile_status = "not_built"
    else:
        profile_status = "missing"
    if volume_error:
        volume_status = "missing"
    elif not validate_volume(volume_data or {}):
        volume_status = "ready"
    else:
        volume_status = "rough"
    target = str((book_data or {}).get("target_word_count") or "unset") if isinstance(book_data, dict) else "unset"
    genre = "clear" if isinstance(book_data, dict) and not has_placeholders(BOOK_JSON) and (book_data or {}).get("genre_lane") else "missing"
    ending = "clear" if isinstance(book_data, dict) and not has_placeholders(BOOK_JSON) and (book_data or {}).get("ending_direction") else "missing"
    return {
        "book_outline": book_status,
        "volume_outline": volume_status,
        "target_word_count": target,
        "genre_lane": genre,
        "ending_direction": ending,
        "style_contract": style_status,
        "style_profile": profile_status,
    }


def gate_prompt() -> str | None:
    if shipped_through(125) and gate_decision("e") != "continue":
        return "进入 Gate E，评估是否进入 300 万字模式，并给我 continue / pause / kill / rework 裁决建议。"
    if shipped_through(25) and gate_decision("c") != "continue":
        return "进入 Gate C，生成 gate_c_assessment，评估阶段高潮、不可逆变化、伏笔负债、设定膨胀和卷内结构。"
    if shipped_through(10) and gate_decision("b") != "continue":
        return "进入 Gate B，检查主角欲望、主要阻力、管理成本、连续问题和每 3 章爽点复盘。"
    if shipped_through(3) and gate_decision("a") != "continue":
        return "进入 Gate A 检查，汇总前三章证据，并给我是否继续到第 4 章的裁决建议。"
    return None


def blocking_gate() -> str | None:
    if shipped_through(125) and gate_decision("e") != "continue":
        return "E"
    if shipped_through(25) and gate_decision("c") != "continue":
        return "C"
    if shipped_through(10) and gate_decision("b") != "continue":
        return "B"
    if shipped_through(3) and gate_decision("a") != "continue":
        return "A"
    return None


def prompt_for_chapter(chapter: str) -> str:
    paths = chapter_paths(chapter)
    if not paths["brief"].exists() or has_placeholders(paths["brief"]):
        return (
            f"写下一章：先为 {chapter} 生成 brief 候选。Codex 写 drafts/codex/{chapter}_brief.md，"
            f"DeepSeek 写 drafts/deepseek/{chapter}_brief.md；然后汇总优劣，让我选择 / 混合 / 修改后再落正式 brief。"
        )
    if not paths["brief_landing"].exists():
        return "正式 brief 已有内容，但还缺 brief landing provenance。请汇总 brief 候选，让我裁决后运行 select-brief 和 land-brief。"
    if not paths["context_pack"].exists():
        return f"确认 brief，开章 {chapter}。"
    if not paths["codex_prompt_manifest"].exists():
        return f"Run `python scripts/novel.py codex-draft-prompt {chapter}` to create the Codex candidate prompt with Candidate Style Requirements evidence."
    if not paths["codex_draft"].exists() or not read_text(paths["codex_draft"]).strip():
        return f"生成 Codex 候选稿，并调用 DeepSeek 生成 {chapter} 外部候选。"
    if not paths["selection"].exists():
        return f"比较 {chapter} 的 Codex/DeepSeek 候选，给我推荐选择和理由。"
    if not paths["official"].exists() or not read_text(paths["official"]).strip():
        return f"按已选候选方向，落正式正文 {chapter}；若人类已选 DeepSeek，可直采用其候选稿，但仍需由 Codex 记录 landing provenance。"
    if decision_for(chapter) != "Ship":
        return f"收章 {chapter}。"
    next_number = chapter_number(chapter) + 1
    return f"写下一章，并给我 v01_c{next_number:03d} 的 brief 候选。"


def next_prompt(chapter: str | None = None) -> str:
    gate = gate_prompt()
    if gate:
        return gate
    idea = analyze_idea_lab()
    freeze_errors = validate_freeze()
    if freeze_errors and idea["status"] == "WAITING_AGENT_MANIFEST":
        return f"记录开书实验 {idea['idea_id']} 的三类 agent provenance：运行 idea-agent-manifest，然后确认 Codex synthesis 并定盘。"
    if freeze_errors and idea["status"] == "READY_TO_SELECT" and idea.get("idea_id"):
        return (
            f"总结开书实验 {idea['idea_id']} 的 A/B/C/Mixed 方向，选择一个方向并锁定开书前核心设定："
            "世界观核心规则、主角异常原因、主角家属/亲密关系、前三章约束和不可违背红线。"
        )
    if freeze_errors and idea["status"] == "BLOCKED" and idea.get("idea_id"):
        return f"修复开书实验 {idea['idea_id']} 的 readiness 阻塞；先运行 `python scripts/novel.py idea-status --id {idea['idea_id']}`。"
    if freeze_errors:
        return "开书前先走开书实验：用 DeepSeek 和 product_founder/technical_lead/qa_release 三类 agent 固定世界观、主角异常原因和主角家属关系。"
    book_outline_errors = validate_book_outline_contract(_safe_json(BOOK_JSON)[0] or {}, official=True)
    if book_outline_errors:
        return "定纲：运行 book-outline-start / book-outline-land，先把书本总纲落为 READY，再进入 brief 候选。"
    style_contract_errors = validate_style_contract(_safe_json(CONTRACT_JSON)[0] or {}, official=True)
    if style_contract_errors:
        return "定风格：运行 style-contract-start / style-contract-land，先把写作风格契约落为 READY，再进入 brief 候选。"
    if has_placeholders(ROOT / "outline" / "premise.md"):
        return "我想开一本新书。先判断应该走开书实验还是启动问卷，并给我下一步提示词。"
    return prompt_for_chapter(chapter or first_unshipped())


def dashboard(chapter: str | None = None) -> dict[str, Any]:
    chapter = chapter or first_unshipped()
    freeze_errors = validate_freeze()
    book_outline_errors = validate_book_outline_contract(_safe_json(BOOK_JSON)[0] or {}, official=True)
    style_contract_errors = validate_style_contract(_safe_json(CONTRACT_JSON)[0] or {}, official=True)
    idea = analyze_idea_lab()
    paths = chapter_paths(chapter)
    locks = unresolved_locks()
    prompt = next_prompt(chapter)
    gate = blocking_gate()
    if locks:
        phase_id = "stop_lock"
        blocker = "存在 stop lock，写入动作被暂停"
        why = "; ".join(f"{item.get('id')}: {item.get('reason')}" for item in locks)
        command = "先处理 `stop-list` / `stop-resolve`。"
    elif freeze_errors:
        phase_id = "opening_experiment"
        blocker = "缺核心设定冻结"
        why = "开正文前必须完成 DeepSeek + 三类 agent 开书实验并锁定 core_setting_freeze。"
        command = "想法：..."
    elif book_outline_errors:
        phase_id = "book_outline_contract"
        blocker = "book outline contract is not ready"
        why = "; ".join(book_outline_errors[:3])
        command = "定纲 / book-outline-land"
    elif style_contract_errors:
        phase_id = "style_contract"
        blocker = "style contract is not ready"
        why = "; ".join(style_contract_errors[:3])
        command = "定风格 / style-contract-land"
    elif gate:
        phase_id = "gate_review"
        blocker = f"Gate {gate} 等待总编裁决"
        why = "已到阶段门槛，需要先检查证据并记录人类 gate 决策。"
        command = prompt
    elif not paths["brief"].exists() or has_placeholders(paths["brief"]):
        phase_id = "brief_candidates"
        blocker = f"{chapter} brief 未正式可用"
        why = "正式 brief 缺失或仍有占位，必须先走 brief 候选选择与 landing。"
        command = "写下一章"
    elif not paths["context_pack"].exists():
        phase_id = "context_pack"
        blocker = f"{chapter} context pack 未生成"
        why = "正式写作只能读当章 context pack 和正式 brief。"
        command = f"开章 {chapter}"
    else:
        phase_id = "draft_or_close"
        blocker = f"{chapter} 可继续推进"
        why = "已具备下一步所需基础材料，按候选/收章流程继续。"
        command = prompt

    env_blockers: list[str] = []
    if not os.environ.get("DEEPSEEK_API_KEY"):
        env_blockers.append("DEEPSEEK_API_KEY is missing")
    template = template_readiness()
    story_ready = phase_id == "draft_or_close" and not locks and not freeze_errors and not book_outline_errors and not style_contract_errors and not gate
    readiness = {
        "env_status": "ENV_READY" if not env_blockers else "ENV_NOT_READY",
        "template_status": template["status"],
        "story_status": "STORY_READY" if story_ready else "STORY_NOT_READY",
        "env_blockers": env_blockers,
        "template_check_returncode": template["returncode"],
        "template_check_detail": template["detail"],
    }

    writes = ["state/idea_lab/", "external_runs/deepseek/"] if freeze_errors else []
    if not freeze_errors:
        if not paths["brief"].exists() or has_placeholders(paths["brief"]):
            writes = [f"drafts/codex/{chapter}_brief.md", f"drafts/deepseek/{chapter}_brief.md", f"reviews/{chapter}/brief_candidate_selection.md"]
        elif not paths["context_pack"].exists():
            writes = [f"state/context_pack/{chapter}.md", f"state/derived/context_quality/{chapter}.json"]
        elif not paths["codex_prompt_manifest"].exists():
            writes = [f"external_runs/codex/{chapter}/draft.prompt.md", f"external_runs/codex/{chapter}/draft.prompt.manifest.json"]
        else:
            writes = [f"drafts/codex/{chapter}.md", f"drafts/deepseek/{chapter}.md", f"external_runs/deepseek/{chapter}/generate.prompt.manifest.json", f"reviews/{chapter}/"]

    risk_flags: list[str] = []
    if locks:
        risk_flags.append("stop_lock_open")
    if freeze_errors:
        risk_flags.append("core_freeze_missing")
    if book_outline_errors:
        risk_flags.append("book_outline_not_ready")
    if style_contract_errors:
        risk_flags.append("style_contract_not_ready")
    if has_placeholders(ROOT / "outline" / "premise.md"):
        risk_flags.append("premise_placeholders")
    if has_placeholders(ROOT / "outline" / "chapter_briefs" / "v01_c001.md"):
        risk_flags.append("c001_brief_placeholders")
    stale = stale_overview(chapter)
    if stale.get("status") not in {None, "CLEAR"}:
        risk_flags.append(f"stale_{str(stale.get('status')).lower()}")
    if gate:
        risk_flags.append(f"gate_{gate.lower()}_pending")

    evidence_paths = [rel(paths["brief"])]
    if paths["context_pack"].exists():
        evidence_paths.append(rel(paths["context_pack"]))
    if paths["context_quality"].exists():
        evidence_paths.append(rel(paths["context_quality"]))
    if paths["codex_prompt_manifest"].exists():
        evidence_paths.append(rel(paths["codex_prompt_manifest"]))
    if paths["deepseek_prompt_manifest"].exists():
        evidence_paths.append(rel(paths["deepseek_prompt_manifest"]))
    if paths["style_metrics"].exists():
        evidence_paths.append(rel(paths["style_metrics"]))
    if paths["series_style"].exists():
        evidence_paths.append(rel(paths["series_style"]))
    idea_id = idea.get("idea_id")
    advisory = advisory_snapshot(chapter, idea_id)
    contracts = contract_snapshot()
    if idea_id:
        evidence_paths.extend(
            [
                f"state/idea_lab/{idea_id}/agent_runs.json",
                f"state/idea_lab/{idea_id}/agent_review_manifest.json",
                f"state/idea_lab/{idea_id}/core_setting_freeze.json",
            ]
        )
        for path in (
            f"state/idea_lab/{idea_id}/commercial_idea.json",
            f"state/idea_lab/{idea_id}/market_scan.json",
        ):
            if (ROOT / path).exists():
                evidence_paths.append(path)

    return {
        "root": str(ROOT),
        "git": git_status(),
        "deepseek_api_key": "set" if os.environ.get("DEEPSEEK_API_KEY") else "missing",
        "env_status": readiness["env_status"],
        "template_status": readiness["template_status"],
        "story_status": readiness["story_status"],
        "readiness": readiness,
        "chapter": chapter,
        "phase_id": phase_id,
        "blocker": blocker,
        "blocking_gate": gate,
        "why": why,
        "human_action": command,
        "codex_action": prompt,
        "recommended_command": command,
        "next_prompt": prompt,
        "reads": [rel(paths["brief"]), rel(paths["context_pack"])],
        "writes": writes,
        "risk_flags": risk_flags,
        "advisory": advisory,
        "contracts": contracts,
        "evidence_paths": evidence_paths,
        "freeze_ready": not freeze_errors,
        "freeze_errors": freeze_errors,
        "book_outline_ready": not book_outline_errors,
        "book_outline_errors": book_outline_errors,
        "style_contract_ready": not style_contract_errors,
        "style_contract_errors": style_contract_errors,
        "idea": idea,
        "locks": locks,
        "gates": {
            "A": gate_decision("a") or "not recorded",
            "B": gate_decision("b") or "not recorded",
            "C": gate_decision("c") or "not recorded",
            "E": gate_decision("e") or "not recorded",
            "F": gate_decision("f") or "not recorded",
            "G": gate_decision("g") or "not recorded",
            "H": gate_decision("h") or "not recorded",
        },
        "stale": stale,
        "premise_placeholders": has_placeholders(ROOT / "outline" / "premise.md"),
        "c001_brief_placeholders": has_placeholders(ROOT / "outline" / "chapter_briefs" / "v01_c001.md"),
        "event_ledger_exists": (ROOT / "state" / "event_ledger.jsonl").exists(),
    }


def stale_overview(chapter: str | None = None) -> dict[str, Any]:
    try:
        from stale_check import stale_summary

        return stale_summary(chapter)
    except Exception as exc:
        return {"status": "UNKNOWN", "error": str(exc)}
