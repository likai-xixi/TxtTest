from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import ROOT, chapter_number, chapter_parts, read_text, write_json
from brief_contract import (
    COST_CONSEQUENCE_CONTRACT_SECTIONS,
    EXTERNAL_PRESSURE_SECTIONS,
    HIGH_IMPACT_SCALES,
    HIGH_S_LEVELS,
    HIGH_W_LEVELS,
    IMPACT_SCALES,
    INHERITED_CHANGE_SECTIONS,
    LEDGER_EVENT_TYPES,
    LOW_IMPACT_SCALES,
    LOW_S_LEVELS,
    LOW_W_LEVELS,
    MAINLINE_TRACTION_SECTIONS,
    PACING_NOTE_SECTIONS,
    PROGRESS_CONTRACT_SECTIONS,
    RESOLUTION_BOUNDARY_SECTIONS,
    REST_NOTE_KEYWORDS,
    concrete_value,
    digestion_window_chapters,
    is_none_body,
    normalized_consequence_level,
    normalized_impact_scale,
    normalized_progress_mode,
    parse_pacing_level,
    progress_value,
)
from element_context import markdown_sections, section_body


CHAPTER_RE = re.compile(r"^v\d{2}_c\d{3}$")
DIGEST_MODES = {"digest", "cost_payment"}
EFFECTIVE_PROGRESS_MODES = {"reveal", "decision", "thread_advance", "payoff", "cost_payment"}


def brief_paths(target_chapter: str | None) -> list[Path]:
    candidates = [
        path
        for path in (ROOT / "outline" / "chapter_briefs").glob("v*_c*.md")
        if CHAPTER_RE.match(path.stem)
    ]
    paths = sorted(
        candidates,
        key=lambda path: (path.stem[:3], chapter_number(path.stem)),
    )
    if target_chapter is None:
        return paths
    target_number = chapter_number(target_chapter)
    target_volume = target_chapter[:3]
    return [path for path in paths if path.stem[:3] == target_volume and chapter_number(path.stem) <= target_number]


def parse_entry(path: Path) -> dict:
    chapter = path.stem
    sections = markdown_sections(read_text(path))
    mainline_body = section_body(sections, MAINLINE_TRACTION_SECTIONS)
    external_body = section_body(sections, EXTERNAL_PRESSURE_SECTIONS)
    inherited_change = section_body(sections, INHERITED_CHANGE_SECTIONS)
    pacing_note = section_body(sections, PACING_NOTE_SECTIONS)
    progress_body = section_body(sections, PROGRESS_CONTRACT_SECTIONS)
    cost_body = section_body(sections, COST_CONSEQUENCE_CONTRACT_SECTIONS)
    boundary_body = section_body(sections, RESOLUTION_BOUNDARY_SECTIONS)
    mainline_level, mainline_explanation = parse_pacing_level(mainline_body, "S")
    external_level, external_explanation = parse_pacing_level(external_body, "W")
    progress_mode = normalized_progress_mode(progress_value(progress_body, "progress_mode"))
    impact_scale = normalized_impact_scale(progress_value(cost_body, "impact_scale"))
    consequence_level = normalized_consequence_level(progress_value(cost_body, "consequence_level"))
    end_state_delta = progress_value(progress_body, "end_state_delta")
    minimum_ledger_event = progress_value(progress_body, "minimum_ledger_event").strip()
    buffer_function = progress_value(progress_body, "buffer_function")
    aftermath_obligation = progress_value(cost_body, "aftermath_obligation")
    digestion_window = progress_value(cost_body, "digestion_window")
    resolved_threads = progress_value(boundary_body, "resolved_threads")
    errors: list[str] = []
    if mainline_level is None:
        errors.append("missing or invalid 主线牵引档位")
    if external_level is None:
        errors.append("missing or invalid 外部压力档位")
    if not progress_body:
        errors.append("missing 本章进展契约")
    if not cost_body:
        errors.append("missing 本章代价与后果契约")
    if not boundary_body:
        errors.append("missing 本章解决边界")
    if progress_body and not progress_mode:
        errors.append("missing or invalid 进展类型")
    if progress_body and not concrete_value(end_state_delta):
        errors.append("missing concrete 结束状态变化")
    if progress_body and minimum_ledger_event not in LEDGER_EVENT_TYPES:
        errors.append("missing or invalid 最低落账事件")
    if cost_body and impact_scale not in IMPACT_SCALES:
        errors.append("missing or invalid 推进重量")
    if cost_body and not consequence_level:
        errors.append("missing or invalid 后果等级")
    if mainline_level in LOW_S_LEVELS and external_level in LOW_W_LEVELS and not concrete_value(buffer_function):
        errors.append("低牵引章缺少具体低牵引功能")
    if impact_scale in LOW_IMPACT_SCALES and not concrete_value(buffer_function):
        errors.append("低推进重量章缺少具体低牵引功能")
    if (mainline_level in HIGH_S_LEVELS or external_level in HIGH_W_LEVELS or impact_scale in HIGH_IMPACT_SCALES) and (
        not concrete_value(aftermath_obligation) or digestion_window_chapters(digestion_window) is None
    ):
        errors.append("高推进章缺少后果承接义务或消化窗口")
    return {
        "chapter": chapter,
        "chapter_number": chapter_number(chapter),
        "path": path.relative_to(ROOT).as_posix(),
        "mainline_level": mainline_level,
        "mainline_explanation": mainline_explanation,
        "external_level": external_level,
        "external_explanation": external_explanation,
        "inherited_change": inherited_change,
        "pacing_note": pacing_note,
        "progress_mode": progress_mode,
        "end_state_delta": end_state_delta,
        "minimum_ledger_event": minimum_ledger_event,
        "buffer_function": buffer_function,
        "impact_scale": impact_scale,
        "consequence_level": consequence_level,
        "aftermath_obligation": aftermath_obligation,
        "digestion_window": digestion_window,
        "digestion_window_chapters": digestion_window_chapters(digestion_window),
        "resolved_threads": resolved_threads,
        "errors": errors,
    }


