from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import ROOT, now_iso, read_text, write_text
from core_setting_freeze import FREEZE_JSON, FREEZE_MD, REQUIRED_FIELDS, sha256


IDEA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
CHOICES = ["A", "B", "C", "Mixed"]
REQUIRED_INPUTS = [
    "original_idea.md",
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "agent_review_manifest.json",
    "codex_synthesis.md",
]
PLACEHOLDER_MARKERS = ("待定", "待填", "待评", "待生成", "TODO", "{idea_id}")
AGENT_OUTPUTS = [
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "codex_synthesis.md",
]
AGENT_REVIEW_MANIFEST = "agent_review_manifest.json"
AGENT_ROLES = {
    "product_founder": "product_founder_review.md",
    "technical_lead": "technical_lead_review.md",
    "qa_release": "qa_release_review.md",
}
REQUIRED_DIRECTION_FIELDS = [
    "一句话卖点",
    "主角欲望",
    "核心冲突",
    "世界异常",
    *REQUIRED_FIELDS.values(),
    "前三章验证点",
    "最大风险",
    "适合继续的信号",
    "不适合继续的信号",
]


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def has_placeholder(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return ""


def direction_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s*Direction\s+([ABC])\b.*$", text, flags=re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def validate_codex_synthesis(text: str) -> list[str]:
    errors: list[str] = []
    sections = direction_sections(text)
    for direction in ("A", "B", "C"):
        section = sections.get(direction)
        if section is None:
            errors.append(f"codex_synthesis.md missing Direction {direction}")
            continue
        for field in REQUIRED_DIRECTION_FIELDS:
            if field not in section:
                errors.append(f"codex_synthesis.md Direction {direction} missing field {field}")
    return errors


def field_value(section: str, field: str) -> str:
    lines = section.splitlines()
    collected: list[str] = []
    in_field = False
    for line in lines:
        stripped = line.strip()
        match = re.match(rf"^(?:[-*]\s*)?{re.escape(field)}\s*[：:]\s*(.*)$", stripped)
        if match:
            collected = [match.group(1).strip()]
            in_field = True
            continue
        if in_field:
            if re.match(r"^[-*]\s*\S+?[：:]", stripped) or stripped.startswith("## "):
                break
            if stripped:
                collected.append(stripped)
    return "\n".join(item for item in collected if item).strip()


def freeze_source_for_choice(args: argparse.Namespace, contents: dict[str, str]) -> str:
    if args.choice == "Mixed":
        return args.mixed_strategy
    section = direction_sections(contents["codex_synthesis.md"]).get(args.choice, "")
    return section


def core_fields(args: argparse.Namespace, contents: dict[str, str]) -> dict[str, str]:
    source = freeze_source_for_choice(args, contents)
    return {key: field_value(source, label) for key, label in REQUIRED_FIELDS.items()}


def validate_core_fields(fields: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key, label in REQUIRED_FIELDS.items():
        value = fields.get(key, "").strip()
        if not value or has_placeholder(value):
            errors.append(f"core setting freeze missing field {key} ({label})")
    return errors


def evidence_item(path: Path) -> dict:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "mtime": path.stat().st_mtime,
    }


def evidence_text_item(path: Path, text: str) -> dict:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def parse_iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_manifest_hash(path: Path, expected: object, label: str) -> list[str]:
    if not isinstance(expected, str) or not expected.strip():
        return [f"{label} missing sha256"]
    if not path.exists() or not path.is_file():
        return [f"{label} missing file: {path.relative_to(ROOT)}"]
    if sha256(path) != expected:
        return [f"{label} hash mismatch: {path.relative_to(ROOT)}"]
    return []


def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_agent_run(idea_id: str, lab: Path, role: str, filename: str, item: dict) -> list[str]:
    run = item.get("agent_run")
    if not isinstance(run, dict):
        return [f"agent_review_manifest.json {role} missing agent_run"]
    errors: list[str] = []
    if run.get("role") != role:
        errors.append(f"agent_review_manifest.json {role} agent_run role mismatch")
    if run.get("agent_id") != item.get("agent_id"):
        errors.append(f"agent_review_manifest.json {role} agent_run agent_id mismatch")
    if not parse_iso_datetime(run.get("completed_at")):
        errors.append(f"agent_review_manifest.json {role} agent_run missing valid completed_at")
    if run.get("runner_type") not in {"codex_subagent", "external_agent"}:
        errors.append(f"agent_review_manifest.json {role} agent_run missing valid runner_type")
    if not str(run.get("runner_id", "")).strip():
        errors.append(f"agent_review_manifest.json {role} agent_run missing runner_id")
    if not str(run.get("isolation_attestation", "")).strip():
        errors.append(f"agent_review_manifest.json {role} agent_run missing isolation_attestation")

    expected_inputs = {
        (lab / "original_idea.md").relative_to(ROOT).as_posix(): lab / "original_idea.md",
        (lab / "deepseek_idea.md").relative_to(ROOT).as_posix(): lab / "deepseek_idea.md",
    }
    input_files = run.get("input_files")
    if not isinstance(input_files, list):
        errors.append(f"agent_review_manifest.json {role} agent_run input_files must be a list")
        input_files = []
    input_by_path = {
        str(input_item.get("path")): input_item
        for input_item in input_files
        if isinstance(input_item, dict)
    }
    extra = sorted(set(input_by_path) - set(expected_inputs))
    if extra:
        errors.append(f"agent_review_manifest.json {role} agent_run has disallowed inputs: {', '.join(extra)}")
    for rel_path, path in expected_inputs.items():
        input_item = input_by_path.get(rel_path)
        if not input_item:
            errors.append(f"agent_review_manifest.json {role} agent_run missing input {rel_path}")
            continue
        errors.extend(validate_manifest_hash(path, input_item.get("sha256"), f"{role} agent_run input {rel_path}"))
    allowed_inputs = run.get("allowed_inputs")
    if not isinstance(allowed_inputs, list):
        errors.append(f"agent_review_manifest.json {role} agent_run allowed_inputs must be a list")
        allowed_inputs = []
    if allowed_inputs != input_files:
        errors.append(f"agent_review_manifest.json {role} agent_run allowed_inputs must match input_files")
    allowed_hash = run.get("allowed_inputs_sha256")
    if not isinstance(allowed_hash, str) or not allowed_hash.strip():
        errors.append(f"agent_review_manifest.json {role} agent_run missing allowed_inputs_sha256")
    elif allowed_hash != stable_hash(allowed_inputs):
        errors.append(f"agent_review_manifest.json {role} agent_run allowed_inputs_sha256 mismatch")

    output = run.get("output_file")
    expected_output = lab / filename
    expected_output_rel = expected_output.relative_to(ROOT).as_posix()
    if not isinstance(output, dict):
        errors.append(f"agent_review_manifest.json {role} agent_run missing output_file")
    else:
        if output.get("path") != expected_output_rel:
            errors.append(f"agent_review_manifest.json {role} agent_run output_file path must be {expected_output_rel}")
        errors.extend(validate_manifest_hash(expected_output, output.get("sha256"), f"{role} agent_run output"))
    transcript = run.get("transcript_file")
    if not isinstance(transcript, dict):
        errors.append(f"agent_review_manifest.json {role} agent_run missing transcript_file")
    else:
        transcript_path = ROOT / str(transcript.get("path", ""))
        errors.extend(validate_manifest_hash(transcript_path, transcript.get("sha256"), f"{role} agent_run transcript"))
        if transcript.get("sha256") != run.get("transcript_sha256"):
            errors.append(f"agent_review_manifest.json {role} agent_run transcript_sha256 mismatch")
    return errors


def validate_agent_review_manifest(idea_id: str, lab: Path) -> list[str]:
    path = lab / AGENT_REVIEW_MANIFEST
    if not path.exists():
        return [f"missing idea-lab input: {path.relative_to(ROOT)}"]
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return [f"agent_review_manifest.json is invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["agent_review_manifest.json must be a JSON object"]

    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("agent_review_manifest.json schema_version must be 1")
    if data.get("idea_id") != idea_id:
        errors.append("agent_review_manifest.json idea_id mismatch")
    if not parse_iso_datetime(data.get("recorded_at")):
        errors.append("agent_review_manifest.json missing valid recorded_at")

    input_paths = {
        str(item.get("path")): item
        for item in data.get("inputs", [])
        if isinstance(item, dict)
    }
    for filename in ("original_idea.md", "deepseek_idea.md"):
        rel_path = (lab / filename).relative_to(ROOT).as_posix()
        item = input_paths.get(rel_path)
        if not item:
            errors.append(f"agent_review_manifest.json missing input {rel_path}")
            continue
        errors.extend(validate_manifest_hash(lab / filename, item.get("sha256"), f"agent manifest input {filename}"))

    reviews = data.get("reviews")
    if not isinstance(reviews, dict):
        errors.append("agent_review_manifest.json missing reviews mapping")
        reviews = {}
    for role, filename in AGENT_ROLES.items():
        item = reviews.get(role)
        if not isinstance(item, dict):
            errors.append(f"agent_review_manifest.json missing review role {role}")
            continue
        if item.get("role", role) != role:
            errors.append(f"agent_review_manifest.json role mismatch for {role}")
        if not str(item.get("agent_id", "")).strip():
            errors.append(f"agent_review_manifest.json {role} missing agent_id")
        expected_path = (lab / filename).relative_to(ROOT).as_posix()
        if item.get("path") != expected_path:
            errors.append(f"agent_review_manifest.json {role} path must be {expected_path}")
        if not parse_iso_datetime(item.get("completed_at")):
            errors.append(f"agent_review_manifest.json {role} missing valid completed_at")
        errors.extend(validate_manifest_hash(lab / filename, item.get("sha256"), f"{role} review"))
        errors.extend(validate_agent_run(idea_id, lab, role, filename, item))
    return errors


def build_core_freeze(
    idea_id: str,
    lab: Path,
    args: argparse.Namespace,
    contents: dict[str, str],
    selection_text: str,
) -> dict:
    raw = ROOT / "external_runs" / "deepseek" / idea_id / "idea.raw.json"
    if not raw.exists():
        raise FileNotFoundError(f"missing DeepSeek raw evidence: {raw.relative_to(ROOT)}")
    selection_path = lab / "selection.json"
    fields = core_fields(args, contents)
    field_errors = validate_core_fields(fields)
    if field_errors:
        raise ValueError("; ".join(field_errors))

    return {
        "idea_id": idea_id,
        "status": "LOCKED",
        "locked_at": now_iso(),
        "selected_direction": args.choice,
        "human_approved": True,
        "verified_by": "human",
        "fields": fields,
        "evidence": {
            "original_idea": evidence_item(lab / "original_idea.md"),
            "deepseek_idea": evidence_item(lab / "deepseek_idea.md"),
            "deepseek_raw": evidence_item(raw),
            "product_founder_review": evidence_item(lab / "product_founder_review.md"),
            "technical_lead_review": evidence_item(lab / "technical_lead_review.md"),
            "qa_release_review": evidence_item(lab / "qa_release_review.md"),
            "agent_review_manifest": evidence_item(lab / AGENT_REVIEW_MANIFEST),
            "codex_synthesis": evidence_item(lab / "codex_synthesis.md"),
            "selection": evidence_text_item(selection_path, selection_text),
        },
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }


def build_core_freeze_md(idea_id: str, data: dict) -> str:
    fields = data["fields"]
    lines = [
        f"# Core Setting Freeze: {idea_id}",
        "",
        f"status: {data['status']}",
        f"selected_direction: {data['selected_direction']}",
        "human_approved: true",
        "",
        "本文件是开书前定盘证据，不是 canon。正文出现并由人类确认后，事实才可进入 bible/canon.md。",
        "",
    ]
    for key, label in REQUIRED_FIELDS.items():
        lines.extend([f"## {label}", "", fields[key], ""])
    return "\n".join(lines).rstrip() + "\n"


def validate_output_freshness(lab: Path) -> list[str]:
    input_mtime = max((lab / "original_idea.md").stat().st_mtime, (lab / "deepseek_idea.md").stat().st_mtime)
    errors: list[str] = []
    for name in AGENT_OUTPUTS:
        path = lab / name
        if path.stat().st_mtime + 0.001 < input_mtime:
            errors.append(f"idea-lab input {path.relative_to(ROOT)} is older than idea inputs")
    return errors


def validate_ready_contents(idea_id: str, lab: Path, contents: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for name in AGENT_OUTPUTS:
        heading = first_heading(contents[name])
        if idea_id not in heading:
            errors.append(f"idea-lab input {lab.joinpath(name).relative_to(ROOT)} heading must include {idea_id}")
    errors.extend(validate_codex_synthesis(contents["codex_synthesis.md"]))
    errors.extend(validate_agent_review_manifest(idea_id, lab))
    errors.extend(validate_output_freshness(lab))
    return errors


def require_ready_lab(idea_id: str) -> tuple[Path, dict[str, str]]:
    lab = ROOT / "state" / "idea_lab" / idea_id
    if not lab.exists():
        raise FileNotFoundError(f"missing idea lab: {lab.relative_to(ROOT)}")
    contents: dict[str, str] = {}
    for name in REQUIRED_INPUTS:
        path = lab / name
        if not path.exists():
            raise FileNotFoundError(f"missing idea-lab input: {path.relative_to(ROOT)}")
        text = read_text(path)
        if not text.strip():
            raise ValueError(f"idea-lab input is empty: {path.relative_to(ROOT)}")
        if name != "original_idea.md" and has_placeholder(text):
            raise ValueError(f"idea-lab input still has placeholders: {path.relative_to(ROOT)}")
        contents[name] = text
    errors = validate_ready_contents(idea_id, lab, contents)
    if errors:
        raise ValueError("; ".join(errors))
    return lab, contents


def build_premise(idea_id: str, args: argparse.Namespace, contents: dict[str, str]) -> str:
    fields = core_fields(args, contents)
    source = freeze_source_for_choice(args, contents)
    hook = field_value(source, "一句话卖点") or f"见 {args.choice} 方向开书实验；由前三章 brief 继续收束。"
    protagonist = field_value(source, "主角欲望") or "主角具体身份由第一章 brief 固定；欲望边界遵守核心设定冻结。"
    anomaly = field_value(source, "世界异常") or fields["worldview_core"]
    conflict = field_value(source, "核心冲突") or "核心冲突由冻结规则、硬边界与主角异常原因共同限定。"
    validation = field_value(source, "前三章验证点") or fields["first_three_chapter_constraints"]
    return f"""# Premise

idea_lab_id: {idea_id}
selected_direction: {args.choice}
selected_at: {now_iso()}

## 一句话卖点

{hook}

## 主角

{protagonist}

## 主角想要什么

{field_value(source, "主角欲望") or "由第一章 brief 转化为章内可行动、可失败的目标。"}

## 世界最大异常

{anomaly}

## 核心冲突

{conflict}

## 前三章验证目标

{validation}

## 开书前核心设定冻结

以下内容来自 DeepSeek 开书实验、三类 agent 审查与 Codex synthesis，经人类选择方向后锁定。它们是前三章试点的硬边界，不直接写入 canon。

- 世界观核心规则：{fields["worldview_core"]}
- 世界观硬边界：{fields["worldview_hard_limits"]}
- 主角异常原因：{fields["protagonist_anomaly_cause"]}
- 主角家属/亲密关系：{fields["protagonist_family"]}
- 家属剧情功能与风险：{fields["family_stakes"]}
- 前三章约束：{fields["first_three_chapter_constraints"]}
- 不可违背红线：{fields["forbidden_changes"]}
- 仍可开放的问题：{fields["open_questions_allowed"]}

## 选择理由

{args.reason or "待人类补充。"}

## Mixed Strategy

{args.mixed_strategy or "无。"}

## Codex Synthesis 摘要

{contents["codex_synthesis.md"].strip()}
"""


def build_rules_seed(idea_id: str, args: argparse.Namespace, fields: dict[str, str]) -> str:
    return f"""# Rules

idea_lab_id: {idea_id}
selected_direction: {args.choice}
source: core_setting_freeze

本文件是从开书前核心设定冻结同步的最小可写规则种子，不是 canon。正文出现并由人类确认后，事实才可进入 `bible/canon.md`。

## 核心异常 / 能力 / 技术是什么？

{fields["protagonist_anomaly_cause"]}

## 能做什么？

只能展示与以下世界观核心规则一致的异常、能力、技术或制度压力：{fields["worldview_core"]}

## 不能做什么？

{fields["worldview_hard_limits"]}

## 代价是什么？

{fields["family_stakes"]}

## 限制是什么？

{fields["first_three_chapter_constraints"]}

## 禁止临时新增什么万能规则？

{fields["forbidden_changes"]}

## 仍可开放的问题

{fields["open_questions_allowed"]}
"""


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_characters_seed(idea_id: str, args: argparse.Namespace, fields: dict[str, str]) -> str:
    return f"""characters:
  - id: protagonist
    name: {yaml_quote("主角")}
    role: protagonist
    idea_lab_id: {yaml_quote(idea_id)}
    selected_direction: {yaml_quote(args.choice)}
    anomaly_cause: {yaml_quote(fields["protagonist_anomaly_cause"])}
    current_state: {yaml_quote("前三章试点期由章节 brief 和正文证据逐步确认。")}
    relationships:
      - family_anchor
    forbidden_changes:
      - {yaml_quote(fields["forbidden_changes"])}
      - {yaml_quote("AI 不得自动决定主角命运；必须由人类总编裁决。")}
  - id: family_anchor
    name: {yaml_quote("主角家属/亲密关系")}
    role: family_or_intimate_anchor
    idea_lab_id: {yaml_quote(idea_id)}
    relationship_to_protagonist: {yaml_quote(fields["protagonist_family"])}
    story_function_and_risk: {yaml_quote(fields["family_stakes"])}
    current_state: {yaml_quote("作为前三章试点的情感与风险锚点；具体出场由 brief 授权。")}
    forbidden_changes:
      - {yaml_quote("不得在正文证据和人类裁决前决定其最终命运。")}
"""


def build_open_questions(idea_id: str, args: argparse.Namespace, contents: dict[str, str]) -> str:
    return f"""# Open Questions

idea_lab_id: {idea_id}
selected_direction: {args.choice}

本文件保存开书实验室产物和待裁决问题。以下内容不得直接视为 canon。

## 原始想法

{contents["original_idea.md"].strip()}

## DeepSeek 外部发散

{contents["deepseek_idea.md"].strip()}

## 多 Agent 审查

### Product Founder

{contents["product_founder_review.md"].strip()}

### Technical Lead

{contents["technical_lead_review.md"].strip()}

### QA Release

{contents["qa_release_review.md"].strip()}

## 人类总编选择

- choice: {args.choice}
- reason: {args.reason or "待人类补充。"}
- mixed_strategy: {args.mixed_strategy or "无。"}
- notes: {args.notes or "无。"}

## 后续必须确认

- 第一章开篇吸引点是否明确。
- 冻结设定在正文中如何展示，必须等章节 brief 决定。
- 哪些已冻结事实可以进入 canon，必须等正文出现并由人类确认后再提议。
- 非核心支线、完整势力谱系、终局细节、地图年表和数值规则仍可开放。
"""


def build_gate_a(idea_id: str, args: argparse.Namespace) -> str:
    return f"""# Gate A: 3 Chapters

idea_lab_id: {idea_id}
selected_direction: {args.choice}

Gate A 只判断是否继续到第 4 章，不判断 300 万字可行性。

## 必须回答

- 是否愿意写第 4 章？
- 流程是否让写作更轻？
- 主角目标是否成立？
- 核心卖点是否一句话说清？
- 3 章里是否至少 2 章让人想看下一章？
- 世界观是否展示压力而不是百科？
- 是否出现设定膨胀或漂移？
- Codex / DeepSeek 哪个更适合主写？

## 继续信号

待人类根据前三章和读者测试确认。

## 停止或重做信号

待人类根据前三章和读者测试确认。
"""


def build_c001_brief(idea_id: str, args: argparse.Namespace) -> str:
    return f"""# v01_c001 Brief

idea_lab_id: {idea_id}
selected_direction: {args.choice}

## 本章功能

待定：请人类总编确认第一章在三章试点中的功能。

## 开篇吸引点

待定：从开书实验方向中选择一个可立即进入冲突的场面。

## 主角目标

待定：必须是本章内可行动、可失败的目标。

## 主要阻力

待定。

## 主角主动选择

待定：本章必须有主角主动选择，不能只被事件推着走。

## 上章章末锚点

TODO：首章写“开篇章，无上章”；非首章按 时间 / 地点 / 在场人物 / 主角状态 / 携带物 / 证据 / 未完成动作 列出上一章章末可见状态。

## 本章开场落点

TODO：按 时间 / 地点 / 在场人物 / 主角状态 / 第一动作 列出本章第一场可见状态。

## 场景承接说明

- 类型：TODO：原地承接 / 明示跳切 / 省略过桥 / 开篇起始
- 说明：TODO：若地点、时间或状态改变，写清过桥原因和动作。

## 主线牵引档位

TODO：写 S0-S4，并说明第一章如何留下主线牵引；不得只写档位。

## 外部压力档位

TODO：写 W0-W4，并说明外部世界、制度、势力、资源或关系如何压到主角身上。

## 本章继承变化

TODO：第一章写开篇初始状态和本章必须建立的变化；不能写 none。

## 本章节奏用途

TODO：推进 / 缓冲 / 兑现 / 铺垫 / 转场 / 蓄压 / 爆发，可选 1-2 个。

## 节奏说明

TODO：说明为什么第一章不会空转，也不会为了过检强行加速。

## 本章进展契约

- 进展类型：TODO：setup / reveal / decision / thread_advance / payoff / digest / cost_payment / transition
- 推进对象：TODO：写 thread_id / entity_id / 主线核心问题。
- 起始状态依据：TODO：写开篇初始状态、open thread 或上一事件 id。
- 结束状态变化：TODO：写第一章结束时不可忽略的状态变化。
- 最低落账事件：TODO：character_decision / character_state_change / relationship_change / world_fact / rule_reveal / thread_opened / thread_advanced / thread_paid_off / location_change / object_change
- 进展重要度：TODO：P0/P1/P2/P3
- 低牵引功能：TODO：若第一章低牵引，写消化、蓄压、关系转向、信息校准或转场功能；否则写本章主要功能。

## 本章代价与后果契约

- 推进重量：TODO：C0/C1/C2/C3/C4
- 后果等级：TODO：reversible / scar / structure_change
- 代价类型：TODO：physical / emotional / relationship / resource / reputation / time / rule_debt
- 已支付代价：TODO：写清谁在第一章付出了什么代价。
- 延后代价：TODO：写清后续会追讨什么代价；没有则说明为什么没有。
- 后果承接义务：TODO：写下一章或三章内必须承接的后果。
- 消化窗口：TODO：写本章 / 下一章 / 2章内 / 3章内。
- 冷却范围：TODO：写哪条主线、伏笔或能力短期内不能继续猛解。

## 本章解决边界

- 新开伏笔：TODO：列出本章新开的 thread；没有则写 none。
- 推进伏笔：TODO：列出本章推进的 thread；没有则写 none。
- 解决伏笔：TODO：列出本章解决的 thread；没有则写 none。
- 禁止解决：TODO：列出本章不能解决的主谜题、核心规则或长期伏笔。
- 解决是否需要代价：TODO：是 / 否；若解决伏笔非空必须为“是”。

## 本章推进

待定。

## 信息增量

待定：只展示前三章够用的信息。

## 章末问题

待定。

## 本章使用设定

待定。

## 本章可用人物状态

待定。

## 本章可用道具 / 装备

待定。

## 本章可用道具 IDs

TODO：只列 `bible/objects.yaml` 中本章允许使用的 id；没有则写 none。

## 本章可用技能 / 能力

待定。

## 本章可用技能 IDs

TODO：只列 `bible/abilities.yaml` 中本章允许使用的 id；没有则写 none。

## 能力限制 / 代价

待定。

## 未解决伏笔

待定。

## 新增设定

待定：新增设定必须先停留在 open_questions，不能直接进 canon。

## 本章允许新增元素

TODO：按 L0/L1/L2/L3/L4 标明本章可新增内容；没有则写 none。

## 本章禁止临场解决

TODO：列明不得靠未授权新道具、新能力或新规则解决的核心问题。

## 伏笔：新开 / 推进 / 回收

待定。

## 本章禁止新增

待定。

## 本章禁止解决

待定。

## 禁止新增 / 禁止解决 / 禁止模仿

待定：禁止把 DeepSeek 或任何参考作品内容直接换皮进正文。
"""


def build_selection_md(args: argparse.Namespace) -> str:
    return (
        "\n".join(
            [
                f"# Idea Selection: {args.id}",
                "",
                f"choice: {args.choice}",
                f"reason: {args.reason or '待人类补充。'}",
                f"mixed_strategy: {args.mixed_strategy or '无。'}",
                f"notes: {args.notes or '无。'}",
                "verified_by: human",
                "",
            ]
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Record human-selected idea direction and create pilot assets.")
    parser.add_argument("--id", required=True, type=validate_idea_id)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--reason", default="")
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    try:
        lab, contents = require_ready_lab(args.id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.choice == "Mixed" and not args.mixed_strategy.strip():
        print("ERROR: Mixed choice requires --mixed-strategy.", file=sys.stderr)
        return 1

    record = {
        "idea_id": args.id,
        "selected_at": now_iso(),
        "choice": args.choice,
        "reason": args.reason,
        "mixed_strategy": args.mixed_strategy,
        "notes": args.notes,
        "verified_by": "human",
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }
    selection_json = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    selection_md = build_selection_md(args)
    try:
        freeze = build_core_freeze(args.id, lab, args, contents, selection_json)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    freeze_json = json.dumps(freeze, ensure_ascii=False, indent=2) + "\n"
    freeze_md = build_core_freeze_md(args.id, freeze)
    selected_pointer = (
        json.dumps(
            {
                "idea_id": args.id,
                "selected_at": record["selected_at"],
                "selection_path": f"state/idea_lab/{args.id}/selection.json",
                "core_setting_freeze_path": f"state/idea_lab/{args.id}/{FREEZE_JSON}",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    fields = freeze["fields"]
    premise = build_premise(args.id, args, contents)
    rules_seed = build_rules_seed(args.id, args, fields)
    characters_seed = build_characters_seed(args.id, args, fields)
    open_questions = build_open_questions(args.id, args, contents)
    gate_a = build_gate_a(args.id, args)
    c001_brief = build_c001_brief(args.id, args)

    write_text(lab / "selection.json", selection_json)
    write_text(lab / "selection.md", selection_md)
    write_text(lab / FREEZE_JSON, freeze_json)
    write_text(lab / FREEZE_MD, freeze_md)
    write_text(ROOT / "state" / "idea_lab" / "selected.json", selected_pointer)
    write_text(ROOT / "outline" / "premise.md", premise)
    write_text(ROOT / "bible" / "rules.md", rules_seed)
    write_text(ROOT / "bible" / "characters.yaml", characters_seed)
    write_text(ROOT / "bible" / "open_questions.md", open_questions)
    write_text(ROOT / "outline" / "gate_a_3_chapters.md", gate_a)
    write_text(ROOT / "outline" / "chapter_briefs" / "v01_c001.md", c001_brief)
    print(f"OK: recorded idea selection {args.id} -> {args.choice}")
    print("next: human confirms or edits outline/chapter_briefs/v01_c001.md, then run `开章 v01_c001`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
