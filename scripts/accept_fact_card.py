from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from _common import ROOT, chapter_parts, read_json


def load_card(chapter: str, card_id: str) -> dict[str, Any]:
    path = ROOT / "reviews" / chapter / "fact_cards.json"
    data = read_json(path, {})
    for item in data.get("cards", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("id") == card_id:
            return item
    raise FileNotFoundError(f"missing fact card {card_id!r}; run `python scripts/novel.py fact-cards {chapter} --write` first")


def append_if(values: list[str], flag: str, value: str | None) -> None:
    if value:
        values.extend([flag, value])


def main() -> int:
    parser = argparse.ArgumentParser(description="Accept one fact card and append it to the event ledger.")
    parser.add_argument("chapter")
    parser.add_argument("--id", required=True)
    parser.add_argument("--fact", default="")
    parser.add_argument("--evidence-quote", default="")
    parser.add_argument("--consequence", default="")
    parser.add_argument("--entity", action="append", default=[])
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--importance", choices=["P0", "P1", "P2", "P3"], default=None)
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--anchor-end-time", default="")
    parser.add_argument("--anchor-end-location", default="")
    parser.add_argument("--anchor-present-character", action="append", default=[])
    parser.add_argument("--anchor-protagonist-state", default="")
    parser.add_argument("--anchor-carried-item", action="append", default=[])
    parser.add_argument("--anchor-unfinished-action", default="")
    parser.add_argument("--anchor-next-required-continuity", default="")
    args = parser.parse_args()

    try:
        chapter_parts(args.chapter)
        card = load_card(args.chapter, args.id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    command = [
        sys.executable,
        str(ROOT / "scripts" / "append_event.py"),
        "--chapter",
        args.chapter,
        "--type",
        str(card["type"]),
        "--fact",
        args.fact or str(card.get("fact", "")),
        "--evidence-quote",
        args.evidence_quote or str(card.get("evidence_quote", "")),
        "--consequence",
        args.consequence or str(card.get("consequence", "")),
    ]
    for entity in args.entity:
        command.extend(["--entity", entity])
    for tag in set([*args.tag, *card.get("tags", [])]):
        command.extend(["--tag", str(tag)])
    append_if(command, "--thread-id", args.thread_id)
    append_if(command, "--importance", args.importance or card.get("importance"))
    for value in args.anchor_present_character:
        command.extend(["--anchor-present-character", value])
    for value in args.anchor_carried_item:
        command.extend(["--anchor-carried-item", value])
    for flag, value in [
        ("--anchor-end-time", args.anchor_end_time),
        ("--anchor-end-location", args.anchor_end_location),
        ("--anchor-protagonist-state", args.anchor_protagonist_state),
        ("--anchor-unfinished-action", args.anchor_unfinished_action),
        ("--anchor-next-required-continuity", args.anchor_next_required_continuity),
    ]:
        append_if(command, flag, value)

    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
