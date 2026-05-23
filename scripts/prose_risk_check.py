from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_json, read_text, write_json, write_text
from review_binding import markdown_review_with_hash, sha256


CATEGORY_KEYS = (
    "subject_repetition",
    "process_bloat",
    "protagonist_invulnerable",
    "flat_side_character",
    "homogeneous_hook",
    "qa_dialogue",
    "anomaly_density",
)

SUBJECT_MARKERS = ("许临", "主角", "他", "她", "我")
PROCESS_MARKERS = (
    "电话",
    "打电话",
    "附件",
    "改附件",
    "文件",
    "记录",
    "归档",
    "审批",
    "申请",
    "回执",
    "转发",
    "提交",
    "等待",
    "通知",
    "同步",
    "表格",
    "报告",
    "流程",
    "call",
    "file",
    "record",
    "submit",
    "wait",
)
CONTRIBUTION_MARKERS = (
    "冲突",
    "威胁",
    "拒绝",
    "阻止",
    "反对",
    "发现",
    "线索",
    "证据",
    "代价",
    "后果",
    "损失",
    "关系",
    "信任",
    "背叛",
    "误会",
    "交换",
    "条件",
    "暴露",
    "决定",
    "选择",
    "risk",
    "cost",
    "threat",
    "clue",
    "choice",
)
COST_MARKERS = (
    "误判",
    "判断错",
    "弄错",
    "错过",
    "失去",
    "损失",
    "代价",
    "后果",
    "反噬",
    "受伤",
    "疼",
    "失败",
    "暴露",
    "短板",
    "弱点",
    "不得不",
    "被迫",
    "求助",
    "依赖",
    "信任风险",
    "cost",
    "wrong",
    "mistake",
    "loss",
    "forced",
)
PRESSURE_MARKERS = ("H3", "H4", "W3", "W4", "高压", "强压", "爆发", "危机", "危险", "威胁")
SIDE_CHARACTER_MARKERS = ("同事", "上司", "母亲", "父亲", "妹妹", "哥哥", "朋友", "警察", "医生", "窗口", "人员", "老师")
SIDE_AGENDA_MARKERS = ("私心", "隐瞒", "误会", "条件", "交换", "迟疑", "犹豫", "反问", "拒绝", "甩锅", "偏袒", "害怕", "嫉妒", "利益")
Q_MARKERS = ("?", "？", "吗", "呢", "为什么", "怎么", "什么", "谁", "哪")
QA_CHANGE_MARKERS = (
    "沉默",
    "反问",
    "冷笑",
    "避开",
    "没有回答",
    "打断",
    "威胁",
    "条件",
    "交换",
    "撒谎",
    "隐瞒",
    "误导",
    "退后",
    "靠近",
    "脸色",
    "权力",
    "选择",
)
ANOMALY_MARKERS = ("异常", "规则", "机制", "信号", "提示音", "新文件", "新电话", "红字", "倒计时", "裂缝", "梦", "影子", "诡异", "L2", "L3", "L4")
ANOMALY_CONSEQUENCE_MARKERS = ("后果", "代价", "反噬", "回收", "兑现", "消化", "影响", "债务", "损失")
HOOK_PATTERNS = {
    "new_phone": ("电话", "来电", "铃声", "手机"),
    "new_file": ("文件", "附件", "档案", "报告", "回执"),
    "new_anomaly": ("异常", "提示音", "红字", "信号", "倒计时"),
    "new_threat": ("威胁", "危险", "追上", "门外", "敌人"),
    "new_rule": ("规则", "禁止", "代价", "条件"),
    "relationship_shift": ("信任", "背叛", "关系", "隐瞒", "撒谎"),
    "choice": ("选择", "决定", "要么", "否则", "必须"),
    "quiet_aftermath": ("沉默", "天亮", "雨停", "空了", "没有人"),
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_path(chapter: str) -> Path:
    volume, chapter_file = chapter_parts(chapter)
    return ROOT / "chapters" / volume / chapter_file


def brief_path(chapter: str) -> Path:
    return ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"


def file_ref(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)} if path.exists() else {"path": rel(path), "sha256": ""}


def paragraphs(text: str) -> list[str]:
    values = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if values:
        return values
    return [line.strip() for line in text.splitlines() if line.strip()]


def first_quote(text: str, markers: tuple[str, ...] = ()) -> str:
    for para in paragraphs(text):
        if not markers or any(marker in para for marker in markers):
            return para.replace("\n", " ")[:160]
    return ""