def warn_runs(entries: list[dict], key: str, levels: set[str], length: int, message: str) -> list[str]:
    warnings: list[str] = []
    run: list[str] = []
    for entry in entries:
        if entry.get(key) in levels:
            run.append(entry["chapter"])
            continue
        if len(run) >= length:
            warnings.append(f"{message}: {', '.join(run)}")
        run = []
    if len(run) >= length:
        warnings.append(f"{message}: {', '.join(run)}")
    return warnings


def level_index(level: str | None) -> int:
    if not level:
        return -1
    return int(level[1:])


def impact_index(scale: str | None) -> int:
    if not scale or len(scale) < 2 or not scale[1:].isdigit():
        return -1
    return int(scale[1:])


def has_effective_progress(entry: dict) -> bool:
    if not concrete_value(entry.get("end_state_delta", "")):
        return False
    if entry.get("progress_mode") in EFFECTIVE_PROGRESS_MODES:
        return True
    if impact_index(entry.get("impact_scale")) >= 2:
        return True
    return entry.get("consequence_level") in {"scar", "structure_change"}


def warn_windows(entries: list[dict], window: int) -> list[str]:
    if window <= 1:
        return []
    warnings: list[str] = []
    for index in range(0, max(0, len(entries) - window + 1)):
        subset = entries[index : index + window]
        if any(item["errors"] for item in subset):
            continue
        max_s = max(level_index(item["mainline_level"]) for item in subset)
        max_w = max(level_index(item["external_level"]) for item in subset)
        if max_s < 2 and max_w < 2:
            warnings.append(
                f"{window}章窗口没有 S2+ 或 W2+，可能状态变化不足: "
                f"{subset[0]['chapter']}..{subset[-1]['chapter']}"
            )
    return warnings


def block_low_impact_runs(entries: list[dict]) -> list[str]:
    blockers: list[str] = []
    run: list[dict] = []
    for entry in entries:
        if impact_index(entry.get("impact_scale")) <= 1:
            run.append(entry)
            continue
        if len(run) >= 3:
            blockers.append(f"连续 3 章推进重量 C0/C1，进展过小: {run[0]['chapter']}..{run[-1]['chapter']}")
        run = []
    if len(run) >= 3:
        blockers.append(f"连续 3 章推进重量 C0/C1，进展过小: {run[0]['chapter']}..{run[-1]['chapter']}")
    return blockers


def block_no_effective_progress_windows(entries: list[dict]) -> list[str]:
    blockers: list[str] = []
    for index in range(0, max(0, len(entries) - 3 + 1)):
        subset = entries[index : index + 3]
        if any(item["errors"] for item in subset):
            continue
        if not any(has_effective_progress(item) for item in subset):
            blockers.append(f"3 章窗口没有有效进展契约: {subset[0]['chapter']}..{subset[-1]['chapter']}")
    return blockers


def block_slow_windows(entries: list[dict], window: int) -> list[str]:
    if window <= 1:
        return []
    blockers: list[str] = []
    for index in range(0, max(0, len(entries) - window + 1)):
        subset = entries[index : index + window]
        if any(item["errors"] for item in subset):
            continue
        max_s = max(level_index(item["mainline_level"]) for item in subset)
        max_w = max(level_index(item["external_level"]) for item in subset)
        max_c = max(impact_index(item["impact_scale"]) for item in subset)
        if max_s < 2 and max_w < 2 and max_c < 2:
            blockers.append(
                f"{window}章窗口没有 S2+、W2+ 或 C2+，进度过小: "
                f"{subset[0]['chapter']}..{subset[-1]['chapter']}"
            )
    return blockers


