from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import ROOT, chapter_number, chapter_parts, now_iso, read_text, truncate, write_text
from context_governance import context_manifest_path, context_pack_budget, input_hash, rel, section_budgets, sha256
from core_setting_freeze import ensure_ready as ensure_core_setting_freeze, freeze_markdown_path
from element_context import (
    ALLOWED_NEW_ELEMENT_SECTIONS,
    PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    USABLE_ABILITY_ID_SECTIONS,
    USABLE_OBJECT_ID_SECTIONS,
    declared_ids,
    has_placeholder,
    markdown_sections,
    missing_section,
    section_body,
    selected_yaml_section,
)


LEGACY_OBJECT_TITLE = "本章可用道具完整条目"
LEGACY_CURRENT_OBJECTS = "当前道具 / 装备变化"
LEGACY_CURRENT_ABILITIES = "当前技能 / 规则揭示"
LEGACY_CORE_FREEZE = "开书前核心设定冻结"
UNAUTHORIZED_BREAKER_RULE = "不得靠未授权新道具、新能力或新规则解决本章核心问题。"


@dataclass
class SourceRef:
    path: Path | None = None
    event_id: str | None = None
    note: str = ""

    def manifest(self) -> dict[str, str]:
        item: dict[str, str] = {}
        if self.path is not None:
            item["path"] = rel(self.path)
            if self.path.exists() and self.path.is_file():
                item["sha256"] = sha256(self.path)
        if self.event_id:
            item["event_id"] = self.event_id
        if self.note:
            item["note"] = self.note
        return item


@dataclass
class Section:
    id: str
    title: str
    body: str
    budget: int
    sources: list[SourceRef]
    included_reason: str
    priority: int

    def render(self) -> tuple[str, dict[str, Any]]:
        original_chars = len(self.body.strip())
        truncated = original_chars > self.budget
        body = truncate(self.body, self.budget) if self.budget > 0 else self.body.strip()
        text = "\n".join(
            [
                f"## {self.title}",
                "",
                source_trace_markdown(self.sources),
                "",
                body.strip() or "none",
                "",
            ]
        ).rstrip() + "\n"
        manifest = {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "budget_chars": self.budget,
            "body_chars": len(body),
            "original_body_chars": original_chars,
            "truncated": truncated,
            "included_reason": self.included_reason,
            "sources": [source.manifest() for source in self.sources],
        }
        event_ids = [source.event_id for source in self.sources if source.event_id]
        if event_ids:
            manifest["event_ids"] = event_ids
        return text, manifest


def source_trace_markdown(sources: list[SourceRef]) -> str:
    if not sources:
        return "source_trace: []"
    lines = ["source_trace:"]
    for source in sources:
        bits = []
        if source.path is not None:
            bits.append(f"path={rel(source.path)}")
        if source.event_id:
            bits.append(f"event_id={source.event_id}")
        if source.note:
            bits.append(f"note={source.note}")
        lines.append(f"- {'; '.join(bits)}")
    return "\n".join(lines)


def file_body(path: Path, default: str = "none") -> str:
    return read_text(path, default).strip() or default


def load_events() -> list[dict[str, Any]]:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def id_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "none"


