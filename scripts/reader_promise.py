from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import ROOT, now_iso, read_json, read_text, write_json, write_text
from reader_personality_contracts import (
    READER_PROMISE_JSON,
    READER_PROMISE_MD,
    READER_PROMISE_TEMPLATE,
    default_reader_promise,
    ensure_reader_promise_file,
    render_reader_promise_markdown,
    validate_reader_promise,
)


def start(force: bool = False) -> int:
    if READER_PROMISE_JSON.exists() and not force:
        print(f"skipped existing: {READER_PROMISE_JSON.relative_to(ROOT)}")
    else:
        write_json(READER_PROMISE_JSON, default_reader_promise())
        print(f"OK: wrote {READER_PROMISE_JSON.relative_to(ROOT)}")
    if READER_PROMISE_MD.exists() and not force:
        print(f"skipped existing: {READER_PROMISE_MD.relative_to(ROOT)}")
    else:
        template = read_text(READER_PROMISE_TEMPLATE)
        write_text(READER_PROMISE_MD, template or render_reader_promise_markdown(default_reader_promise()))
        print(f"OK: wrote {READER_PROMISE_MD.relative_to(ROOT)}")
    return 0


def check(require_ready: bool = False) -> int:
    ensure_reader_promise_file()
    data = read_json(READER_PROMISE_JSON, {})
    errors = validate_reader_promise(data, require_ready=require_ready)
    print("# Reader Promise")
    print()
    if errors:
        print("status: NOT_READY")
        print()
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"status: {data.get('status', 'DRAFT')}")
    print(f"path: {READER_PROMISE_JSON.relative_to(ROOT).as_posix()}")
    return 0


def land(source: Path | None = None, ready: bool = False) -> int:
    ensure_reader_promise_file()
    data = read_json(source, {}) if source else read_json(READER_PROMISE_JSON, {})
    if not isinstance(data, dict):
        print("ERROR: reader promise source must be a JSON object", file=sys.stderr)
        return 1
    data["updated_at"] = now_iso()
    if ready:
        data["status"] = "READY"
    errors = validate_reader_promise(data, require_ready=ready)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    write_json(READER_PROMISE_JSON, data)
    write_text(READER_PROMISE_MD, render_reader_promise_markdown(data))
    print(f"OK: landed {READER_PROMISE_JSON.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create, validate, or land the project reader promise.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("check")
    p.add_argument("--require-ready", action="store_true")
    p = sub.add_parser("land")
    p.add_argument("--source", default=None)
    p.add_argument("--ready", action="store_true")
    args = parser.parse_args()
    if args.command == "start":
        return start(force=args.force)
    if args.command == "check":
        return check(require_ready=args.require_ready)
    if args.command == "land":
        source = Path(args.source) if args.source else None
        if source is not None and not source.is_absolute():
            source = ROOT / source
        return land(source=source, ready=args.ready)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
