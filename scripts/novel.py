from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from _common import ROOT, chapter_parts, now_iso, read_text, unresolved_locks, write_text
from diff_scope_check import ROLE_PATTERNS, changed_files
from gate_config import load_gate_configs
from validate_event_ledger import ALLOWED_TYPES


DECISIONS = ["Ship", "Revise once", "Rewrite brief", "Kill chapter", "Pause project"]
GATES = load_gate_configs()
PLACEHOLDER_MARKERS = ("待定", "待填", "待评", "待生成", "待人类裁决", "TODO")
IDEA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
IDEA_FORCE_CLEANUP_FILES = (
    "deepseek_idea.md",
    "product_founder_review.md",
    "technical_lead_review.md",
    "qa_release_review.md",
    "codex_synthesis.md",
    "agent_tasks.md",
    "selection.json",
    "selection.md",
)


def run_script(script: str, *args: str, check: bool = True) -> int:
    command = [sys.executable, str(ROOT / "scripts" / script), *args]
    result = subprocess.run(command, cwd=ROOT)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.returncode


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if check and result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def git_config_get(key: str) -> str:
    result = run_git("config", "--get", key, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def ensure_git_identity() -> None:
    changed: list[str] = []
    if not git_config_get("user.name"):
        run_git("config", "user.name", "Codex")
        changed.append("user.name=Codex")
    if not git_config_get("user.email"):
        run_git("config", "user.email", "codex@local")
        changed.append("user.email=codex@local")
    if changed:
        print(f"info: set local Git identity ({', '.join(changed)})")


def ensure_no_open_locks() -> None:
    locks = unresolved_locks()
    if not locks:
        return
    print("ERROR: unresolved stop locks block this action:", file=sys.stderr)
    for lock in locks:
        print(f"  - {lock.get('id')}: {lock.get('reason')}", file=sys.stderr)
    raise SystemExit(1)


def copy_questionnaire(output: Path, force: bool) -> None:
    source = ROOT / "templates" / "questionnaire_answers.md"
    if output.exists() and not force:
        raise SystemExit(f"ERROR: {output.relative_to(ROOT)} already exists. Use --force to overwrite.")
    write_text(output, read_text(source))
    print(f"OK: wrote {output.relative_to(ROOT)}")


def has_placeholders(path: Path) -> bool:
    text = read_text(path)
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def validate_idea_id(value: str) -> str:
    if not IDEA_ID_RE.match(value):
        raise argparse.ArgumentTypeError("idea id must use only letters, numbers, dash, and underscore")
    return value


def default_idea_id() -> str:
    return "idea_" + now_iso().replace("-", "").replace(":", "").replace("+00:00", "Z")


def cleanup_forced_idea_lab(lab: Path) -> None:
    for name in IDEA_FORCE_CLEANUP_FILES:
        path = lab / name
        if path.exists():
            path.unlink()


def seed_text(path: Path) -> str:
    text = read_text(path)
    if not text.strip():
        return ""
    return text


def chapter_has_events(chapter: str) -> bool:
    ledger = ROOT / "state" / "event_ledger.jsonl"
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("chapter") == chapter and entry.get("verified_by") == "human":
            return True
    return False


def command_init(args: argparse.Namespace) -> int:
    script_args = ["--project-name", args.name]
    if args.init_git:
        script_args.append("--init-git")
    if args.clean_generated:
        script_args.append("--clean-generated")
    run_script("template_init.py", *script_args)
    run_script("check_template.py")
    return 0


def command_questionnaire(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    copy_questionnaire(output, args.force)
    print("next: fill the answers, then run `python scripts/novel.py apply-questionnaire`")
    return 0


def command_apply_questionnaire(args: argparse.Namespace) -> int:
    script_args = ["--answers", args.answers]
    if args.allow_placeholders:
        script_args.append("--allow-placeholders")
    run_script("apply_questionnaire.py", *script_args)
    print("next: ask Codex to generate minimal worldview, protagonist card, and volume mini-outline for human confirmation")
    return 0


def command_go(args: argparse.Namespace) -> int:
    script_args = ["--project-name", args.name, "--init-git"]
    if args.clean_generated:
        script_args.append("--clean-generated")
    run_script("template_init.py", *script_args)
    run_script("check_template.py")

    print("# Go")
    print()
    print(f"DEEPSEEK_API_KEY: {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'missing'}")
    print()

    answers = Path(args.answers)
    if not answers.is_absolute():
        answers = ROOT / answers

    if not answers.exists():
        copy_questionnaire(answers, force=False)
        print()
        print(f"next: fill `{display_path(answers)}`, then run `python scripts/novel.py go` again.")
        return 0

    if has_placeholders(answers):
        print(f"next: finish `{display_path(answers)}`, then run `python scripts/novel.py go` again.")
        return 0

    premise = ROOT / "outline" / "premise.md"
    if has_placeholders(premise):
        run_script("apply_questionnaire.py", "--answers", str(answers))
        print("OK: applied startup questionnaire.")
        print()

    setup_assets = [
        ROOT / "bible" / "worldview.md",
        ROOT / "bible" / "rules.md",
        ROOT / "bible" / "characters.yaml",
        ROOT / "bible" / "relationships.yaml",
        ROOT / "outline" / "volume_01.md",
    ]
    if any(has_placeholders(path) for path in setup_assets):
        print("next: ask Codex to draft the minimal worldview, protagonist card, relationships seed, and volume mini-outline.")
        print("guardrail: keep canon empty until the human editor confirms hard facts.")
        return 0

    brief = ROOT / "outline" / "chapter_briefs" / f"{args.chapter}.md"
    if not brief.exists():
        run_script("new_chapter.py", "--chapter", args.chapter)
        print()
    if has_placeholders(brief):
        print(f"next: fill `{display_path(brief)}`, then run `python scripts/novel.py go --chapter {args.chapter}` again.")
        return 0

    context = ROOT / "state" / "context_pack" / f"{args.chapter}.md"
    if not context.exists():
        start_args = ["--chapter", args.chapter]
        if args.deepseek_dry_run:
            start_args.append("--deepseek-dry-run")
        run_script("start_chapter.py", *start_args)
        print(f"ready: `{display_path(context)}`")
        return 0

    print(f"ready: `{display_path(context)}`")
    print(f"next: ask Codex to write `drafts/codex/{args.chapter}.md` from the context pack.")
    if os.environ.get("DEEPSEEK_API_KEY"):
        print(f"optional: run `python scripts/novel.py deepseek-generate {args.chapter}` for a DeepSeek candidate.")
    else:
        print("optional: DeepSeek key is missing in this process; use dry-run or restart Codex after setting the system env var.")
    return 0


def command_draft(args: argparse.Namespace) -> int:
    return command_go(
        argparse.Namespace(
            name=args.name,
            answers=args.answers,
            chapter=args.chapter,
            clean_generated=False,
            deepseek_dry_run=args.deepseek_dry_run,
        )
    )


def command_idea_form(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if output.exists() and not args.force:
        print(f"ERROR: {display_path(output)} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    write_text(output, read_text(ROOT / "templates" / "idea_seed.md"))
    print(f"OK: wrote {display_path(output)}")
    print("next: fill it, then run `python scripts/novel.py idea --seed idea_seed.md`.")
    return 0


def command_idea(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("ERROR: DEEPSEEK_API_KEY is required for idea lab; dry-run is not allowed.", file=sys.stderr)
        return 2

    if args.text:
        idea_text = args.text.strip()
    else:
        seed = Path(args.seed)
        if not seed.is_absolute():
            seed = ROOT / seed
        if not seed.exists():
            print(f"ERROR: missing idea seed: {display_path(seed)}", file=sys.stderr)
            return 1
        idea_text = seed_text(seed).strip()
    if not idea_text:
        print("ERROR: idea text must not be empty.", file=sys.stderr)
        return 1
    if args.seed and has_placeholders(seed):
        print("ERROR: idea seed still has placeholders.", file=sys.stderr)
        return 1

    idea_id = args.id or default_idea_id()
    validate_idea_id(idea_id)
    lab = ROOT / "state" / "idea_lab" / idea_id
    if lab.exists() and not args.force:
        print(f"ERROR: idea lab already exists: {lab.relative_to(ROOT)}. Use --force to overwrite metadata.", file=sys.stderr)
        return 1
    if lab.exists() and args.force:
        cleanup_forced_idea_lab(lab)
    write_text(lab / "original_idea.md", f"# Original Idea: {idea_id}\n\n{idea_text}\n")
    write_text(
        lab / "idea.json",
        json.dumps(
            {
                "idea_id": idea_id,
                "created_at": now_iso(),
                "requires_deepseek": True,
                "requires_multi_agent": True,
                "writes_canon": False,
                "writes_chapters": False,
                "writes_event_ledger": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    script_args = ["--idea-id", idea_id, "--text", idea_text, "--model", args.model]
    script_args.extend(["--temperature", str(args.temperature), "--max-tokens", str(args.max_tokens)])
    run_script("run_deepseek_idea.py", *script_args)
    write_text(
        lab / "agent_tasks.md",
        f"""# Multi-Agent Tasks: {idea_id}

开书实验要求 Codex app 同时启用：

- product_founder：读者钩子、类型承诺、前三章验证价值。
- technical_lead：长篇可控性、设定膨胀风险、状态/伏笔管理。
- qa_release：Gate A 成功标准、失败信号、首三章证据要求。

每个 agent 必须只读取：

- `state/idea_lab/{idea_id}/original_idea.md`
- `state/idea_lab/{idea_id}/deepseek_idea.md`

输出必须分别写入：

- `state/idea_lab/{idea_id}/product_founder_review.md`
- `state/idea_lab/{idea_id}/technical_lead_review.md`
- `state/idea_lab/{idea_id}/qa_release_review.md`

Codex 汇总必须写入：

- `state/idea_lab/{idea_id}/codex_synthesis.md`

汇总固定包含 A/B/C 三个方向：商业钩子、人物驱动、差异化/反套路。
""",
    )
    print(f"OK: idea lab created at state/idea_lab/{idea_id}")
    print("next: enable product_founder, technical_lead, and qa_release agents, then write codex_synthesis.md.")
    return 0


def command_idea_select(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--id", args.id, "--choice", args.choice]
    if args.reason:
        script_args.extend(["--reason", args.reason])
    if args.mixed_strategy:
        script_args.extend(["--mixed-strategy", args.mixed_strategy])
    if args.notes:
        script_args.extend(["--notes", args.notes])
    run_script("record_idea_selection.py", *script_args)
    return 0


def command_new_chapter(args: argparse.Namespace) -> int:
    script_args = ["--chapter", args.chapter]
    if args.force:
        script_args.append("--force")
    run_script("new_chapter.py", *script_args)
    print(f"next: fill outline/chapter_briefs/{args.chapter}.md")
    return 0


def command_start(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--chapter", args.chapter]
    if args.allow_placeholders:
        script_args.append("--allow-placeholders")
    if args.deepseek_dry_run:
        script_args.append("--deepseek-dry-run")
    run_script("start_chapter.py", *script_args)
    if args.deepseek:
        run_script("run_deepseek_generate.py", "--chapter", args.chapter)
    print(f"ready: state/context_pack/{args.chapter}.md")
    return 0


def command_deepseek_generate(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--chapter", args.chapter]
    if args.model:
        script_args.extend(["--model", args.model])
    if args.dry_run:
        script_args.append("--dry-run")
    run_script("run_deepseek_generate.py", *script_args)
    return 0


def command_review(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    if args.deepseek or args.deepseek_dry_run:
        script_args = ["--chapter", args.chapter]
        if args.input:
            script_args.extend(["--input", args.input])
        if args.deepseek_dry_run:
            script_args.append("--dry-run")
        run_script("run_deepseek_review.py", *script_args)

    if not args.skip_chapter_validate:
        run_script("validate_chapter.py", "--chapter", args.chapter)
    run_script("continuity_check.py", "--chapter", args.chapter)

    compare_args = ["--chapter", args.chapter]
    if args.allow_missing_reviews:
        compare_args.append("--allow-missing")
    run_script("compare_model_reviews.py", *compare_args)
    run_script("stop_check.py", "--chapter", args.chapter)
    print(f"next: human decision in reviews/{args.chapter}/decision.md")
    return 0


def command_codex_review_start(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    volume, chapter_file = chapter_parts(args.chapter)
    context = f"state/context_pack/{args.chapter}.md"
    review_input = args.input or f"chapters/{volume}/{chapter_file}"
    run_script(
        "review_manifest.py",
        "--chapter",
        args.chapter,
        "--reviewer",
        "codex",
        "--input",
        context,
        "--input",
        review_input,
    )
    print(f"next: write reviews/{args.chapter}/codex_integrated_review.md without reading DeepSeek review")
    return 0


def command_select_candidate(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--chapter", args.chapter, "--choice", args.choice, "--reason", args.reason]
    if args.adopt:
        script_args.extend(["--adopt", args.adopt])
    if args.reject:
        script_args.extend(["--reject", args.reject])
    if args.mixed_strategy:
        script_args.extend(["--mixed-strategy", args.mixed_strategy])
    if args.notes:
        script_args.extend(["--notes", args.notes])
    run_script("record_candidate_selection.py", *script_args)
    return 0


def command_land(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    selected_direction = args.selected_direction or args.source
    if not selected_direction:
        print("ERROR: land requires --selected-direction (or legacy --source).", file=sys.stderr)
        return 1
    script_args = [
        "--chapter",
        args.chapter,
        "--selected-direction",
        selected_direction,
        "--attestation",
        args.attestation,
    ]
    if args.notes:
        script_args.extend(["--notes", args.notes])
    run_script("record_chapter_landing.py", *script_args)
    return 0


def command_decision(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--chapter", args.chapter, "--decision", args.decision]
    for attr, option in [
        ("keep", "--keep"),
        ("change", "--change"),
        ("next_verify", "--next-verify"),
        ("setting_boundary", "--setting-boundary"),
        ("failure_condition", "--failure-condition"),
        ("notes", "--notes"),
    ]:
        value = getattr(args, attr, "")
        if value:
            script_args.extend([option, value])
    run_script("record_decision.py", *script_args)
    return 0


def command_event(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = [
        "--chapter",
        args.chapter,
        "--type",
        args.type,
        "--fact",
        args.fact,
        "--evidence-quote",
        args.evidence_quote,
        "--consequence",
        args.consequence,
    ]
    if args.event_id:
        script_args.extend(["--event-id", args.event_id])
    run_script("append_event.py", *script_args)
    if args.rebuild:
        run_script("build_derived_state.py")
    return 0


def command_close(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    chapter_parts(args.chapter)
    run_script("validate_event_ledger.py")
    if args.decision == "Ship":
        run_script("validate_chapter.py", "--chapter", args.chapter)
        run_script("continuity_check.py", "--chapter", args.chapter)
        run_script("stop_check.py", "--chapter", args.chapter)
        if not chapter_has_events(args.chapter):
            print(
                "ERROR: Ship requires at least one human-verified event for this chapter. "
                "Run `python scripts/novel.py event ...`.",
                file=sys.stderr,
            )
            return 1
        run_script("chapter_evidence.py", "--chapter", args.chapter)

    command_decision(args)
    run_script("build_derived_state.py")
    if args.decision == "Ship":
        run_script("diff_scope_check.py", "--role", "chapter", "--chapter", args.chapter)
    if args.commit_message:
        return command_commit(
            argparse.Namespace(message=args.commit_message, all=True, role="chapter", chapter=args.chapter)
        )
    return 0


def command_derive(_args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    run_script("validate_event_ledger.py")
    run_script("build_derived_state.py")
    return 0


def command_gate(args: argparse.Namespace) -> int:
    gate = args.gate.upper()
    config = GATES[gate]
    path_text = config["criteria"]
    needed = config["needed"]
    path = ROOT / path_text
    print(f"# Gate {gate}")
    print()
    print(f"minimum chapters before decision: {needed}")
    print(f"criteria file: {path.relative_to(ROOT).as_posix()}")
    print()
    print(read_text(path).strip())
    print()
    print("Human must decide. This command does not pass a gate automatically.")
    print()
    sys.stdout.flush()
    return run_script("gate_check.py", "--gate", gate, check=False)


def command_gate_check(args: argparse.Namespace) -> int:
    run_script("gate_check.py", "--gate", args.gate)
    return 0


def command_gate_close(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = ["--gate", args.gate, "--decision", args.decision, "--reason", args.reason]
    if args.next_limits:
        script_args.extend(["--next-limits", args.next_limits])
    if args.continue_to:
        script_args.extend(["--continue-to", args.continue_to])
    if args.budget:
        script_args.extend(["--budget", args.budget])
    if args.primary_model:
        script_args.extend(["--primary-model", args.primary_model])
    if args.must_fix:
        script_args.extend(["--must-fix", args.must_fix])
    if args.stop_trigger:
        script_args.extend(["--stop-trigger", args.stop_trigger])
    run_script("record_gate_decision.py", *script_args)
    return 0


def command_reader_test(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    script_args = [args.reader_command, "--gate", args.gate]
    if args.reader_command == "add":
        script_args.extend(["--reader", args.reader])
        if args.answers:
            script_args.extend(["--answers", args.answers])
        if args.target_reader:
            script_args.extend(["--target-reader", args.target_reader])
    else:
        if args.risk:
            script_args.extend(["--risk", args.risk])
        if args.recommendation:
            script_args.extend(["--recommendation", args.recommendation])
    run_script("reader_test.py", *script_args)
    return 0


def command_stop_check(args: argparse.Namespace) -> int:
    run_script("stop_check.py", "--chapter", args.chapter)
    return 0


def command_chapter_evidence(args: argparse.Namespace) -> int:
    run_script("chapter_evidence.py", "--chapter", args.chapter)
    return 0


def command_continuity(args: argparse.Namespace) -> int:
    run_script("continuity_check.py", "--chapter", args.chapter)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    script_args = ["--chapter", args.chapter]
    if args.allow_missing:
        script_args.append("--allow-missing")
    run_script("compare_model_reviews.py", *script_args)
    return 0


def command_diff_scope(args: argparse.Namespace) -> int:
    run_script("diff_scope_check.py", "--role", args.role, "--chapter", args.chapter)
    return 0


def command_doctor(_args: argparse.Namespace) -> int:
    return run_script("project_doctor.py", check=False)


def command_next_prompt(args: argparse.Namespace) -> int:
    script_args: list[str] = []
    if args.chapter:
        script_args.extend(["--chapter", args.chapter])
    return run_script("next_prompt.py", *script_args, check=False)


def command_brief_check(args: argparse.Namespace) -> int:
    return run_script("brief_check.py", "--chapter", args.chapter, check=False)


def command_event_suggest(args: argparse.Namespace) -> int:
    return run_script("event_suggest.py", args.chapter, check=False)


def command_canon_propose(args: argparse.Namespace) -> int:
    return run_script("canon_propose.py", args.chapter, check=False)


def command_health_report(args: argparse.Namespace) -> int:
    return run_script("health_report.py", "--to", args.to, check=False)


def command_self_test(_args: argparse.Namespace) -> int:
    run_script("self_test.py")
    return 0


def command_stop_record(args: argparse.Namespace) -> int:
    script_args = ["record", "--reason", args.reason]
    if args.chapter:
        script_args.extend(["--chapter", args.chapter])
    if args.lock_id:
        script_args.extend(["--lock-id", args.lock_id])
    run_script("project_lock.py", *script_args)
    return 0


def command_stop_resolve(args: argparse.Namespace) -> int:
    run_script("project_lock.py", "resolve", "--lock-id", args.lock_id, "--resolution", args.resolution)
    return 0


def command_stop_list(_args: argparse.Namespace) -> int:
    run_script("project_lock.py", "list", check=False)
    return 0


def command_backup(args: argparse.Namespace) -> int:
    run_script("build_backup.py", "--label", args.label)
    return 0


def command_export(args: argparse.Namespace) -> int:
    run_script("export_clean.py", "--volume", args.volume)
    return 0


def allowed_patterns_for(role: str, chapter: str) -> list[str]:
    volume, chapter_file = chapter_parts(chapter)
    return [
        pattern.format(chapter=chapter, volume=volume, chapter_file=chapter_file)
        for pattern in ROLE_PATTERNS[role]
    ]


def file_allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(str(path).replace("\\", "/"), pattern) for pattern in patterns)


def stage_role_files(role: str, chapter: str) -> int:
    patterns = allowed_patterns_for(role, chapter)
    files = changed_files()
    allowed = [path for path in files if file_allowed(path, patterns)]
    if not allowed:
        return 0
    run_git("add", "--", *allowed)
    return len(allowed)


def command_commit(args: argparse.Namespace) -> int:
    ensure_no_open_locks()
    if args.all and not args.role:
        print("ERROR: commit --all requires --role and --chapter so diff_scope_check can run.", file=sys.stderr)
        return 1
    if args.role:
        if not args.chapter:
            print("ERROR: --chapter is required when --role is used.", file=sys.stderr)
            return 1
        run_script("diff_scope_check.py", "--role", args.role, "--chapter", args.chapter)
    if args.all:
        if args.role:
            stage_role_files(args.role, args.chapter)
        else:
            run_git("add", "--", ".")
    status = run_git("status", "--short", check=False).stdout.strip()
    if not status:
        print("OK: nothing to commit")
        return 0
    ensure_git_identity()
    result = run_git("commit", "-m", args.message, check=False)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    print(result.stdout.strip())
    return 0


def command_status(_args: argparse.Namespace) -> int:
    run_script("project_status.py")
    return 0


def command_check(_args: argparse.Namespace) -> int:
    run_script("check_template.py")
    return 0


def command_flow(_args: argparse.Namespace) -> int:
    print(
        """# Simplified Full Flow

1. Open a copied template in Codex app.
   python scripts/novel.py init --name "Book Name"

2. Prepare and apply questionnaire.
   Easiest path:
   python scripts/novel.py go --name "Book Name"
   Fill setup_answers.md, then run:
   python scripts/novel.py go

3. Or start from idea lab.
   python scripts/novel.py idea --text "A cyber-folk suspense story about someone who refuses to believe in ghosts."
   Enable product_founder, technical_lead, and qa_release agents.
   python scripts/novel.py idea-select --id idea_... --choice A --reason "..."

4. Ask Codex to draft setup assets for human confirmation.
   Minimal worldview, protagonist card, relationships seed, volume mini-outline.
   Do not write canon until human confirms facts.

5. Start a chapter.
   Easiest path:
   python scripts/novel.py draft v01_c001
   Fill the brief if requested, then run the same command again.

6. Generate candidates.
   Codex candidate: Codex writes drafts/codex/v01_c001.md from context pack.
   DeepSeek candidate: python scripts/novel.py deepseek-generate v01_c001
   Human chooses Codex, DeepSeek, or mixed direction.
   python scripts/novel.py select-candidate v01_c001 --choice "Mixed" --reason "..." --mixed-strategy "..." --notes "..."

7. Land official chapter.
   Codex writes chapters/v01/c001.md.
   Do not copy DeepSeek directly into chapters.
   python scripts/novel.py land v01_c001 --selected-direction "Codex" --attestation "Codex integrated from context pack, brief, and selected direction; no direct DeepSeek copy."

8. Review.
   python scripts/novel.py codex-review-start v01_c001
   Codex writes reviews/v01_c001/codex_integrated_review.md without reading DeepSeek review.
   python scripts/novel.py review v01_c001 --deepseek

9. Human decision.
   python scripts/novel.py decision v01_c001 --decision "Revise once"
   or
   python scripts/novel.py decision v01_c001 --decision "Ship"

10. Record human-verified facts.
   python scripts/novel.py event v01_c001 --type character_decision --fact "..." --evidence-quote "..." --consequence "..."

11. Close chapter.
    python scripts/novel.py close v01_c001 --decision "Ship" --commit-message "complete v01 c001"

12. Gates.
    python scripts/novel.py reader-test summarize --gate A --risk "..." --recommendation "..."
    python scripts/novel.py gate-check A
    After 3 chapters: python scripts/novel.py gate A
    python scripts/novel.py gate-close A --decision continue --reason "..." --next-limits "..." --continue-to v01_c010 --budget "10章小连载验证" --primary-model Codex --must-fix "..." --stop-trigger "..."
    Human decides whether to continue to 10-chapter validation.

13. Maintenance.
    python scripts/novel.py backup --label before_gate_a
    python scripts/novel.py export --volume v01
    python scripts/novel.py status
"""
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-command hub for the novel workflow template.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Initialize a copied template for a new novel.")
    p.add_argument("--name", required=True)
    p.add_argument("--init-git", action="store_true")
    generated = p.add_mutually_exclusive_group()
    generated.add_argument("--clean-generated", dest="clean_generated", action="store_true", default=True)
    generated.add_argument("--keep-generated", dest="clean_generated", action="store_false")
    p.set_defaults(func=command_init)

    p = sub.add_parser("questionnaire", help="Create setup_answers.md from the questionnaire template.")
    p.add_argument("--output", default="setup_answers.md")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=command_questionnaire)

    p = sub.add_parser("apply-questionnaire", help="Apply startup questionnaire answers.")
    p.add_argument("--answers", default="setup_answers.md")
    p.add_argument("--allow-placeholders", action="store_true")
    p.set_defaults(func=command_apply_questionnaire)

    p = sub.add_parser("go", help="One-step helper that initializes and tells you the next action.")
    p.add_argument("--name", default="Untitled Novel")
    p.add_argument("--answers", default="setup_answers.md")
    p.add_argument("--chapter", default="v01_c001")
    p.add_argument("--clean-generated", action="store_true", help="Remove generated context/snapshot/prompt files before guiding.")
    p.add_argument("--deepseek-dry-run", action="store_true", help="When the brief is ready, also write the DeepSeek prompt without calling the API.")
    p.set_defaults(func=command_go)

    p = sub.add_parser("draft", help="Open or continue a chapter until its context pack is ready.")
    p.add_argument("chapter")
    p.add_argument("--name", default="Untitled Novel")
    p.add_argument("--answers", default="setup_answers.md")
    p.add_argument("--deepseek-dry-run", action="store_true", help="When the brief is ready, also write the DeepSeek prompt without calling the API.")
    p.set_defaults(func=command_draft)

    p = sub.add_parser("idea-form", help="Create a short idea seed form.")
    p.add_argument("--output", default="idea_seed.md")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=command_idea_form)

    p = sub.add_parser("idea", help="Create an idea lab from one idea and call DeepSeek.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", default="")
    source.add_argument("--seed", default="")
    p.add_argument("--id", type=validate_idea_id, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--max-tokens", type=int, default=5000)
    p.set_defaults(func=command_idea)

    p = sub.add_parser("idea-select", help="Record the selected idea direction and create pilot assets.")
    p.add_argument("--id", required=True, type=validate_idea_id)
    p.add_argument("--choice", required=True, choices=["A", "B", "C", "Mixed"])
    p.add_argument("--reason", default="")
    p.add_argument("--mixed-strategy", default="")
    p.add_argument("--notes", default="")
    p.set_defaults(func=command_idea_select)

    p = sub.add_parser("new-chapter", help="Create chapter brief and review workspace.")
    p.add_argument("chapter")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=command_new_chapter)

    p = sub.add_parser("start", help="Build derived state and context pack for a chapter.")
    p.add_argument("chapter")
    p.add_argument("--allow-placeholders", action="store_true")
    p.add_argument("--deepseek", action="store_true", help="Call DeepSeek generation after context pack is built.")
    p.add_argument("--deepseek-dry-run", action="store_true", help="Write DeepSeek prompt without calling API.")
    p.set_defaults(func=command_start)

    p = sub.add_parser("deepseek-generate", help="Generate a DeepSeek candidate draft.")
    p.add_argument("chapter")
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=command_deepseek_generate)

    p = sub.add_parser("select-candidate", help="Record the human-selected candidate direction.")
    p.add_argument("chapter")
    p.add_argument("--choice", required=True, choices=["Codex", "DeepSeek", "Mixed", "Rewrite brief", "No usable candidate"])
    p.add_argument("--reason", required=True)
    p.add_argument("--adopt", default="")
    p.add_argument("--reject", default="")
    p.add_argument("--mixed-strategy", default="")
    p.add_argument("--notes", default="")
    p.set_defaults(func=command_select_candidate)

    p = sub.add_parser("land", help="Record provenance for the official chapter landing.")
    p.add_argument("chapter")
    direction_group = p.add_mutually_exclusive_group(required=True)
    direction_group.add_argument("--selected-direction", choices=["Codex", "DeepSeek", "Mixed"])
    direction_group.add_argument("--source", choices=["Codex", "DeepSeek", "Mixed"], help="Legacy alias for --selected-direction.")
    p.add_argument("--attestation", required=True)
    p.add_argument("--notes", default="")
    p.set_defaults(func=command_land)

    p = sub.add_parser("review", help="Run chapter validation, continuity, review comparison, and optional DeepSeek review.")
    p.add_argument("chapter")
    p.add_argument("--deepseek", action="store_true")
    p.add_argument("--deepseek-dry-run", action="store_true")
    p.add_argument("--input", default=None)
    p.add_argument("--skip-chapter-validate", action="store_true")
    p.add_argument("--allow-missing-reviews", action="store_true")
    p.set_defaults(func=command_review)

    p = sub.add_parser("codex-review-start", help="Record Codex review input manifest before manual Codex review.")
    p.add_argument("chapter")
    p.add_argument("--input", default=None)
    p.set_defaults(func=command_codex_review_start)

    p = sub.add_parser("decision", help="Record a human chapter decision.")
    p.add_argument("chapter")
    p.add_argument("--decision", required=True, choices=DECISIONS)
    p.add_argument("--keep", default="")
    p.add_argument("--change", default="")
    p.add_argument("--next-verify", default="")
    p.add_argument("--setting-boundary", default="")
    p.add_argument("--failure-condition", default="")
    p.add_argument("--notes", default="")
    p.set_defaults(func=command_decision)

    p = sub.add_parser("event", help="Append one human-verified event ledger entry.")
    p.add_argument("chapter")
    p.add_argument("--type", required=True, choices=sorted(ALLOWED_TYPES))
    p.add_argument("--fact", required=True)
    p.add_argument("--evidence-quote", required=True)
    p.add_argument("--consequence", required=True)
    p.add_argument("--event-id", default=None)
    p.add_argument("--no-rebuild", dest="rebuild", action="store_false")
    p.set_defaults(func=command_event, rebuild=True)

    p = sub.add_parser("close", help="Record decision, validate ledger, rebuild derived state, and optionally commit.")
    p.add_argument("chapter")
    p.add_argument("--decision", required=True, choices=DECISIONS)
    p.add_argument("--keep", default="")
    p.add_argument("--change", default="")
    p.add_argument("--next-verify", default="")
    p.add_argument("--setting-boundary", default="")
    p.add_argument("--failure-condition", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--commit-message", default=None)
    p.set_defaults(func=command_close)

    p = sub.add_parser("derive", help="Validate ledger and rebuild derived state.")
    p.set_defaults(func=command_derive)

    p = sub.add_parser("gate", help="Show gate criteria. Never auto-passes a gate.")
    p.add_argument("gate", choices=sorted(GATES))
    p.set_defaults(func=command_gate)

    p = sub.add_parser("gate-check", help="Check machine-verifiable evidence before a human gate decision.")
    p.add_argument("gate", choices=sorted(GATES))
    p.set_defaults(func=command_gate_check)

    p = sub.add_parser("gate-close", help="Record a human gate decision.")
    p.add_argument("gate", choices=sorted(GATES))
    p.add_argument("--decision", required=True, choices=["continue", "pause", "kill", "rework"])
    p.add_argument("--reason", required=True)
    p.add_argument("--next-limits", default="")
    p.add_argument("--continue-to", default="")
    p.add_argument("--budget", default="")
    p.add_argument("--primary-model", default="")
    p.add_argument("--must-fix", default="")
    p.add_argument("--stop-trigger", default="")
    p.set_defaults(func=command_gate_close)

    p = sub.add_parser("reader-test", help="Record or summarize reader-test evidence.")
    reader_sub = p.add_subparsers(dest="reader_command", required=True)
    rp = reader_sub.add_parser("add")
    rp.add_argument("--gate", required=True, choices=["A", "B"])
    rp.add_argument("--reader", required=True)
    rp.add_argument("--answers", default=None)
    rp.add_argument("--target-reader", default="unknown")
    rp.set_defaults(func=command_reader_test)
    rp = reader_sub.add_parser("summarize")
    rp.add_argument("--gate", required=True, choices=["A", "B"])
    rp.add_argument("--risk", default="")
    rp.add_argument("--recommendation", default="")
    rp.set_defaults(func=command_reader_test)

    p = sub.add_parser("stop-check", help="Evaluate machine-checkable stop rules.")
    p.add_argument("chapter")
    p.set_defaults(func=command_stop_check)

    p = sub.add_parser("chapter-evidence", help="Check per-chapter evidence before Ship close.")
    p.add_argument("chapter")
    p.set_defaults(func=command_chapter_evidence)

    p = sub.add_parser("evidence", help="Alias for chapter-evidence.")
    p.add_argument("chapter")
    p.set_defaults(func=command_chapter_evidence)

    p = sub.add_parser("continuity", help="Run continuity check for one chapter.")
    p.add_argument("chapter")
    p.set_defaults(func=command_continuity)

    p = sub.add_parser("compare", help="Compare Codex and DeepSeek reviews for one chapter.")
    p.add_argument("chapter")
    p.add_argument("--allow-missing", action="store_true")
    p.set_defaults(func=command_compare)

    p = sub.add_parser("diff-scope", help="Check changed files against a workflow role.")
    p.add_argument("--role", required=True, choices=sorted(ROLE_PATTERNS))
    p.add_argument("--chapter", required=True)
    p.set_defaults(func=command_diff_scope)

    p = sub.add_parser("doctor", help="Check whether the project environment is ready to run the workflow.")
    p.set_defaults(func=command_doctor)

    p = sub.add_parser("next-prompt", help="Print the next recommended Codex app prompt.")
    p.add_argument("--chapter", default=None)
    p.set_defaults(func=command_next_prompt)

    p = sub.add_parser("brief-check", help="Check a chapter brief for anti-drift requirements.")
    p.add_argument("chapter")
    p.set_defaults(func=command_brief_check)

    p = sub.add_parser("event-suggest", help="Suggest event ledger entries without writing them.")
    p.add_argument("chapter")
    p.set_defaults(func=command_event_suggest)

    p = sub.add_parser("canon-propose", help="Propose canon entries without writing canon.")
    p.add_argument("chapter")
    p.set_defaults(func=command_canon_propose)

    p = sub.add_parser("health-report", help="Print a long-form health report without mutating state.")
    p.add_argument("--to", required=True)
    p.set_defaults(func=command_health_report)

    p = sub.add_parser("stop-record", help="Record an unresolved stop-rule lock.")
    p.add_argument("--chapter", default="")
    p.add_argument("--reason", required=True)
    p.add_argument("--lock-id", default=None)
    p.set_defaults(func=command_stop_record)

    p = sub.add_parser("stop-resolve", help="Resolve a stop-rule lock.")
    p.add_argument("--lock-id", required=True)
    p.add_argument("--resolution", required=True)
    p.set_defaults(func=command_stop_resolve)

    p = sub.add_parser("stop-list", help="List unresolved stop-rule locks.")
    p.set_defaults(func=command_stop_list)

    p = sub.add_parser("backup", help="Create a backup zip without secrets/raw API JSON.")
    p.add_argument("--label", default="manual")
    p.set_defaults(func=command_backup)

    p = sub.add_parser("export", help="Export clean chapter text.")
    p.add_argument("--volume", default="v01")
    p.set_defaults(func=command_export)

    p = sub.add_parser("commit", help="Commit current changes.")
    p.add_argument("--message", required=True)
    p.add_argument("--all", action="store_true", help="Stage all files before committing.")
    p.add_argument("--role", choices=sorted(ROLE_PATTERNS), default=None)
    p.add_argument("--chapter", default=None)
    p.set_defaults(func=command_commit)

    p = sub.add_parser("status", help="Show project status and next likely action.")
    p.set_defaults(func=command_status)

    p = sub.add_parser("check", help="Run template integrity check.")
    p.set_defaults(func=command_check)

    p = sub.add_parser("self-test", help="Run local workflow regression tests.")
    p.set_defaults(func=command_self_test)

    p = sub.add_parser("flow", help="Print the complete simplified lifecycle.")
    p.set_defaults(func=command_flow)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
