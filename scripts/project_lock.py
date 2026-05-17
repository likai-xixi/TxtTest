from __future__ import annotations

import argparse

from _common import ROOT, now_iso, read_json, write_json


LOCKS = ROOT / "state" / "stops" / "project_locks.json"


def load() -> dict:
    return read_json(LOCKS, {"locks": []})


def save(data: dict) -> None:
    write_json(LOCKS, data)


def command_record(args: argparse.Namespace) -> int:
    data = load()
    lock_id = args.lock_id or f"lock_{len(data.get('locks', [])) + 1:03d}"
    data.setdefault("locks", []).append(
        {
            "id": lock_id,
            "chapter": args.chapter,
            "reason": args.reason,
            "status": "open",
            "created_at": now_iso(),
            "resolved_at": None,
            "resolution": "",
        }
    )
    save(data)
    print(f"OK: recorded stop lock {lock_id}")
    return 0


def command_resolve(args: argparse.Namespace) -> int:
    data = load()
    found = False
    for item in data.get("locks", []):
        if item.get("id") == args.lock_id:
            item["status"] = "resolved"
            item["resolved_at"] = now_iso()
            item["resolution"] = args.resolution
            found = True
            break
    if not found:
        print(f"ERROR: lock not found: {args.lock_id}")
        return 1
    save(data)
    print(f"OK: resolved stop lock {args.lock_id}")
    return 0


def command_list(_args: argparse.Namespace) -> int:
    data = load()
    open_locks = [item for item in data.get("locks", []) if item.get("status") == "open"]
    print(f"open_locks: {len(open_locks)}")
    for item in open_locks:
        print(f"- {item.get('id')}: {item.get('chapter') or 'project'} {item.get('reason')}")
    return 1 if open_locks else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage unresolved stop-rule locks.")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--chapter", default="")
    record.add_argument("--reason", required=True)
    record.add_argument("--lock-id", default=None)
    record.set_defaults(func=command_record)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--lock-id", required=True)
    resolve.add_argument("--resolution", required=True)
    resolve.set_defaults(func=command_resolve)

    listed = sub.add_parser("list")
    listed.set_defaults(func=command_list)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
