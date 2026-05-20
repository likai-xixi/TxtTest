from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_json, write_blocked_by_locks, write_json, write_text
from candidate_style_requirements import prompt_paths, validate_prompt_manifest


CHOICES = ["Codex", "DeepSeek", "Mixed", "Rewrite brief", "No usable candidate"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_paths(chapter: str, choice: str) -> list[Path]:
    paths: list[Path] = []
    if choice in {"Codex", "Mixed"}:
        paths.append(ROOT / "drafts" / "codex" / f"{chapter}.md")
    if choice in {"DeepSeek", "Mixed"}:
        paths.append(ROOT / "drafts" / "deepseek" / f"{chapter}.md")
    return paths


def collect_candidates(chapter: str, choice: str) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    for path in candidate_paths(chapter, choice):
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing non-empty selected candidate: {path.relative_to(ROOT)}")
            continue
        candidates.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)})
    return candidates, errors


def providers_for_choice(choice: str) -> list[str]:
    providers: list[str] = []
    if choice in {"Codex", "Mixed"}:
        providers.append("Codex")
    if choice in {"DeepSeek", "Mixed"}:
        providers.append("DeepSeek")
    return providers


def collect_prompt_evidence(chapter: str, choice: str) -> tuple[list[dict], list[str]]:
    evidence: list[dict] = []
    errors: list[str] = []
    for provider in providers_for_choice(choice):
        errors.extend(validate_prompt_manifest(chapter, provider, require_candidate_written=(provider == "DeepSeek")))
        _prompt_path, manifest_path = prompt_paths(chapter, provider)
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path, {})
        context_pack = manifest.get("context_pack") if isinstance(manifest, dict) else {}
        evidence.append(
            {
                "provider": provider,
                "manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), "sha256": sha256(manifest_path)},
                "prompt": {
                    "path": str(manifest.get("prompt_path", "")) if isinstance(manifest, dict) else "",
                    "sha256": str(manifest.get("prompt_sha256", "")) if isinstance(manifest, dict) else "",
                },
                "context_pack_sha256": context_pack.get("sha256") if isinstance(context_pack, dict) else "",
                "style_sources": manifest.get("style_sources", []) if isinstance(manifest, dict) else [],
            }
        )
    return evidence, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the human-selected candidate direction for a chapter.")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--choice", required=True, choices=CHOICES)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--adopt", default="")
    parser.add_argument("--reject", default="")
    parser.add_argument("--mixed-strategy", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if write_blocked_by_locks("candidate selection recording"):
        return 1

    chapter_parts(args.chapter)
    candidates, errors = collect_candidates(args.chapter, args.choice)
    prompt_evidence, prompt_errors = collect_prompt_evidence(args.chapter, args.choice)
    errors.extend(prompt_errors)
    if args.choice == "Mixed" and not args.mixed_strategy.strip():
        errors.append("Mixed selection requires --mixed-strategy.")
    if args.choice not in {"Rewrite brief", "No usable candidate"} and not candidates:
        errors.append("selected candidate choice requires at least one candidate file.")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    selected_at = now_iso()
    record = {
        "chapter": args.chapter,
        "selected_at": selected_at,
        "choice": args.choice,
        "reason": args.reason,
        "adopt": args.adopt,
        "reject": args.reject,
        "mixed_strategy": args.mixed_strategy,
        "selected_candidates": candidates,
        "selected_prompt_evidence": prompt_evidence,
        "notes": args.notes.strip() or "无。",
        "human_decision_required": True,
        "deepseek_can_be_official_after_selection": True,
    }
    lines = [
        f"# Candidate Selection: {args.chapter}",
        "",
        f"selected_at: {selected_at}",
        f"choice: {args.choice}",
        "",
        "## Reason",
        "",
        args.reason,
        "",
        "## Selected Candidates",
        "",
    ]
    if candidates:
        for candidate in candidates:
            lines.append(f"- `{candidate['path']}` sha256={candidate['sha256']}")
    else:
        lines.append("无。")
    lines.extend(["", "## Selected Prompt Evidence", ""])
    if prompt_evidence:
        for item in prompt_evidence:
            manifest = item["manifest"]
            prompt = item["prompt"]
            lines.append(f"- {item['provider']}: `{manifest['path']}` sha256={manifest['sha256']}")
            lines.append(f"  prompt: `{prompt['path']}` sha256={prompt['sha256']}")
    else:
        lines.append("none")
    lines.extend(
        [
            "",
            "## Adopt",
            "",
            args.adopt.strip() or "无。",
            "",
            "## Reject",
            "",
            args.reject.strip() or "无。",
            "",
            "## Mixed Strategy",
            "",
            args.mixed_strategy.strip() or "无。",
            "",
        ]
    )
    lines.extend([
        "## Notes",
        "",
        args.notes.strip() or "无。",
        "",
        "## Boundary",
        "",
        "- DeepSeek output may become the official chapter only after human selection and Codex landing provenance.",
        "- If DeepSeek is selected, the official chapter may match the selected DeepSeek draft exactly.",
        "- This record does not change canon, state, or event ledger.",
        "",
        "## Allowed Choices",
        "",
    ])
    lines.extend(f"- {item}" for item in CHOICES)
    out = ROOT / "reviews" / args.chapter / "candidate_selection.md"
    write_text(out, "\n".join(lines) + "\n")
    write_json(ROOT / "state" / "selections" / f"{args.chapter}.json", record)
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