def selected_events_for_chapter(chapter: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    number = chapter_number(chapter)
    lower = max(1, number - 5)
    selected: dict[str, dict[str, Any]] = {}
    for event in events:
        event_chapter = chapter_number(event["chapter"])
        if lower <= event_chapter < number or (event_chapter < number and event.get("importance") in {"P0", "P1"}):
            selected[event["event_id"]] = event
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(
        selected.values(),
        key=lambda event: (rank.get(event.get("importance", "P2"), 2), -chapter_number(event["chapter"]), event["event_id"]),
    )


def event_body(events: list[dict[str, Any]]) -> str:
    if not events:
        return "none"
    lines = []
    for event in events:
        meta = [event["chapter"], event["type"], event.get("importance", "P2")]
        if event.get("thread_id"):
            meta.append(f"thread={event['thread_id']}")
        if event.get("entities"):
            meta.append("entities=" + ",".join(str(item) for item in event["entities"]))
        lines.append(f"- {event['event_id']} ({'; '.join(meta)}): {event['fact']} -> {event['consequence']}")
    return "\n".join(lines)


def relevant_entity_cards(brief_text: str, object_ids: list[str], ability_ids: list[str]) -> tuple[str, list[SourceRef]]:
    roots = [
        ROOT / "state" / "derived" / "entities" / "characters",
        ROOT / "state" / "derived" / "entities" / "objects",
        ROOT / "state" / "derived" / "entities" / "abilities",
        ROOT / "state" / "derived" / "entities" / "locations",
    ]
    needles = set(object_ids + ability_ids + ["protagonist", "main_character"])
    selected: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.yaml")):
            text = read_text(path)
            if path.stem in needles or path.stem in brief_text or any(item and item in text for item in needles):
                selected.append(path)
    if not selected:
        return "none", [SourceRef(ROOT / "state" / "derived" / "entities", note="no relevant entity cards")]
    parts = []
    sources = []
    for path in selected[:20]:
        parts.append(f"### {path.stem}\n\n```yaml\n{read_text(path).strip()}\n```")
        sources.append(SourceRef(path))
    return "\n\n".join(parts), sources


def thread_sources() -> list[SourceRef]:
    return [
        SourceRef(ROOT / "state" / "derived" / "threads" / "active.yaml"),
        SourceRef(ROOT / "state" / "derived" / "threads" / "open.yaml"),
    ]


def thread_body() -> str:
    parts = []
    for source in thread_sources():
        if source.path and source.path.exists():
            parts.append(f"### {source.path.stem}\n\n```yaml\n{read_text(source.path).strip()}\n```")
    return "\n\n".join(parts) if parts else "none"


def arc_sources(chapter: str) -> list[SourceRef]:
    number = chapter_number(chapter)
    start = ((number - 1) // 50) * 50 + 1
    end = start + 49
    return [
        SourceRef(ROOT / "state" / "derived" / "arcs" / "volume_01.md"),
        SourceRef(ROOT / "state" / "derived" / "arcs" / f"chunk_{start:03d}_{end:03d}.md"),
    ]


def arc_body(chapter: str) -> str:
    parts = [file_body(source.path) for source in arc_sources(chapter) if source.path and source.path.exists()]
    return "\n\n".join(parts) if parts else "none"


def validate_brief_element_sections(brief_sections: dict[str, str]) -> tuple[list[str], list[str], str, str] | None:
    for aliases in (
        USABLE_OBJECT_ID_SECTIONS,
        USABLE_ABILITY_ID_SECTIONS,
        ALLOWED_NEW_ELEMENT_SECTIONS,
        PROHIBITED_INSTANT_SOLUTION_SECTIONS,
    ):
        label = aliases[0]
        if missing_section(brief_sections, aliases):
            print(f"ERROR: missing brief element section: {label}", file=sys.stderr)
            return None
        body = section_body(brief_sections, aliases)
        if not body or has_placeholder(body):
            print(f"ERROR: brief element section is not ready: {label}", file=sys.stderr)
            return None
    return (
        declared_ids(section_body(brief_sections, USABLE_OBJECT_ID_SECTIONS)),
        declared_ids(section_body(brief_sections, USABLE_ABILITY_ID_SECTIONS)),
        section_body(brief_sections, ALLOWED_NEW_ELEMENT_SECTIONS),
        section_body(brief_sections, PROHIBITED_INSTANT_SOLUTION_SECTIONS),
    )


def build_sections(chapter: str, brief_text: str, object_ids: list[str], ability_ids: list[str], allowed_new: str, prohibited_solutions: str) -> tuple[list[Section], list[str]]:
    budgets = section_budgets()
    freeze_path = freeze_markdown_path() or ROOT / "state" / "idea_lab" / "missing.md"
    object_path = ROOT / "bible" / "objects.yaml"
    ability_path = ROOT / "bible" / "abilities.yaml"
    object_section, missing_objects = selected_yaml_section(LEGACY_OBJECT_TITLE, object_path, "objects", object_ids)
    ability_section, missing_abilities = selected_yaml_section("Authorized Ability Entries", ability_path, "abilities", ability_ids)
    if missing_objects or missing_abilities:
        errors = [f"brief references unknown object id: {item}" for item in missing_objects]
        errors.extend(f"brief references unknown ability id: {item}" for item in missing_abilities)
        return [], errors

    entity_cards, entity_sources = relevant_entity_cards(brief_text, object_ids, ability_ids)
    events = selected_events_for_chapter(chapter, load_events())
    event_sources = [SourceRef(ROOT / "state" / "event_ledger.jsonl", event["event_id"]) for event in events]
    if not event_sources:
        event_sources = [SourceRef(ROOT / "state" / "event_ledger.jsonl", note="no prior key events")]

    authorization = "\n".join(
        [
            "### Usable Object IDs",
            id_list(object_ids),
            "",
            "### Usable Ability IDs",
            id_list(ability_ids),
            "",
            "### Allowed New Elements",
            allowed_new or "none",
            "",
            "### Prohibited Instant Solutions",
            prohibited_solutions or "none",
            "",
            object_section.strip(),
            "",
            ability_section.strip(),
        ]
    )
    boundaries = "\n\n".join(
        [
            "### Canon Hard Facts\n\n" + file_body(ROOT / "bible" / "canon.md"),
            "### Rules and Boundaries\n\n" + file_body(ROOT / "bible" / "rules.md"),
            "### Style / Forbidden Drift\n\n" + file_body(ROOT / "bible" / "style_guide.md"),
        ]
    )

    return [
        Section(
            "writing_boundaries",
            "Writing Hard Boundaries",
            "\n".join(
                [
                    "- Context pack is a cockpit for this chapter, not a whole-book archive.",
                    "- Full history lives in state/event_ledger.jsonl; current state is rebuilt in state/derived/.",
                    "- Drafting must use only this pack and the official chapter brief.",
                    "- Do not invent missing L3/L4 mechanisms; ask for a human decision.",
                    f"- {UNAUTHORIZED_BREAKER_RULE}",
                ]
            ),
            1200,
            [SourceRef(ROOT / "AGENTS.md"), SourceRef(ROOT / "ops" / "process_budget.yaml")],
            "always",
            0,
        ),
        Section("core_freeze", LEGACY_CORE_FREEZE, file_body(freeze_path), budgets["core_freeze"], [SourceRef(freeze_path)], "always", 1),
        Section("chapter_brief", "本章 brief", brief_text, budgets["chapter_brief"], [SourceRef(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md")], "always", 2),
        Section("authorized_elements_full", "本章元素授权", authorization, budgets["authorized_elements_full"], [SourceRef(ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"), SourceRef(object_path), SourceRef(ability_path)], "brief_authorized_ids", 3),
        Section("active_entity_cards", "本章相关实体状态卡", entity_cards, budgets["active_entity_cards"], entity_sources, "brief_and_authorized_entity_recall", 4),
        Section("open_threads", "Active / Open Threads", thread_body(), budgets["open_threads"], thread_sources(), "active_or_open_threads", 5),
        Section("recent_events", "Recent Key Events", event_body(events), budgets["recent_events"], event_sources, "recent_3_to_5_chapters_plus_P0_P1", 6),
        Section("arc_summary", "Arc / Chunk Summary", arc_body(chapter), budgets["arc_summary"], arc_sources(chapter), "long_cause_by_arc_chunk", 7),
        Section("rules_and_boundaries", "Rules And Boundaries", boundaries, budgets["rules_and_boundaries"], [SourceRef(ROOT / "bible" / "canon.md"), SourceRef(ROOT / "bible" / "rules.md"), SourceRef(ROOT / "bible" / "style_guide.md")], "hard_rules_only", 8),
        Section("legacy_state_compat", LEGACY_CURRENT_OBJECTS, file_body(ROOT / "state" / "derived" / "current_objects.yaml"), 700, [SourceRef(ROOT / "state" / "derived" / "current_objects.yaml")], "legacy_compatibility", 9),
        Section("legacy_ability_compat", LEGACY_CURRENT_ABILITIES, file_body(ROOT / "state" / "derived" / "current_abilities.yaml"), 700, [SourceRef(ROOT / "state" / "derived" / "current_abilities.yaml")], "legacy_compatibility", 10),
    ], []


def append_manifest_sections(text: str, manifest: dict[str, Any]) -> str:
    rank = sorted(manifest["sections"], key=lambda item: item["body_chars"], reverse=True)
    manifest_path = context_manifest_path(manifest["chapter"])
    lines = [text.rstrip(), "", "## Section Character Rank", "", "source_trace:", f"- path={rel(manifest_path)}", ""]
    for item in rank:
        marker = " truncated" if item["truncated"] else ""
        lines.append(f"- {item['id']}: {item['body_chars']} chars (budget {item['budget_chars']}){marker}")
    lines.extend(["", "## Context Pack Manifest", "", f"- manifest: `{rel(manifest_path)}`"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the single allowed context pack for a chapter.")
    parser.add_argument("--chapter", required=True, help="Chapter id like v01_c001.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--allow-truncated", action="store_true")
    args = parser.parse_args()

    chapter = args.chapter
    try:
        chapter_parts(chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not ensure_core_setting_freeze():
        return 1
    limit = context_pack_budget(chapter, args.limit)

    brief_path = ROOT / "outline" / "chapter_briefs" / f"{chapter}.md"
    if not brief_path.exists():
        print(f"ERROR: missing chapter brief: {brief_path.relative_to(ROOT)}")
        return 1
    brief_text = read_text(brief_path)
    parsed = validate_brief_element_sections(markdown_sections(brief_text))
    if parsed is None:
        return 1
    object_ids, ability_ids, allowed_new, prohibited_solutions = parsed

    sections, errors = build_sections(chapter, brief_text, object_ids, ability_ids, allowed_new, prohibited_solutions)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    rendered_sections = []
    section_manifest = []
    for section in sections:
        rendered, item = section.render()
        rendered_sections.append(rendered)
        section_manifest.append(item)

    generated_at = now_iso()
    header = [
        f"# Context Pack: {chapter}",
        "",
        f"generated_at: {generated_at}",
        f"budget_chars: {limit}",
        "architecture: event_ledger -> derived state -> brief-scoped context pack",
        "",
    ]
    text = "\n".join(header + rendered_sections).strip() + "\n"
    manifest = {
        "schema_version": 2,
        "chapter": chapter,
        "generated_at": generated_at,
        "budget_chars": limit,
        "hard_max_chars": context_pack_budget(chapter, 999999999),
        "allow_truncated": args.allow_truncated,
        "pack_chars": len(text),
        "object_ids": object_ids,
        "ability_ids": ability_ids,
        "sections": section_manifest,
        "section_char_rank": sorted(
            [{"id": item["id"], "body_chars": item["body_chars"], "budget_chars": item["budget_chars"]} for item in section_manifest],
            key=lambda item: item["body_chars"],
            reverse=True,
        ),
        "input_hashes": [
            input_hash(path)
            for path in sorted(
                {
                    source.path
                    for section in sections
                    for source in section.sources
                    if source.path is not None and source.path.exists() and source.path.is_file()
                }
            )
        ],
    }
    text = append_manifest_sections(text, manifest)
    manifest["pack_chars"] = len(text)

    if len(text) > limit:
        snapshot = ROOT / "state" / "snapshots" / f"{chapter}_oversize_context.md"
        write_text(snapshot, text)
        manifest["snapshot"] = rel(snapshot)
        if not args.allow_truncated:
            write_text(context_manifest_path(chapter), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            print(
                f"ERROR: context pack exceeds {limit} chars; full candidate saved to {snapshot.relative_to(ROOT)}. "
                "Tighten source files or rerun with --allow-truncated for diagnostics."
            )
            return 1
        text = (
            "\n".join(header).strip()
            + f"\n\n## Snapshot\n\nsource_trace:\n- path={rel(snapshot)}\n\nContext exceeded {limit} chars. Full candidate pack saved to `{rel(snapshot)}`. Tighten source files before drafting.\n"
        )
        if len(text) > limit:
            text = text[: limit - 120].rstrip() + "\n\n[context truncated; rebuild required]\n"
        manifest["pack_chars"] = len(text)
        manifest["pack_truncated"] = True
    else:
        manifest["pack_truncated"] = False

    out = ROOT / "state" / "context_pack" / f"{chapter}.md"
    write_text(out, text)
    manifest["context_pack"] = {"path": rel(out), "sha256": sha256(out), "chars": len(text)}
    write_text(context_manifest_path(chapter), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    from context_pack_quality import write_quality_report

    quality = write_quality_report(chapter)
    print(
        f"OK: wrote {out.relative_to(ROOT)} ({len(text)} chars, limit {limit}); "
        f"manifest={context_manifest_path(chapter).relative_to(ROOT)}; quality={quality.get('status', 'UNKNOWN')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
