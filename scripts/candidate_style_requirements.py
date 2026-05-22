from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json
from style_contract import REQUIRED_FIELDS, validate_contract
from reader_personality_contracts import READER_PROMISE_JSON, READER_PROMISE_MD, load_reader_promise, validate_reader_promise
from reader_reward_policy import POLICY_PATH


HEADER = "# Candidate Style Requirements"
CONTRACT_JSON = ROOT / "state" / "project_style_contract.json"
CONTRACT_MD = ROOT / "state" / "project_style_contract.md"
STYLE_GUIDE = ROOT / "bible" / "style_guide.md"
STYLE_PROFILE = ROOT / "state" / "derived" / "style_profile.json"
DERIVED_PERSONALITY = ROOT / "state" / "derived" / "personality" / "protagonist.json"
PROTAGONIST_PROGRESSION = ROOT / "state" / "derived" / "protagonist_progression.json"
WORLD_REVEAL_LEDGER = ROOT / "state" / "derived" / "world_reveal_ledger.json"
SUSPENSE_LEDGER = ROOT / "state" / "derived" / "suspense_ledger.json"
PROMPT_RECORDED_BUT_POST_CHAPTER_MUTABLE_ROLES = {
    "derived_personality",
    "derived_current_personality",
    "protagonist_progression",
    "world_reveal_ledger",
    "suspense_ledger",
}


PLACEHOLDERS = ("TODO", "TBD", "待定", "待填", "待评", "placeholder")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_ref(path: Path, role: str) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path), "role": role, "exists": path.exists()}
    if path.exists() and path.is_file():
        item["sha256"] = sha256(path)
    return item


def has_placeholder_text(text: str) -> bool:
    lowered = text.lower()
    return not text.strip() or any(marker.lower() in lowered for marker in PLACEHOLDERS)


def render_value(value: Any, *, limit: int = 360) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value or "").strip()
    if len(text) > limit:
        return text[: limit - 18].rstrip() + " ...[truncated]"
    return text or "none"


def extract_declared_value(text: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(key)}\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip().strip("`")
    return value or None


def detect_conflicts(contract: dict[str, Any], texts: list[tuple[Path, str]]) -> list[str]:
    blockers: list[str] = []
    for key in REQUIRED_FIELDS:
        expected = render_value(contract.get(key), limit=200)
        if not expected or expected == "none":
            continue
        for path, text in texts:
            declared = extract_declared_value(text, key)
            if declared and declared != expected:
                blockers.append(f"{rel(path)} declares {key}={declared!r}, but style contract has {expected!r}")
    return blockers


def load_contract() -> tuple[dict[str, Any], list[str]]:
    if not CONTRACT_JSON.exists():
        return {}, [f"missing style contract: {rel(CONTRACT_JSON)}"]
    try:
        data = read_json(CONTRACT_JSON, {})
    except json.JSONDecodeError as exc:
        return {}, [f"invalid JSON in {rel(CONTRACT_JSON)}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{rel(CONTRACT_JSON)} must be a JSON object"]
    errors = validate_contract(data, official=True)
    if data.get("status") != "READY":
        errors.append(f"style contract status must be READY, got {data.get('status', 'MISSING')}")
    return data, errors


def profile_mode_for(chapter: str, blockers: list[str]) -> tuple[str, dict[str, Any]]:
    if not STYLE_PROFILE.exists():
        if chapter_number(chapter) < 4:
            return "warmup_not_hard_gate", {}
        blockers.append(f"post-warmup chapter requires READY style profile: {rel(STYLE_PROFILE)}")
        return "ready_profile_required", {}
    try:
        profile = read_json(STYLE_PROFILE, {})
    except json.JSONDecodeError as exc:
        blockers.append(f"invalid JSON in {rel(STYLE_PROFILE)}: {exc}")
        return "ready_profile_required" if chapter_number(chapter) >= 4 else "warmup_not_hard_gate", {}
    if not isinstance(profile, dict):
        blockers.append(f"{rel(STYLE_PROFILE)} must be a JSON object")
        return "ready_profile_required" if chapter_number(chapter) >= 4 else "warmup_not_hard_gate", {}
    if chapter_number(chapter) < 4:
        return "warmup_not_hard_gate", profile
    if profile.get("status") != "READY":
        blockers.append(
            f"post-warmup chapter requires READY style profile, got {profile.get('status', 'MISSING')}; run style-profile-build"
        )
    return "ready_profile_required", profile