def block_unresolved_aftermath(entries: list[dict]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not entries:
        return blockers, warnings
    latest_number = max(entry["chapter_number"] for entry in entries)
    for index, entry in enumerate(entries):
        window = entry.get("digestion_window_chapters")
        creates_obligation = (
            entry.get("impact_scale") in HIGH_IMPACT_SCALES
            or entry.get("progress_mode") == "payoff"
            or not is_none_body(entry.get("resolved_threads", ""))
        )
        if not creates_obligation or window is None:
            continue
        if window == 0:
            continue
        due_number = entry["chapter_number"] + window
        later = [
            item
            for item in entries[index + 1 :]
            if item["chapter_number"] <= due_number
        ]
        resolved = any(item.get("progress_mode") in DIGEST_MODES for item in later)
        if resolved:
            continue
        if latest_number >= due_number:
            blockers.append(
                f"{entry['chapter']} 的高推进/兑现后果未在 {window} 章内消化，截止 {entry['chapter'][:3]}_c{due_number:03d}"
            )
        else:
            warnings.append(f"{entry['chapter']} 产生后果承接义务，需要在 {window} 章内消化")
    return blockers, warnings


def warn_rest_notes(entries: list[dict]) -> list[str]:
    warnings: list[str] = []
    for entry in entries:
        if entry.get("mainline_level") == "S0" and entry.get("external_level") == "W0":
            note = entry.get("pacing_note", "")
            if not any(keyword in note for keyword in REST_NOTE_KEYWORDS):
                warnings.append(f"S0+W0 需要休整/释压/后果消化说明: {entry['chapter']}")
    return warnings


def analyze(entries: list[dict], window: int) -> tuple[str, list[str], list[str]]:
    blockers = [
        f"{entry['chapter']}: {error}"
        for entry in entries
        for error in entry["errors"]
    ]
    warnings: list[str] = []
    if not blockers:
        blockers.extend(block_low_impact_runs(entries))
        blockers.extend(block_no_effective_progress_windows(entries))
        blockers.extend(block_slow_windows(entries, window))
        aftermath_blockers, aftermath_warnings = block_unresolved_aftermath(entries)
        blockers.extend(aftermath_blockers)
        warnings.extend(aftermath_warnings)
    if not blockers:
        warnings.extend(warn_runs(entries, "mainline_level", LOW_S_LEVELS, 3, "连续低主线牵引"))
        warnings.extend(warn_runs(entries, "external_level", LOW_W_LEVELS, 3, "连续低外部压力"))
        warnings.extend(warn_runs(entries, "mainline_level", HIGH_S_LEVELS, 3, "连续高主线牵引，注意节奏过热"))
        warnings.extend(warn_runs(entries, "external_level", HIGH_W_LEVELS, 3, "连续高外部压力，注意节奏过热"))
        warnings.extend(warn_windows(entries, window))
        warnings.extend(warn_rest_notes(entries))
    status = "BLOCKED" if blockers else "WARN" if warnings else "READY"
    return status, blockers, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check cross-chapter mainline and external-pressure pacing.")
    parser.add_argument("chapter", nargs="?", default=None, help="Optional target chapter; only earlier chapters in the same volume are included.")
    parser.add_argument("--window", type=int, default=5, help="Window size for slow-drift checks.")
    parser.add_argument("--write", action="store_true", help="Write JSON evidence to state/derived/pacing/.")
    args = parser.parse_args()

    if args.chapter:
        chapter_parts(args.chapter)
    paths = brief_paths(args.chapter)
    entries = [parse_entry(path) for path in paths]
    status, blockers, warnings = analyze(entries, args.window)

    print(f"# Pacing Check{': ' + args.chapter if args.chapter else ''}")
    print()
    print(f"status: {status}")
    print(f"chapters_checked: {len(entries)}")
    print()
    if blockers:
        print("## Blockers")
        for item in blockers:
            print(f"- {item}")
        print()
    if warnings:
        print("## Warnings")
        for item in warnings:
            print(f"- {item}")
        print()
    if not blockers and not warnings:
        print("No pacing warnings.")

    if args.write:
        label = args.chapter or (entries[-1]["chapter"] if entries else "all")
        write_json(
            ROOT / "state" / "derived" / "pacing" / f"{label}.json",
            {
                "schema_version": 1,
                "status": status,
                "target_chapter": args.chapter,
                "window": args.window,
                "entries": entries,
                "blockers": blockers,
                "warnings": warnings,
            },
        )
    return 1 if status == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
