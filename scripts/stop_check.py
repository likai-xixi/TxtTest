from __future__ import annotations

import argparse
import hashlib
import re

from _common import ROOT, now_iso, read_json, read_text, write_json
from gate_check import continuity_has_blocker


REJECT_RE = re.compile(r"(Rewrite brief|Kill chapter|Pause project)", re.IGNORECASE)


def review_rejects(path_text: str) -> bool:
    return bool(REJECT_RE.search(read_text(ROOT / path_text)))


def model_disagreement_blocks(chapter: str) -> bool:
    text = read_text(ROOT / "reviews" / chapter / "model_disagreement.md")
    for line in text.splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip() in {"CONFLICT", "NEEDS_HUMAN"}
    return False


def record_stop_lock(chapter: str, reason: str) -> None:
    path = ROOT / "state" / "stops" / "project_locks.json"
    data = read_json(path, {"locks": []})
    digest = hashlib.sha1(reason.encode("utf-8")).hexdigest()[:10]
    lock_id = f"stop_{chapter}_{digest}"
    for item in data.get("locks", []):
        if item.get("id") == lock_id and item.get("status") == "open":
            return
    data.setdefault("locks", []).append(
        {
            "id": lock_id,
            "chapter": chapter,
            "reason": reason,
            "status": "open",
            "created_at": now_iso(),
            "resolved_at": None,
            "resolution": "",
        }
    )
    write_json(path, data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate machine-checkable stop rules for one chapter.")
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    blockers: list[str] = []
    if continuity_has_blocker(args.chapter):
        blockers.append("continuity_check has unresolved P0/P1; human decision required before continuing")

    codex_rejects = review_rejects(f"reviews/{args.chapter}/codex_integrated_review.md")
    deepseek_rejects = review_rejects(f"reviews/{args.chapter}/deepseek_integrated_review.md")
    if codex_rejects and deepseek_rejects:
        blockers.append("Codex and DeepSeek both recommend rewrite/kill/pause")
    if model_disagreement_blocks(args.chapter):
        blockers.append("Codex and DeepSeek review comparison requires human decision")

    print(f"# Stop Check: {args.chapter}")
    print()
    if blockers:
        print("status: STOP")
        print()
        for blocker in blockers:
            print(f"- {blocker}")
            record_stop_lock(args.chapter, blocker)
        return 1

    print("status: CLEAR")
    print()
    print("No machine-checkable stop rule fired. Human/editorial rules still apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