def source_refs(include_profile: bool) -> list[dict[str, Any]]:
    refs = [
        file_ref(CONTRACT_JSON, "project_style_contract_json"),
        file_ref(CONTRACT_MD, "project_style_contract_markdown"),
        file_ref(STYLE_GUIDE, "style_guide"),
    ]
    if include_profile:
        refs.append(file_ref(STYLE_PROFILE, "derived_style_profile"))
    refs.extend(
        [
            file_ref(READER_PROMISE_JSON, "project_reader_promise_json"),
            file_ref(READER_PROMISE_MD, "project_reader_promise_markdown"),
            file_ref(POLICY_PATH, "reader_reward_policy"),
            file_ref(DERIVED_PERSONALITY, "derived_current_personality"),
            file_ref(PROTAGONIST_PROGRESSION, "protagonist_progression"),
            file_ref(WORLD_REVEAL_LEDGER, "world_reveal_ledger"),
            file_ref(SUSPENSE_LEDGER, "suspense_ledger"),
        ]
    )
    return refs


def context_pack_ref(chapter: str) -> tuple[dict[str, Any], list[str]]:
    path = ROOT / "state" / "context_pack" / f"{chapter}.md"
    if not path.exists():
        return {"path": rel(path), "exists": False}, [f"missing context pack: {rel(path)}"]
    if not read_text(path).strip():
        return file_ref(path, "context_pack"), [f"context pack is empty: {rel(path)}"]
    return file_ref(path, "context_pack"), []


