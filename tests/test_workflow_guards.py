from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import hashlib
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def copy_repo() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "repo"
        shutil.copytree(
            ROOT,
            target,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "backups", "exports", "*.pyc"),
        )
        yield target


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def file_sha(repo: Path, relative: str) -> str:
    return hashlib.sha256((repo / relative).read_bytes()).hexdigest()


class WorkflowGuardTests(unittest.TestCase):
    def test_minimal_chapter_happy_path_closes_ship(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/premise.md", "# Premise\n\nA focused pilot premise.\n")
            write(repo, "outline/volume_01.md", "# Volume 01\n\nPilot arc.\n")
            write(repo, "bible/characters.yaml", "characters:\n  - id: protagonist\n    current_state: ready\n")
            write(repo, "bible/relationships.yaml", "relationships: []\n")
            write(repo, "bible/locations.yaml", "locations: []\n")
            write(repo, "bible/rules.md", "# Rules\n\nNo special rule yet.\n")
            write(repo, "bible/style_guide.md", "# Style Guide\n\nClear, direct prose.\n")
            brief_body = "A" * 320
            write(repo, "outline/chapter_briefs/v01_c001.md", f"# v01_c001 Brief\n\n{brief_body}\n")

            self.assertEqual(run(repo, "scripts/build_derived_state.py").returncode, 0)
            context = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "5000")
            self.assertEqual(context.returncode, 0, context.stdout + context.stderr)

            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

            write(repo, "chapters/v01/c001.md", "Official chapter text with a concrete protagonist choice.\n")
            write(repo, "drafts/codex/v01_c001.md", "Codex candidate text.\n")
            selection = run(
                repo,
                "scripts/novel.py",
                "select-candidate",
                "v01_c001",
                "--choice",
                "Codex",
                "--reason",
                "human selected Codex candidate",
                "--notes",
                "human selected Codex direction",
            )
            self.assertEqual(selection.returncode, 0, selection.stderr)
            landing = run(
                repo,
                "scripts/novel.py",
                "land",
                "v01_c001",
                "--source",
                "Codex",
                "--attestation",
                "Codex integrated the official chapter from the context pack, brief, and selected direction; no direct DeepSeek copy.",
            )
            self.assertEqual(landing.returncode, 0, landing.stderr)
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")

            manifest = run(repo, "scripts/novel.py", "codex-review-start", "v01_c001")
            self.assertEqual(manifest.returncode, 0, manifest.stderr)
            deepseek_manifest = run(
                repo,
                "scripts/review_manifest.py",
                "--chapter",
                "v01_c001",
                "--reviewer",
                "deepseek",
                "--input",
                "state/context_pack/v01_c001.md",
                "--input",
                "chapters/v01/c001.md",
            )
            self.assertEqual(deepseek_manifest.returncode, 0, deepseek_manifest.stdout + deepseek_manifest.stderr)
            review = run(repo, "scripts/novel.py", "review", "v01_c001")
            self.assertEqual(review.returncode, 0, review.stdout + review.stderr)
            event = run(
                repo,
                "scripts/novel.py",
                "event",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "The protagonist chooses action.",
                "--evidence-quote",
                "concrete protagonist choice",
                "--consequence",
                "The pilot can continue.",
            )
            self.assertEqual(event.returncode, 0, event.stderr)
            close = run(
                repo,
                "scripts/novel.py",
                "close",
                "v01_c001",
                "--decision",
                "Ship",
                "--keep",
                "protagonist agency",
                "--change",
                "none",
                "--next-verify",
                "chapter two hook",
                "--setting-boundary",
                "no new canon",
                "--failure-condition",
                "goal unclear",
            )
            self.assertEqual(close.returncode, 0, close.stdout + close.stderr)

    def test_novel_chapter_evidence_wrapper_reports_not_ready(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "chapter-evidence", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: NOT_READY", result.stdout)

    def test_close_ship_requires_structured_candidate_selection(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/model_disagreement.md", "# Model Disagreement\n\n无核心冲突。\n")
            write(
                repo,
                "reviews/v01_c001/continuity.md",
                "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n",
            )
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[]},"deepseek":{"inputs":[]}}\n',
            )
            event = run(
                repo,
                "scripts/novel.py",
                "event",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "quote",
                "--consequence",
                "consequence",
            )
            self.assertEqual(event.returncode, 0, event.stderr)

            close = run(repo, "scripts/novel.py", "close", "v01_c001", "--decision", "Ship")

            self.assertNotEqual(close.returncode, 0)
            self.assertIn("missing structured candidate selection", close.stdout)

    def test_stop_lock_blocks_writing_commands(self) -> None:
        with copy_repo() as temp:
            repo = temp
            lock = run(repo, "scripts/novel.py", "stop-record", "--reason", "blocked", "--lock-id", "lock_test")
            self.assertEqual(lock.returncode, 0, lock.stderr)

            commands = [
                ("start", "v01_c001", "--allow-placeholders"),
                ("deepseek-generate", "v01_c001", "--dry-run"),
                ("select-candidate", "v01_c001", "--choice", "Codex", "--reason", "blocked"),
                ("review", "v01_c001", "--allow-missing-reviews"),
                ("codex-review-start", "v01_c001"),
                ("decision", "v01_c001", "--decision", "Ship"),
                (
                    "event",
                    "v01_c001",
                    "--type",
                    "character_decision",
                    "--fact",
                    "fact",
                    "--evidence-quote",
                    "quote",
                    "--consequence",
                    "consequence",
                ),
                (
                    "close",
                    "v01_c001",
                    "--decision",
                    "Ship",
                    "--keep",
                    "blocked",
                    "--change",
                    "blocked",
                    "--next-verify",
                    "blocked",
                    "--setting-boundary",
                    "blocked",
                    "--failure-condition",
                    "blocked",
                ),
                ("reader-test", "add", "--gate", "A", "--reader", "r01"),
                ("reader-test", "summarize", "--gate", "A", "--risk", "risk"),
                ("derive",),
                ("gate-close", "A", "--decision", "pause", "--reason", "blocked"),
                ("commit", "--message", "blocked"),
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = run(repo, "scripts/novel.py", *command)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("unresolved stop locks", result.stderr)

    def test_gate_continue_requires_ready_evidence(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(
                repo,
                "scripts/novel.py",
                "gate-close",
                "A",
                "--decision",
                "continue",
                "--reason",
                "not ready",
                "--next-limits",
                "limit",
                "--continue-to",
                "v01_c010",
                "--budget",
                "budget",
                "--primary-model",
                "Codex",
                "--must-fix",
                "fix",
                "--stop-trigger",
                "stop",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("gate evidence is not ready", result.stderr)

    def test_gate_continue_requires_structured_forward_plan(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(
                repo,
                "scripts/record_gate_decision.py",
                "--gate",
                "A",
                "--decision",
                "continue",
                "--reason",
                "continue",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("structured gate continue fields are required", result.stderr)

    def test_structured_decision_fields_required_for_ship(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/record_decision.py", "--chapter", "v01_c001", "--decision", "Ship")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("structured decision fields are required", result.stderr)

    def test_reader_response_requires_complete_answers_and_target_reader(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "answers.json", "{}\n")
            result = run(
                repo,
                "scripts/reader_test.py",
                "add",
                "--gate",
                "A",
                "--reader",
                "r01",
                "--answers",
                "answers.json",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("target reader must be identified", result.stderr)
            self.assertIn("missing answer", result.stderr)

    def test_diff_scope_rejects_untracked_out_of_scope_file(self) -> None:
        with copy_repo() as temp:
            repo = temp
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

            write(repo, "bible/untracked_scope_violation.md", "bad\n")
            result = run(repo, "scripts/diff_scope_check.py", "--role", "state", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bible/untracked_scope_violation.md", result.stdout)

    def test_append_event_invalid_duplicate_does_not_mutate_ledger(self) -> None:
        with copy_repo() as temp:
            repo = temp
            base_args = [
                "scripts/append_event.py",
                "--chapter",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "quote",
                "--consequence",
                "consequence",
                "--event-id",
                "v01_c001_e001",
            ]
            first = run(repo, *base_args)
            before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")
            second = run(repo, *base_args)
            after = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(before, after)

    def test_deepseek_review_rejects_review_file_as_input(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "codex review\n")

            result = run(
                repo,
                "scripts/run_deepseek_review.py",
                "--chapter",
                "v01_c001",
                "--input",
                "reviews/v01_c001/codex_integrated_review.md",
                "--dry-run",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Allowed inputs", result.stderr)

    def test_deepseek_generate_rejects_invalid_chapter_id(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/run_deepseek_generate.py", "--chapter", "../bad", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid chapter id", result.stderr)

    def test_deepseek_review_dry_run_does_not_write_manifest(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "chapter\n")

            result = run(repo, "scripts/run_deepseek_review.py", "--chapter", "v01_c001", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((repo / "external_runs/deepseek/v01_c001/review.prompt.md").exists())
            self.assertFalse((repo / "reviews/v01_c001/review_manifest.json").exists())

    def test_empty_export_fails(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/export_clean.py", "--volume", "v01")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no non-empty chapters", result.stderr)

    def test_export_refuses_unshipped_chapter(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "draft text\n")

            result = run(repo, "scripts/export_clean.py", "--volume", "v01")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to export unshipped chapter v01_c001", result.stderr)

    def test_commit_all_requires_role_scope(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "commit", "--message", "test", "--all")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("commit --all requires --role", result.stderr)

    def test_gate_check_not_ready_fails(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/gate_check.py", "--gate", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: NOT_READY", result.stdout)
            self.assertIn("reader responses below minimum", result.stdout)

    def test_start_chapter_blocks_fourth_chapter_before_gate_a(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/chapter_briefs/v01_c004.md", "# v01_c004 Brief\n\n" + ("A" * 320) + "\n")

            result = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c004")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gate A", result.stderr)

    def test_start_chapter_blocks_twenty_six_before_gate_c(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/gates/gate_a.json", '{"decision":"continue"}\n')
            write(repo, "state/gates/gate_b.json", '{"decision":"continue"}\n')
            write(repo, "outline/chapter_briefs/v01_c026.md", "# v01_c026 Brief\n\n" + ("A" * 320) + "\n")

            result = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c026")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gate C", result.stderr)

    def test_stop_check_records_project_lock_on_stop(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "reviews/v01_c001/continuity.md", "# Continuity\n\nstatus: BLOCKED\np0_count: 0\np1_count: 1\n")

            result = run(repo, "scripts/stop_check.py", "--chapter", "v01_c001")
            locks = (repo / "state/stops/project_locks.json").read_text(encoding="utf-8")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: STOP", result.stdout)
            self.assertIn("continuity_check has unresolved P0/P1", locks)

    def test_direct_write_script_blocks_stop_lock(self) -> None:
        with copy_repo() as temp:
            repo = temp
            lock = run(repo, "scripts/project_lock.py", "record", "--reason", "blocked", "--lock-id", "direct_lock")
            self.assertEqual(lock.returncode, 0, lock.stderr)

            result = run(
                repo,
                "scripts/record_decision.py",
                "--chapter",
                "v01_c001",
                "--decision",
                "Kill chapter",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unresolved stop locks", result.stderr)

    def test_chapter_evidence_rejects_bad_manifest_shapes(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "state/selections/v01_c001.json", '{"choice":"Codex"}\n')
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/model_disagreement.md", "# Model Disagreement\n\n无核心冲突。\n")
            write(repo, "reviews/v01_c001/continuity.md", "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n")

            write(repo, "state/selections/v01_c001.json", '{"choice":"Invalid","reason":"bad","selected_candidates":[]}\n')
            invalid_choice = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(invalid_choice.returncode, 0)
            self.assertIn("invalid candidate selection choice", invalid_choice.stdout)

            write(repo, "state/selections/v01_c001.json", '{"choice":"Codex","reason":"ok","selected_candidates":[]}\n')

            write(repo, "reviews/v01_c001/review_manifest.json", '{"codex":{"inputs":[]},"deepseek":{"inputs":[]}}\n')
            empty_inputs = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(empty_inputs.returncode, 0)
            self.assertIn("has no inputs", empty_inputs.stdout)

            context_item = {
                "path": "state/context_pack/v01_c001.md",
                "sha256": file_sha(repo, "state/context_pack/v01_c001.md"),
            }
            chapter_item = {
                "path": "chapters/v01/c001.md",
                "sha256": file_sha(repo, "chapters/v01/c001.md"),
            }
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s]},"deepseek":{"inputs":[%s]}}\n'
                % (__import__("json").dumps(context_item), __import__("json").dumps(context_item)),
            )
            missing_required = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(missing_required.returncode, 0)
            self.assertIn("manifest missing input chapters/v01/c001.md", missing_required.stdout)

            bad_chapter_item = dict(chapter_item)
            bad_chapter_item["sha256"] = "bad"
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(bad_chapter_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )
            hash_mismatch = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(hash_mismatch.returncode, 0)
            self.assertIn("hash mismatch", hash_mismatch.stdout)

            missing_item = {"path": "state/context_pack/missing.md", "sha256": "bad"}
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                    __import__("json").dumps(missing_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )
            missing_disk = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(missing_disk.returncode, 0)
            self.assertIn("manifest has disallowed input state/context_pack/missing.md", missing_disk.stdout)

    def test_chapter_evidence_rejects_disallowed_manifest_input(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            context_item = {
                "path": "state/context_pack/v01_c001.md",
                "sha256": file_sha(repo, "state/context_pack/v01_c001.md"),
            }
            chapter_item = {
                "path": "chapters/v01/c001.md",
                "sha256": file_sha(repo, "chapters/v01/c001.md"),
            }
            review_item = {
                "path": "reviews/v01_c001/deepseek_integrated_review.md",
                "sha256": file_sha(repo, "reviews/v01_c001/deepseek_integrated_review.md"),
            }
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                    __import__("json").dumps(review_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest has disallowed input reviews/v01_c001/deepseek_integrated_review.md", result.stdout)

    def test_event_id_must_match_chapter(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(
                repo,
                "bad_ledger.jsonl",
                '{"event_id":"v01_c002_e001","chapter":"v01_c001","type":"character_decision","fact":"fact","evidence_quote":"quote","consequence":"consequence","verified_by":"human"}\n',
            )

            result = run(repo, "scripts/validate_event_ledger.py", "--path", "bad_ledger.jsonl")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match chapter", result.stderr)

    def test_context_pack_oversize_fails_without_allow_truncated(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/premise.md", "# Premise\n\n" + ("x" * 4000) + "\n")

            result = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "500")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("context pack exceeds", result.stdout)
            self.assertTrue((repo / "state/snapshots/v01_c001_oversize_context.md").exists())

    def test_backup_excludes_secrets_raw_json_and_prompts(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, ".env", "SECRET=1\n")
            write(repo, "external_runs/deepseek/v01_c001/generate.raw.json", "{}\n")
            write(repo, "external_runs/deepseek/v01_c001/generate.prompt.md", "private prompt\n")

            result = run(repo, "scripts/build_backup.py", "--label", "test")

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = next((repo / "backups").glob("*_test.zip"))
            with zipfile.ZipFile(backup) as archive:
                names = set(archive.namelist())
            self.assertNotIn(".env", names)
            self.assertNotIn("external_runs/deepseek/v01_c001/generate.raw.json", names)
            self.assertNotIn("external_runs/deepseek/v01_c001/generate.prompt.md", names)


if __name__ == "__main__":
    unittest.main()