def category(
    *,
    status: str,
    severity: str,
    issue: str,
    quote: str,
    action: str,
    human_acceptance_allowed: bool,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "severity": severity,
        "issue": issue,
        "evidence_quotes": [quote] if quote else [],
        "revision_actions": [action],
        "human_acceptance_allowed": human_acceptance_allowed,
        "metrics": metrics or {},
    }


def paragraph_subject(para: str, protagonist_names: list[str]) -> str:
    head = para.strip().lstrip("「“\"'（(").strip()
    for name in protagonist_names + list(SUBJECT_MARKERS):
        if name and head.startswith(name):
            return name
    match = re.match(r"^([A-Za-z][A-Za-z0-9_]{1,20})\b", head)
    return match.group(1) if match else ""


def protagonist_names() -> list[str]:
    names = ["许临"]
    path = ROOT / "bible" / "characters.yaml"
    text = read_text(path)
    match = re.search(r"id:\s*protagonist[\s\S]{0,500}name:\s*([^\n#]+)", text)
    if match:
        name = match.group(1).strip().strip("'\"")
        if name and "待定" not in name and name not in names:
            names.append(name)
    return names


def max_subject_run(paras: list[str], names: list[str]) -> tuple[int, str, str]:
    best = (0, "", "")
    current_subject = ""
    current_run: list[str] = []
    for para in paras:
        subject = paragraph_subject(para, names)
        if subject and subject == current_subject:
            current_run.append(para)
        else:
            if len(current_run) > best[0]:
                best = (len(current_run), current_subject, " / ".join(item[:80] for item in current_run))
            current_subject = subject
            current_run = [para] if subject else []
    if len(current_run) > best[0]:
        best = (len(current_run), current_subject, " / ".join(item[:80] for item in current_run))
    return best


def process_result(text: str) -> tuple[list[str], list[str]]:
    process = [para for para in paragraphs(text) if any(marker in para for marker in PROCESS_MARKERS)]
    empty = [para for para in process if not any(marker in para for marker in CONTRIBUTION_MARKERS)]
    return process, empty


def event_types(chapter: str) -> set[str]:
    path = ROOT / "state" / "event_ledger.jsonl"
    if not path.exists():
        return set()
    values: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("chapter") == chapter:
            values.add(str(event.get("type", "")))
    return values