def render_requirements(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    blockers: list[str] = []
    warnings: list[str] = []
    contract, contract_errors = load_contract()
    blockers.extend(contract_errors)
    reader_promise = load_reader_promise()
    blockers.extend(validate_reader_promise(reader_promise, require_ready=True))

    md_text = read_text(CONTRACT_MD)
    guide_text = read_text(STYLE_GUIDE)
    if not CONTRACT_MD.exists() or has_placeholder_text(md_text):
        blockers.append(f"missing or placeholder human style contract: {rel(CONTRACT_MD)}")
    if not STYLE_GUIDE.exists() or has_placeholder_text(guide_text):
        blockers.append(f"missing or placeholder style guide: {rel(STYLE_GUIDE)}")
    if contract:
        blockers.extend(detect_conflicts(contract, [(CONTRACT_MD, md_text), (STYLE_GUIDE, guide_text)]))

    profile_mode, profile = profile_mode_for(chapter, blockers)
    context_pack, context_errors = context_pack_ref(chapter)
    blockers.extend(context_errors)

    profile_status = str(profile.get("status", "MISSING")) if isinstance(profile, dict) and profile else "MISSING"
    include_profile_source = profile_mode == "ready_profile_required" or profile_status == "READY"
    if profile_mode == "warmup_not_hard_gate":
        warnings.append("Chapters 1-3 use the project style contract and style guide; derived series profile is not a hard gate yet.")

    lines = [
        HEADER,
        "",
        f"status: {'READY' if not blockers else 'BLOCKED'}",
        f"chapter: {chapter}",
        f"profile_mode: {profile_mode}",
        "",
        "## Priority",
        "",
        "- Brief, canon, event ledger, and context_pack facts outrank style guidance.",
        "- Candidate Style Requirements outrank model defaults and generic prose habits.",
        "- Style guidance must not introduce new facts, canon, event ledger entries, tools, abilities, or rules.",
        "- If style inputs are missing or contradictory, stop and report the blocker instead of drafting.",
        "",
        "## Project Voice",
        "",
    ]
    for key in REQUIRED_FIELDS:
        lines.append(f"- {key}: {render_value(contract.get(key) if contract else '')}")
    lines.extend(
        [
            "",
            "## Series Calibration",
            "",
            f"- profile_status: {profile_status}",
            f"- profile_mode: {profile_mode}",
        ]
    )
    if profile.get("baseline_policy"):
        lines.append(f"- baseline_policy: {render_value(profile.get('baseline_policy'))}")
    if profile.get("series_dimensions"):
        lines.append(f"- series_dimensions: {render_value(profile.get('series_dimensions'))}")
    if profile.get("allowed_ranges"):
        lines.append(f"- allowed_ranges: {render_value(profile.get('allowed_ranges'))}")
    lines.extend(
        [
            "",
            "## Reader Retention Requirements",
            "",
            "- 开篇必须从扰动、压力、异常、冲突或强人物动作开始，禁止先写日常流水账。",
            "- 每章必须有一个中段变化点，不能从头到尾按计划推进。",
            "- 章末必须给出下一章点击理由，不能只写等待、归档、沉默、继续观察。",
            "- 流程、表格、回函、检测、记录只能作为冲突工具，不能成为叙事主体。",
            "- 主角每章必须主动改变局面，哪怕改变带来更大麻烦。",
            "- 金手指必须定期展示能力、限制、反噬、升级或误导，不能长期只是发热和提示。",
            "- 本章必须按 reader promise 的手动 R 档兑现回报；不得把 R 档当成模板默认值。",
            "- R2+ 必须给出正文可匹配的回报证据；R3/R4 必须触达核心卖点或写清替代回报证据。",
            "- 世界观信息必须通过场景压力、人物选择或普通人反应展示。",
            "- 每章至少保留一句有传播力的台词、吐槽、反差句或情绪句。",
            "- 正文候选只把 Story Card 当创作输入；Machine Contract Appendix 是硬边界，不是叙事腔。",
            "- 禁止把“本章、合同、证据、门禁、流程”等审计词当旁白结构使用。",
            "",
            "# This Chapter Prose Risk Budget",
            "",
            "- 主语泛滥：禁止连续 3 个自然段以同一专名、代词或同构主语起句；优先用动作后果、物件反应、环境压力或他人视线承接。",
            "- 流程注水：电话、附件、记录、等待、审批、转发、回执、表格等流程动作必须改变冲突、信息差、关系或代价；否则删掉或压缩。",
            "- 主角零失误：本章至少呈现误判、代价、短期损失、被反制、暴露短板、依赖他人之一；不能全程最优解无成本推进。",
            "- 配角标签化：关键配角至少具备私心、误解、利益交换、遮掩、反向行动或迟疑之一；不能只提醒、阻拦、解释或递工具。",
            "- 悬念结尾同质化：章末钩子不得连续复用前两章同类形态；不要反复依赖新电话、新文件、新异常、提示音或一句话反转。",
            "- 对话 Q&A 化：关键对话不能连续“主角问 -> 对方解释”；回答必须带遮掩、反问、交易、误导、权力变化或情绪变化。",
            "- 异常密度过高：新增异常、规则、名词不得超出 brief 授权和世界观预算；未授权内容不得成为破局钥匙。",
            "",
            "## Project Reader Promise",
            "",
            render_value(reader_promise, limit=1200),
            "",
            "## Protagonist Initial Personality Contract",
            "",
            "- 第 1 章前主角人格来自 core_setting_freeze / characters.yaml；第 1 章后变化只能来自 character_state_change。",
            "- 不得无事件推翻 opening_misbelief、default_strategy 或 stress_response。",
            "",
            "## Current Personality Snapshot",
            "",
            read_text(DERIVED_PERSONALITY, "missing derived personality; rebuild derived state"),
            "",
            "## World Reveal Budget",
            "",
            read_text(WORLD_REVEAL_LEDGER, "missing world reveal ledger; rebuild derived state"),
            "",
            "## Suspense Ladder Requirements",
            "",
            read_text(SUSPENSE_LEDGER, "missing suspense ledger; rebuild derived state"),
            "",
            "## Language Memorability Requirements",
            "",
            "- 本章必须规划金句、梗、反差笑点、角色口头禅、标志动作或可截图传播句之一。",
            "- 禁止整章只有平铺解释、流程复述和无压迫的观察。",
            "",
            "## Anti-AI Taste Requirements",
            "",
            "- 禁止把潜台词直接翻译成总结腔；先让动作、误判、停顿、逃避或代价发生。",
            "- 关键角色每章至少暴露一次私利、隐瞒、错位判断、情绪越界或灰度动作；善意不能写成无菌。",
            "- 主角可以使坏，但必须有动机、风险、短期收益、长期后果和可追责痕迹。",
            "- 关键对白必须推进信息、暴露欲望、制造压力、遮掩真相、试探关系之一；纯主题陈述不能连续主导。",
            "- 句式必须有毛边：允许口语冗余、突然短断、非对称节奏和被场景打断的半句话。",
            "- 细节只保留有功能的细节：制造选择、误导、伏笔、代价、关系变化或场景压力；装饰性仿真细节要删或弱化。",
            "- 灰度行为、偷懒、撒谎、迁怒、嫉妒、怯懦和自保可以出现，但不能无后果地被叙事洗白。",
            "",
            "## Source Trace",
            "",
            f"- context_pack: {context_pack.get('path')} sha256={context_pack.get('sha256', 'missing')}",
        ]
    )
    for item in source_refs(include_profile_source):
        lines.append(f"- {item['role']}: {item['path']} sha256={item.get('sha256', 'missing')}")
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)

    block = "\n".join(lines).rstrip() + "\n"
    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": "READY" if not blockers else "BLOCKED",
        "profile_mode": profile_mode,
        "context_pack": context_pack,
        "style_sources": source_refs(include_profile_source),
        "candidate_style_requirements_present": block.startswith(HEADER),
        "block": block,
        "blockers": blockers,
        "warnings": warnings,
    }


def prompt_paths(chapter: str, provider: str) -> tuple[Path, Path]:
    if provider == "Codex":
        run_dir = ROOT / "external_runs" / "codex" / chapter
        return run_dir / "draft.prompt.md", run_dir / "draft.prompt.manifest.json"
    if provider == "DeepSeek":
        run_dir = ROOT / "external_runs" / "deepseek" / chapter
        return run_dir / "generate.prompt.md", run_dir / "generate.prompt.manifest.json"
    raise ValueError(f"unsupported provider: {provider}")


def top_level_requirements_present(prompt_text: str) -> bool:
    stripped = prompt_text.lstrip()
    return stripped.startswith(HEADER + "\n") or stripped.strip() == HEADER


def build_prompt_manifest(
    *,
    chapter: str,
    provider: str,
    prompt_path: Path,
    prompt_text: str,
    style_result: dict[str, Any],
    candidate_written: bool = False,
    candidate_path: Path | None = None,
) -> dict[str, Any]:
    prompt_ref = file_ref(prompt_path, "prompt")
    prompt_ref["sha256"] = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    candidate_ref = file_ref(candidate_path, "candidate_draft") if candidate_path is not None else None
    return {
        "schema_version": 1,
        "chapter": chapter,
        "status": style_result.get("status", "BLOCKED"),
        "generated_at": now_iso(),
        "provider": provider,
        "prompt_path": rel(prompt_path),
        "prompt_sha256": prompt_ref["sha256"],
        "context_pack": style_result.get("context_pack", {}),
        "style_sources": style_result.get("style_sources", []),
        "candidate_style_requirements_present": top_level_requirements_present(prompt_text),
        "profile_mode": style_result.get("profile_mode", ""),
        "candidate_written": candidate_written,
        "candidate_path": candidate_ref,
        "blockers": style_result.get("blockers", []),
        "warnings": style_result.get("warnings", []),
    }