def ending_hook(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tail = "\n".join(lines[-8:]) if lines else text[-500:]
    scores = {
        name: sum(1 for marker in markers if marker in tail)
        for name, markers in HOOK_PATTERNS.items()
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return (best if score else "unclear", tail[:160])


def dialogue_lines(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("「", "“", '"', "'", "-", "—")) or "？”" in stripped or "？”" in stripped or "?" in stripped or "？" in stripped:
            values.append(stripped)
    return values


def max_qa_run(lines: list[str]) -> tuple[int, str]:
    longest = 0
    current: list[str] = []
    for line in lines:
        is_question = any(marker in line for marker in Q_MARKERS)
        if is_question or current:
            current.append(line)
        if len(current) >= 2:
            window_text = "\n".join(current[-4:])
            if any(marker in window_text for marker in QA_CHANGE_MARKERS):
                if len(current) > longest:
                    longest = len(current) - 1
                current = []
        if len(current) > 4:
            if len(current) > longest:
                longest = len(current)
            current = current[-1:]
        if not is_question and not current:
            current = []
    if len(current) > longest:
        longest = len(current)
    sample = " / ".join(current[:4])[:160] if current else ""
    return longest, sample


def anomaly_count(text: str) -> int:
    return sum(text.count(marker) for marker in ANOMALY_MARKERS)


def authorized_anomaly_failure(chapter: str, text: str, brief: str) -> bool:
    if re.search(r"\bL[34]\b", text) and not re.search(r"\bL[34]\b", brief):
        return True
    breaker_terms = ("破局", "解决", "破解", "救了", "扭转")
    if any(term in text for term in breaker_terms) and re.search(r"\bL[234]\b", text) and not re.search(r"\bL[234]\b", brief):
        return True
    return False


def evaluate(chapter: str) -> dict[str, Any]:
    chapter_parts(chapter)
    official = official_path(chapter)
    brief = brief_path(chapter)
    if not official.exists() or not read_text(official).strip():
        return {
            "schema_version": 1,
            "chapter": chapter,
            "generated_at": now_iso(),
            "status": "NOT_READY",
            "official_chapter": file_ref(official),
            "official_brief": file_ref(brief),
            "input_hashes": [],
            "categories": {},
            "metrics": {},
            "blockers": [f"missing non-empty official chapter: {rel(official)}"],
            "warnings": [],
            "human_acceptance": None,
        }

    text = read_text(official)
    brief_text = read_text(brief)
    paras = paragraphs(text)
    names = protagonist_names()
    events = event_types(chapter)

    categories: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []

    run_count, run_subject, run_sample = max_subject_run(paras, names)
    if run_count >= 3:
        categories["subject_repetition"] = category(
            status="WARNING",
            severity="P1",
            issue=f"连续 {run_count} 个段落以同一主语 {run_subject or 'unknown'} 起句，形成机械动作链。",
            quote=run_sample or first_quote(text),
            action="打散段首主语，改用动作、感官、物件、环境压力或他人反应承接。",
            human_acceptance_allowed=True,
            metrics={"max_subject_run": run_count, "subject": run_subject},
        )
    elif run_count == 2:
        categories["subject_repetition"] = category(
            status="WARNING",
            severity="P2",
            issue="段首主语开始重复，需确认是否用于动作压迫或视角强调。",
            quote=run_sample or first_quote(text),
            action="检查相邻段落是否可以用省略、环境反应或宾语前置替换。",
            human_acceptance_allowed=True,
            metrics={"max_subject_run": run_count, "subject": run_subject},
        )
    else:
        categories["subject_repetition"] = category(
            status="CLEAR",
            severity="P3",
            issue="未发现连续机械段首主语。",
            quote=first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"max_subject_run": run_count},
        )

    process, empty_process = process_result(text)
    if len(empty_process) >= 2:
        categories["process_bloat"] = category(
            status="WARNING",
            severity="P1",
            issue="连续流程动作没有明确承担冲突、信息差、人物变化或代价。",
            quote=empty_process[0][:160],
            action="删减或重写流程段，让每个电话、附件、记录、等待改变局面。",
            human_acceptance_allowed=True,
            metrics={"process_paragraphs": len(process), "empty_process_paragraphs": len(empty_process)},
        )
    elif process:
        categories["process_bloat"] = category(
            status="WARNING",
            severity="P2",
            issue="存在流程动作，需确认每段都服务冲突、信息、人物或后果。",
            quote=process[0][:160],
            action="给流程段补即时阻力、关系变化、线索转向或代价。",
            human_acceptance_allowed=True,
            metrics={"process_paragraphs": len(process), "empty_process_paragraphs": len(empty_process)},
        )
    else:
        categories["process_bloat"] = category(
            status="CLEAR",
            severity="P3",
            issue="未发现流程注水信号。",
            quote=first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"process_paragraphs": 0},
        )

    has_cost_text = any(marker in text for marker in COST_MARKERS)
    has_cost_event = bool(events & {"character_decision", "character_state_change", "relationship_change", "object_change"})
    brief_pressure = any(marker in brief_text for marker in PRESSURE_MARKERS) or any(marker in brief_text for marker in ("代价", "后果", "压力"))
    if not has_cost_text and not has_cost_event and brief_pressure:
        categories["protagonist_invulnerable"] = category(
            status="WARNING",
            severity="P1",
            issue="brief 声明压力/代价，但正文和事件账本未显示主角误判、代价、短期损失或被迫修正。",
            quote=first_quote(text),
            action="补主角边界、误判、损失、求助或后续债务，并用事件账本承接。",
            human_acceptance_allowed=True,
            metrics={"cost_text": has_cost_text, "cost_event": has_cost_event, "brief_pressure": brief_pressure},
        )
    elif not has_cost_text and not has_cost_event:
        categories["protagonist_invulnerable"] = category(
            status="WARNING",
            severity="P2",
            issue="本章未识别到主角代价、误判、短期损失、被反制或暴露短板。",
            quote=first_quote(text),
            action="若本章不是纯兑现章，补一个可见边界或下一章后果义务。",
            human_acceptance_allowed=True,
            metrics={"cost_text": has_cost_text, "cost_event": has_cost_event},
        )
    else:
        categories["protagonist_invulnerable"] = category(
            status="CLEAR",
            severity="P3",
            issue="主角存在可识别代价、选择或状态变化。",
            quote=first_quote(text, COST_MARKERS) or first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"cost_text": has_cost_text, "cost_event": has_cost_event},
        )

    has_side_character = any(marker in text for marker in SIDE_CHARACTER_MARKERS)
    has_side_agenda = any(marker in text for marker in SIDE_AGENDA_MARKERS)
    core_side_required = any(marker in brief_text for marker in ("核心配角", "配角私心", "反向行动", "交换条件", "遮掩"))
    if has_side_character and not has_side_agenda and core_side_required:
        categories["flat_side_character"] = category(
            status="WARNING",
            severity="P1",
            issue="brief 要求核心配角功能，但正文只识别到功能性配角，未见私心、误解、交换或反向行动。",
            quote=first_quote(text, SIDE_CHARACTER_MARKERS),
            action="给核心配角补与主角不完全一致的小目标或可见反作用。",
            human_acceptance_allowed=True,
            metrics={"side_character": has_side_character, "side_agenda": has_side_agenda},
        )
    elif has_side_character and not has_side_agenda:
        categories["flat_side_character"] = category(
            status="WARNING",
            severity="P2",
            issue="配角可能偏工具化；尚未识别到私心、误解、交换、迟疑或反向行动。",
            quote=first_quote(text, SIDE_CHARACTER_MARKERS),
            action="若该配角会复用，补独立动机或与主角目标的偏差。",
            human_acceptance_allowed=True,
            metrics={"side_character": has_side_character, "side_agenda": has_side_agenda},
        )
    else:
        categories["flat_side_character"] = category(
            status="CLEAR",
            severity="P3",
            issue="未发现核心配角标签化硬风险。",
            quote=first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"side_character": has_side_character, "side_agenda": has_side_agenda},
        )

    hook_type, hook_quote = ending_hook(text)
    if hook_type in {"new_phone", "new_file", "new_anomaly"}:
        categories["homogeneous_hook"] = category(
            status="WARNING",
            severity="P2",
            issue=f"章末使用 {hook_type} 型钩子；需要与近三章钩子区分，避免电话/文件/异常突现重复。",
            quote=hook_quote or first_quote(text),
            action="若前两章同类，改成代价到账、关系变化、选择逼近或安静余波。",
            human_acceptance_allowed=True,
            metrics={"hook_type": hook_type},
        )
    else:
        categories["homogeneous_hook"] = category(
            status="CLEAR",
            severity="P3",
            issue="单章章末钩子未显示常见同质尾声。",
            quote=hook_quote or first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"hook_type": hook_type},
        )

    dlines = dialogue_lines(text)
    qa_run, qa_sample = max_qa_run(dlines)
    qa_has_change = any(marker in "\n".join(dlines) for marker in QA_CHANGE_MARKERS)
    if qa_run >= 4 and not qa_has_change:
        categories["qa_dialogue"] = category(
            status="WARNING",
            severity="P1",
            issue="关键对话呈连续问答灌输，缺少遮掩、反问、交易、误导、权力或情绪变化。",
            quote=qa_sample or first_quote(text),
            action="把回答改成博弈：隐藏、反问、交换条件、误导或权力变化。",
            human_acceptance_allowed=True,
            metrics={"max_qa_run": qa_run, "dialogue_line_count": len(dlines), "qa_has_change": qa_has_change},
        )
    elif qa_run >= 3:
        categories["qa_dialogue"] = category(
            status="WARNING",
            severity="P2",
            issue="存在连续问答段，需确认不是纯信息灌输。",
            quote=qa_sample or first_quote(text),
            action="保留必要问答，但让每轮问答改变关系、权力、情绪或信息差。",
            human_acceptance_allowed=True,
            metrics={"max_qa_run": qa_run, "dialogue_line_count": len(dlines), "qa_has_change": qa_has_change},
        )
    else:
        categories["qa_dialogue"] = category(
            status="CLEAR",
            severity="P3",
            issue="未发现连续 Q&A 化对话。",
            quote=first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"max_qa_run": qa_run, "dialogue_line_count": len(dlines)},
        )

    a_count = anomaly_count(text)
    unauthorized = authorized_anomaly_failure(chapter, text, brief_text)
    has_anomaly_consequence = any(marker in text for marker in ANOMALY_CONSEQUENCE_MARKERS)
    if unauthorized:
        categories["anomaly_density"] = category(
            status="BLOCKED",
            severity="P0",
            issue="正文出现未被 brief 授权的 L2-L4 异常/机制破局风险。",
            quote=first_quote(text, ("L2", "L3", "L4", "异常", "规则")) or first_quote(text),
            action="删除未授权破局，或回到 brief/设定裁决流程授权后重写。",
            human_acceptance_allowed=False,
            metrics={"anomaly_marker_count": a_count, "unauthorized_breaker": True},
        )
    elif a_count >= 8 and not has_anomaly_consequence:
        categories["anomaly_density"] = category(
            status="WARNING",
            severity="P1",
            issue="异常/规则/信号密度高，但缺少后果、代价、回收或消化段。",
            quote=first_quote(text, ANOMALY_MARKERS),
            action="减少新增异常，优先写旧异常后果或把异常转化为人物选择代价。",
            human_acceptance_allowed=True,
            metrics={"anomaly_marker_count": a_count, "has_consequence": has_anomaly_consequence},
        )
    elif a_count >= 4:
        categories["anomaly_density"] = category(
            status="WARNING",
            severity="P2",
            issue="异常/规则/信号密度偏高，需确认均来自授权并有消化。",
            quote=first_quote(text, ANOMALY_MARKERS),
            action="检查新增异常是否必要，优先保留有后果和回收功能的异常。",
            human_acceptance_allowed=True,
            metrics={"anomaly_marker_count": a_count, "has_consequence": has_anomaly_consequence},
        )
    else:
        categories["anomaly_density"] = category(
            status="CLEAR",
            severity="P3",
            issue="异常密度未超出单章预警阈值。",
            quote=first_quote(text),
            action="none",
            human_acceptance_allowed=False,
            metrics={"anomaly_marker_count": a_count},
        )

    for key, item in categories.items():
        if item["status"] == "BLOCKED":
            blockers.append(f"{key}: {item['issue']}")
        elif item["status"] == "WARNING":
            warnings.append(f"{key}: {item['issue']}")

    status = "BLOCKED" if blockers else "WARNING" if warnings else "CLEAR"
    input_hashes = [file_ref(official), file_ref(brief)]
    for extra in (
        ROOT / "reviews" / chapter / "dialogue_function.json",
        ROOT / "reviews" / chapter / "chapter_shape.json",
    ):
        if extra.exists():
            input_hashes.append(file_ref(extra))

    return {
        "schema_version": 1,
        "chapter": chapter,
        "generated_at": now_iso(),
        "status": status,
        "official_chapter": file_ref(official),
        "official_brief": file_ref(brief),
        "input_hashes": input_hashes,
        "categories": categories,
        "metrics": {
            "paragraph_count": len(paras),
            "dialogue_line_count": len(dlines),
            "event_types": sorted(events),
            "ending_hook_type": hook_type,
        },
        "blockers": blockers,
        "warnings": warnings,
        "human_acceptance": None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Prose Risk Review: {report['chapter']}",
        "",
        f"status: {report['status']}",
        f"official_chapter_sha256: {report.get('official_chapter', {}).get('sha256', '')}",
        "review_sha256:",
        "",
        "## Scope",
        "",
        "Checks seven recurring prose risks: subject repetition, process bloat, invulnerable protagonist, flat side characters, homogeneous hooks, Q&A dialogue, and anomaly density.",
        "",
        "## Findings",
        "",
        "| severity | category | status | evidence_quote | issue | action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in CATEGORY_KEYS:
        item = (report.get("categories") or {}).get(name, {})
        quote = (item.get("evidence_quotes") or [""])[0]
        action = "; ".join(item.get("revision_actions") or [])
        lines.append(f"| {item.get('severity', '')} | {name} | {item.get('status', '')} | {quote} | {item.get('issue', '')} | {action} |")
    lines.extend(["", "## Evidence Quotes", ""])
    used: list[str] = []
    for item in (report.get("categories") or {}).values():
        for quote in item.get("evidence_quotes") or []:
            if quote and quote not in used:
                used.append(quote)
                lines.append(f"- {quote}")
    if not used:
        lines.append("- none")
    for key, title in (("blockers", "Blockers"), ("warnings", "Warnings")):
        lines.extend(["", f"## {title}", ""])
        values = report.get(key) or []
        lines.extend(f"- {value}" for value in values) if values else lines.append("- none")
    lines.extend(["", "## Required Outcome", "", "`CLEAR` / `WARNING` / `BLOCKED` / `ACCEPTED_BY_HUMAN`"])
    return markdown_review_with_hash("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check one official chapter for seven prose-risk patterns.")
    parser.add_argument("chapter")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.chapter)
    if args.write and not args.no_write:
        out_dir = ROOT / "reviews" / args.chapter
        write_json(out_dir / "prose_risk.json", report)
        write_text(out_dir / "prose_risk.md", render_markdown(report))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Prose Risk: {args.chapter}")
        print(f"status: {report['status']}")
        for item in report.get("blockers", []):
            print(f"- {item}")
        for item in report.get("warnings", []):
            print(f"- WARNING: {item}")
    return 1 if report["status"] in {"BLOCKED", "NOT_READY"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