def write_prompt_manifest(path: Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)


def validate_prompt_manifest(chapter: str, provider: str, *, require_candidate_written: bool = False) -> list[str]:
    prompt_path, manifest_path = prompt_paths(chapter, provider)
    label = f"{provider} candidate prompt evidence"
    if not manifest_path.exists():
        return [f"{chapter}: missing {label} manifest {rel(manifest_path)}"]
    data = read_json(manifest_path, {})
    failures: list[str] = []
    if not isinstance(data, dict):
        return [f"{chapter}: malformed {label} manifest {rel(manifest_path)}"]
    if data.get("chapter") != chapter:
        failures.append(f"{chapter}: {label} manifest chapter mismatch")
    if data.get("provider") != provider:
        failures.append(f"{chapter}: {label} manifest provider mismatch")
    if data.get("status") != "READY":
        failures.append(f"{chapter}: {label} status is {data.get('status', 'MISSING')}")
    if data.get("candidate_style_requirements_present") is not True:
        failures.append(f"{chapter}: {label} manifest does not confirm Candidate Style Requirements")
    if not prompt_path.exists():
        failures.append(f"{chapter}: missing {label} prompt {rel(prompt_path)}")
    else:
        prompt_text = read_text(prompt_path)
        if not top_level_requirements_present(prompt_text):
            failures.append(f"{chapter}: {label} prompt missing top-level Candidate Style Requirements")
        if data.get("prompt_path") != rel(prompt_path):
            failures.append(f"{chapter}: {label} prompt path mismatch")
        if data.get("prompt_sha256") != sha256(prompt_path):
            failures.append(f"{chapter}: {label} prompt hash mismatch")

    context = data.get("context_pack")
    if not isinstance(context, dict):
        failures.append(f"{chapter}: {label} context_pack ref is malformed")
    else:
        context_rel = str(context.get("path", "")).strip()
        context_sha = str(context.get("sha256", "")).strip()
        context_path = ROOT / context_rel
        expected_rel = f"state/context_pack/{chapter}.md"
        if context_rel != expected_rel:
            failures.append(f"{chapter}: {label} context_pack path mismatch")
        elif not context_path.exists():
            failures.append(f"{chapter}: {label} context_pack missing on disk")
        elif context_sha != sha256(context_path):
            failures.append(f"{chapter}: {label} context_pack hash is stale")

    sources = data.get("style_sources")
    if not isinstance(sources, list) or not sources:
        failures.append(f"{chapter}: {label} has no style_sources")
    else:
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                failures.append(f"{chapter}: {label} style_sources[{index}] is malformed")
                continue
            source_rel = str(item.get("path", "")).strip()
            expected_sha = str(item.get("sha256", "")).strip()
            if not source_rel or not expected_sha:
                failures.append(f"{chapter}: {label} style source missing path/sha256")
                continue
            source_path = ROOT / source_rel
            if not source_path.exists():
                failures.append(f"{chapter}: {label} style source missing on disk {source_rel}")
            elif sha256(source_path) != expected_sha and item.get("role") not in PROMPT_RECORDED_BUT_POST_CHAPTER_MUTABLE_ROLES:
                failures.append(f"{chapter}: {label} style source hash is stale for {source_rel}")

    if require_candidate_written and data.get("candidate_written") is not True:
        failures.append(f"{chapter}: {label} must confirm candidate_written")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the shared candidate chapter style requirements block.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = render_requirements(args.chapter)
    if args.json:
        payload = {key: value for key, value in result.items() if key != "block"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result["block"], end="")
    if result["status"] != "READY":
        for blocker in result.get("blockers", []):
            print(f"ERROR: {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
